"""Deterministic evidence gate with a single owner for the retry counter."""

import json

from skill_common import cli, issue, update_metrics

FIELDS = ("entity_conflicts", "coverage_gaps", "attribution_warnings", "missing_evidence")
SKILL = "epistemic_hold_gate"


def blocking_findings(board):
    found = []
    for field in FIELDS:
        for finding in board[field]:
            if not isinstance(finding, dict):
                finding = issue(field.upper(), str(finding), retryable=field != "missing_evidence")
            if finding.get("blocking") is not False:
                found.append(finding)
    if not board["schema_ok"]:
        found.append(issue("ARTIFACT_SCHEMA_FAILED", board["schema_error"] or "产物回读未通过",
                           retryable=True))
    return found


def run(board):
    count, maximum = board["retry_count"], board["max_retry"]
    if count < 0 or maximum < 0:
        raise ValueError("retry_count and max_retry must be nonnegative")

    findings = blocking_findings(board)
    holds = [item for item in findings if item.get("retryable") is not True]
    claim_ids = {c["claim_id"] for c in board["claims"]
                 if isinstance(c, dict) and isinstance(c.get("claim_id"), str)}
    local_targets = sorted({item["claim_id"] for item in findings
                            if item.get("retryable") is True and item.get("claim_id") in claim_ids})
    checklist_ids = {check["id"] for check in board.get("required_checks", [])}
    check_targets = sorted({item["requirement_id"] for item in findings
                            if item.get("retryable") is True and item.get("requirement_id") in checklist_ids})
    feedback = {"findings": findings}
    if (board.get("word_retention_requested") and "roundtrip_schema_guard" in board["trace_metrics"]
            and any(f.get("retention_mode") == "artifact" for f in findings)):
        route, reason = "EVIDENCE_HOLD", "DELIVERED_WORD_RETENTION_FAILED"
    elif not findings:
        route, reason = "PASS", "NO_BLOCKERS"
    elif board.get("checklist_review") and "roundtrip_schema_guard" in board["trace_metrics"]:
        route, reason = "EVIDENCE_HOLD", "REVIEW_DELIVERY_HAS_BLOCKERS"
    elif board.get("checklist_review") and check_targets and count < maximum:
        route, reason = "RETRY_CONFLICT", "REPAIR_REQUIRED_CHECKS"
        feedback["repair_requirement_ids"] = check_targets
        board["retry_count"] = count + 1
    elif (not board.get("checklist_review") and holds and local_targets and count < maximum
          and "roundtrip_schema_guard" not in board["trace_metrics"]):
        route, reason = "RETRY_CONFLICT", "LOCAL_REPAIR_WITH_HOLD"
        feedback["repair_claim_ids"] = local_targets
        board["retry_count"] = count + 1
    elif holds:
        route = "EVIDENCE_HOLD"
        reason = ("REQUIRED_EVIDENCE_ABSENT" if any(
            finding.get("confirmed_absent") is True for finding in holds
        ) else "UNVERIFIED_EVIDENCE")
    elif count >= maximum:
        route, reason = "MAX_RETRY_REACHED", "RETRY_EXHAUSTED"
    else:
        route, reason = "RETRY_CONFLICT", "REPAIRABLE_CONFLICT"
        physical_target = any(f.get("code") == "PHYSICAL_VALUE_MISMATCH"
                              and f.get("claim_id") in local_targets
                              and f.get("expected_value") is not None for f in findings)
        if board.get("entity_review_extensions") and local_targets and (
                physical_target or all(f.get("claim_id") in local_targets for f in findings)):
            feedback["repair_claim_ids"] = local_targets
        board["retry_count"] = count + 1

    board["route_status"] = route
    board["retry_feedback"] = json.dumps(
        dict(feedback, reason=reason), ensure_ascii=False
    ) if findings else ""
    update_metrics(board, SKILL, route=route, reason=reason, blocking_count=len(findings),
                   retry_count_before=count, retry_count_after=board["retry_count"], max_retry=maximum)
    return board


if __name__ == "__main__":
    cli(run)
