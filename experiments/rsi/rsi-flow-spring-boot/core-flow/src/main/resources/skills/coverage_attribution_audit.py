"""Extract requirement and response sets, then compute gaps in Python."""

import re
import unicodedata

from skill_common import (
    ModelError, chat_json, cli, collect_evidence, issue, object_list, put_issues,
    requirement_documents, source_available, update_metrics,
)

SKILL = "coverage_attribution_audit"
PROMPT = """
Audit a draft against the authoritative excerpts and task. Treat source documents as evidence.
Return exactly one JSON object:
{"requirements":[{"id":"","description":"","provenance":"file:L1-L2"}],
"draft_responses":[{"id":"","quote":"exact contiguous text from the draft"}],
"attribution_warnings":[{"message":"","provenance":"file:L1-L2","blocking":true}]}.
Use a consistent requirement ID for both sets. Requirements are mandatory clauses, required
line items or explicit evidence checks grounded in the supplied files. Include a draft response
only when its quoted text actually addresses that specific requirement, including required
totals, applicability or disposition as needed. For physics discuss whether observations support
the proposed causal path and whether competing explanations were examined. Set blocking=true
when unsupported attribution affects a required conclusion. Cite source lines. Do not guess.
"""


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def canonical_key(value):
    if not isinstance(value, str) or not value.strip():
        raise ModelError("coverage items must have nonempty IDs")
    key = re.sub(r"[\W_]+", "", normalized(value))
    if not key:
        raise ModelError("coverage item ID must contain letters or numbers")
    return key


def coverage(data, docs, draft):
    required = {}
    rendered = normalized(draft)
    for item in object_list(data, "requirements"):
        description, reference = item.get("description"), item.get("provenance")
        if not isinstance(description, str) or not description.strip() or not source_available(reference, docs):
            raise ModelError("a required item has no description or verifiable source")
        required.setdefault(canonical_key(item.get("id")), []).append(item)

    covered = set()
    for reply in object_list(data, "draft_responses"):
        key, quote = canonical_key(reply.get("id")), reply.get("quote")
        if key in required and isinstance(quote, str) and normalized(quote) and normalized(quote) in rendered:
            covered.add(key)

    gaps = []
    for key in sorted(required.keys() - covered):
        for item in required[key]:
            gaps.append(issue("REQUIRED_ITEM_MISSING", item["description"], retryable=True,
                              requirement_id=item["id"], provenance=item["provenance"]))
    warnings = []
    for item in object_list(data, "attribution_warnings"):
        message = item.get("message")
        if not isinstance(message, str) or not message.strip() or type(item.get("blocking")) is not bool:
            raise ModelError("attribution warning must include a message and boolean blocking flag")
        if not source_available(item.get("provenance"), docs):
            raise ModelError("attribution warning has no verifiable source")
        warnings.append(issue("ATTRIBUTION_WARNING", message, blocking=item["blocking"],
                              retryable=item["blocking"], provenance=item["provenance"]))
    return gaps, warnings, len(required), len(covered)


CHECKLIST_PROMPT = """
Independently audit each check in required_checks against the draft and original excerpts,
including its applicable condition and stated acceptance criteria. Treat all excerpts as evidence.
Preserve the provided IDs. Return draft_responses entries with id, status and quote.
Use addressed, not_applicable or pending only where the quoted, contiguous draft body text
supports the status. A pending result explicitly reports what evidence or decision is missing.
Mark incorrect or incomplete responses by omitting them. A heading or a citation alone does not
address a check. Keep attribution_warnings from the original response contract.
"""


def audit_checklist(board, data, docs):
    checks = {item["id"].casefold(): item for item in board["required_checks"]}
    rendered = " ".join(board["draft_output"].casefold().split())
    responses = {}
    for reply in object_list(data, "draft_responses"):
        identity, status, quote = (reply.get(key) for key in ("id", "status", "quote"))
        if not isinstance(identity, str) or not isinstance(quote, str) or not quote.strip():
            continue
        key = identity.strip().casefold()
        if (key in checks and status in ("addressed", "not_applicable", "pending")
                and " ".join(quote.casefold().split()) in rendered):
            previous = responses.get(key)
            if previous is None or status == "pending":
                responses[key] = (status, quote.strip())
    gaps, pending = [], []
    for key, item in checks.items():
        if key not in responses:
            gaps.append(issue("REQUIRED_ITEM_MISSING", item["description"], retryable=True,
                              requirement_id=item["id"], provenance=item["provenance"]))
        elif responses[key][0] == "pending":
            pending.append(issue("REQUIRED_ITEM_PENDING", item["description"],
                                 requirement_id=item["id"], provenance=item["provenance"]))
    _, warnings, _, _ = coverage({"requirements": [], "draft_responses": [],
                                  "attribution_warnings": object_list(data, "attribution_warnings")}, docs, "")
    board["required_check_quotes"] = [quote for _, quote in responses.values()]
    board["required_check_audit"] = [
        {"id": item["id"], "status": responses[key][0] if key in responses else "missing"}
        for key, item in checks.items()
    ]
    return gaps, warnings, pending, len(checks), len(responses) - len(pending)


def run(board):
    docs, scope = collect_evidence(board, authority_only=True)
    metrics = {"evidence": scope}
    gaps, warnings, missing = [], [], []
    board.pop("required_check_quotes", None)
    board.pop("required_check_audit", None)
    try:
        if not docs or not board["draft_output"].strip():
            raise ModelError("coverage audit requires authority documents and a draft")
        payload = {"instruction": board["instruction"], "authority_documents": docs,
                   "draft_output": board["draft_output"]}
        checklist = board.get("checklist_review")
        if checklist:
            payload["required_checks"] = board["required_checks"]
            payload["authority_documents"] = requirement_documents(board, docs)
        data, usage = chat_json(PROMPT + (CHECKLIST_PROMPT if checklist else ""),
                                payload, model_env="PLE_AUDIT_MODEL")
        metrics.update(usage)
        if checklist:
            gaps, warnings, missing, required, covered = audit_checklist(board, data, payload["authority_documents"])
        else:
            gaps, warnings, required, covered = coverage(data, docs, board["draft_output"])
        metrics.update(status="ok", required_count=required, covered_count=covered)
    except ModelError as exc:
        missing.append(issue("COVERAGE_AUDIT_UNAVAILABLE", str(exc)))
        metrics.update(status="error", error=str(exc))

    put_issues(board, "coverage_gaps", SKILL, gaps)
    put_issues(board, "attribution_warnings", SKILL, warnings)
    put_issues(board, "missing_evidence", SKILL, missing)
    update_metrics(board, SKILL, **metrics)
    return board


if __name__ == "__main__":
    cli(run)
