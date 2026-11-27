"""Detect regressions in scoped claim repairs and in the exported Word document."""
import json
import re
import unicodedata
from copy import deepcopy

from skill_common import artifact_location, cli, issue, put_issues, update_metrics

SKILL = "revision_retention"
FIELDS = ("param", "value", "unit", "target_entity", "source_entity", "provenance",
          "regime_or_version", "calculation")


def index_claims(claims):
    if not isinstance(claims, list):
        raise ValueError("claims must be a list")
    indexed = {}
    for claim in claims:
        cid = claim.get("claim_id") if isinstance(claim, dict) else None
        if not isinstance(cid, str) or not cid.strip() or cid in indexed:
            raise ValueError("each claim needs a unique nonempty claim_id")
        indexed[cid] = claim
    return indexed


def text_list(values, name):
    if not isinstance(values, list) or not all(isinstance(s, str) and s.strip() for s in values):
        raise ValueError(f"{name} must be a list of nonempty strings")
    return list(dict.fromkeys(values))


def identity(board):
    return [board["task_dir"], board["task_id"]]


def snapshot(board):
    claims = index_claims(board["claims"])
    if not claims:
        raise ValueError("no baseline claims to preserve")
    feedback = json.loads(board["retry_feedback"] or "{}")
    if not isinstance(feedback, dict):
        raise ValueError("retry_feedback must encode an object")
    targets = text_list(feedback.get("repair_claim_ids", []), "repair_claim_ids")
    if set(targets) - claims.keys():
        raise ValueError("repair_claim_ids contains an unknown claim")
    texts = text_list(board.get("retention_required_text", []), "retention_required_text")
    prior = board.get("retention_snapshot")
    if isinstance(prior, dict) and prior.get("task") == identity(board):
        if prior["retry_count"] == board["retry_count"]:
            if prior["targets"] != targets or prior["texts"] != texts:
                raise ValueError("conflicting retention settings for an existing snapshot")
            return  # Replaying the node must never reset its baseline.
        if prior["retry_count"] > board["retry_count"]:
            raise ValueError("snapshot belongs to a later repair round")
        # Do not establish a new baseline on top of a previous, unrepaired loss.
        if compare(board, prior):
            raise ValueError("restore earlier retention regressions before taking a new snapshot")
    board["retention_snapshot"] = dict(task=identity(board), retry_count=board["retry_count"],
                                       claims=deepcopy(board["claims"]), targets=targets, texts=texts)


def compare(board, saved):
    before = index_claims(saved["claims"])
    after = index_claims(board["claims"])
    findings = []
    for cid, old in before.items():
        if cid not in after:
            findings.append(issue("CLAIM_DROPPED", f"{cid} was removed", claim_id=cid, retryable=True,
                                  before=old))
        elif cid not in saved["targets"]:
            new = after[cid]
            changes = {k: {"before": old.get(k), "after": new.get(k)}
                       for k in FIELDS if (k in old) != (k in new) or old.get(k) != new.get(k)}
            if changes:
                findings.append(issue("CLAIM_CHANGED_OUTSIDE_REPAIR", f"{cid} changed outside the repair scope",
                                      claim_id=cid, retryable=True, changes=changes))
    return findings


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def inspect_artifact(board, saved):
    from docx import Document
    from docx.text.paragraph import Paragraph

    if not saved["texts"]:
        raise ValueError("snapshot contains no required Word statements")
    path = artifact_location(board, board["artifact_path"], must_exist=True)
    if path.suffix.lower() != ".docx":
        raise ValueError("Word retention check requires a .docx artifact")
    doc = Document(path)
    # Includes paragraphs inside cells, including nested tables. Do not join unrelated cells.
    statements = set()
    for element in doc.element.body.xpath(".//w:p"):
        paragraph = normalized(Paragraph(element, doc).text)
        statements.add(paragraph)
        statements.update(re.split(r"(?<=[.!?])\s+|(?<=[。！？])\s*", paragraph))
    return [issue("ARTIFACT_STATEMENT_MISSING", "Required wording missing in Word body or tables",
                  retryable=True, required_text=s) for s in saved["texts"] if normalized(s) not in statements]


def run(board):
    phase = board.get("retention_mode")
    try:
        if phase == "snapshot":
            snapshot(board)
            findings, status = [], "captured"
        elif phase in ("compare", "artifact"):
            saved = board.get("retention_snapshot")
            if phase == "artifact" and saved is None and board.get("retention_required_text"):
                saved = {"task": identity(board), "texts": text_list(board["retention_required_text"],
                                                                    "retention_required_text")}
            if not isinstance(saved, dict) or saved.get("task") != identity(board):
                raise ValueError("no snapshot for the current task")
            if phase == "compare" and saved["retry_count"] != board["retry_count"]:
                raise ValueError("snapshot belongs to a different repair round")
            findings = compare(board, saved) if phase == "compare" else inspect_artifact(board, saved)
            status = "regression" if findings else "passed"
        else:
            raise ValueError("retention_mode must be snapshot, compare or artifact")
    except Exception as exc:
        findings = [issue("RETENTION_UNVERIFIED", str(exc))]
        status = "unverified"

    report = dict(mode=phase, status=status, findings=findings)
    board["retention_result"] = report
    # Rechecking Word must not erase an unresolved blackboard finding (and vice versa).
    kept = [f for f in board["coverage_gaps"] if isinstance(f, dict) and f.get("source_skill") == SKILL
            and f.get("retention_mode") != phase and f.get("retention_mode") in ("snapshot", "compare", "artifact")]
    put_issues(board, "coverage_gaps", SKILL, kept + [dict(f, retention_mode=phase) for f in findings])
    update_metrics(board, SKILL, mode=phase, status=status, findings_count=len(findings))
    return board


if __name__ == "__main__":
    cli(run)
