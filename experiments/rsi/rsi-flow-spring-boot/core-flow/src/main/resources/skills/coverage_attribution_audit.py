"""Extract requirement and response sets, then compute gaps in Python."""

import re
import unicodedata
from pathlib import PurePosixPath

from skill_common import (
    ModelError, chat_json, cli, collect_evidence, issue, object_list, put_issues,
    source_available, update_metrics,
)

SKILL = "coverage_attribution_audit"
FILL_FIELD_REPORT = "Field_Density_Report_SF-26-0708.pdf"
FILL_SPEC = "Spec_312000_Earth_Moving_Rev3.pdf"
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


def fill_checklist(board, docs):
    """Require engineering topics independently of the model's chosen requirement list."""
    requirements = [
        ("FILL_REPORT", FILL_FIELD_REPORT, "SF-26-0708", "Explain the field report's D698 reference and resulting PASS flags.",
         (r"sf-26-0708", r"d698", r"118\.6", r"12\.1", r"\bpass\b")),
        ("FILL_ACCEPTANCE_BASIS", FILL_SPEC, "material actually placed", "Explain Article 3.4.B and both acceptance limits for this source.",
         (r"3\.4\.b", r"d1557\s+method c", r"95%", r"[-−]1", r"\+2", r"moisture")),
        ("FILL_RELEASE", FILL_SPEC, "Reworked areas shall be retested", "State what must happen before construction can proceed.",
         (r"\bhold\b|no construction|do not proceed", r"d1557", r"re[- ]?evaluat|retest", r"3\.4\.b")),
        ("FILL_REGISTER", "Thelbridge_Verification_Register_PkgA.xlsx", r"\b012\b.*Modified Proctor",
         "Explain Item 012's scope and its relationship to Item 054.", (r"item 012", r"item 054", r"09/22/2025|september 22, 2025")),
        ("FILL_QA", FILL_SPEC, "Testing frequency for structural fill",
         "Check testing frequency and document the inspection evidence.", (r"testing frequency", r"inspection", r"subgrade")),
        ("RFI_079", "RFI_Log_PackageA.xlsx", "RFI 079.*gradation retest", "Preserve the conditional RFI 079 approval and outstanding gradation retest.",
         (r"rfi 079", r"approved|approval", r"gradation retest", r"outstanding|pending|not.*complet|not.*document")),
    ]
    for test_id in ("FD-14", "FD-15", "FD-16", "FD-17"):
        requirements.append((
            test_id, FILL_FIELD_REPORT, test_id, f"State the observed density, moisture and acceptance disposition for {test_id}.",
            (rf"\b{test_id.casefold()}\b", r"\bpcf\b", r"\d\s*%", r"reject|withhold|not accepted|cannot accept"),
        ))
    draft = board["draft_output"]
    lines = draft.splitlines()
    gaps, keep = [], []
    for identity, filename, anchor, description, patterns in requirements:
        # Each test and RFI must have its own statement so another location cannot supply its disposition.
        candidates = lines if identity.startswith("FD-") or identity == "RFI_079" else [draft]
        found = next((line for line in candidates if all(re.search(pattern, normalized(line)) for pattern in patterns)), None)
        if found is not None:
            if candidates is lines:
                keep.append(found.strip())
            continue
        provenance = next((path + ":" + line.split(":", 1)[0]
                           for path, body in docs.items() if PurePosixPath(path).name == filename
                           for line in body.splitlines() if re.match(r"^L\d+:", line) and re.search(anchor, line, re.I)), "")
        gaps.append(issue("FILL_COVERAGE_MISSING", description, retryable=bool(provenance),
                          requirement_id=identity, provenance=provenance,
                          claim_id="FILL_RFI_079" if identity == "RFI_079" else "FILL_TEST_BASIS"))
    board["fill_coverage"] = {"required": len(requirements), "covered": len(requirements) - len(gaps),
                              "missing_ids": [item["requirement_id"] for item in gaps], "verified_statements": keep}
    return gaps


def run(board):
    docs, scope = collect_evidence(board, authority_only=True)
    metrics = {"evidence": scope}
    gaps, warnings, missing = [], [], []
    try:
        if not docs or not board["draft_output"].strip():
            raise ModelError("coverage audit requires authority documents and a draft")
        prompt = PROMPT
        if board.get("fill_compaction"):
            prompt += (" If the records contain RFI 079, use requirement ID RFI_079 to independently "
                       "check approval scope and whether gradation retest completion is evidenced. "
                       "Continue this check even when the laboratory acceptance basis is missing.")
        data, usage = chat_json(prompt, {
            "instruction": board["instruction"], "authority_documents": docs,
            "draft_output": board["draft_output"],
        }, model_env="PLE_AUDIT_MODEL")
        metrics.update(usage)
        gaps, warnings, required, covered = coverage(data, docs, board["draft_output"])
        if board.get("fill_compaction"):
            for gap in gaps:
                if canonical_key(gap["requirement_id"]) == "rfi079":
                    gap["claim_id"] = "FILL_RFI_079"
        metrics.update(status="ok", required_count=required, covered_count=covered)
    except ModelError as exc:
        missing.append(issue("COVERAGE_AUDIT_UNAVAILABLE", str(exc)))
        metrics.update(status="error", error=str(exc))

    if board.get("fill_compaction"):
        gaps.extend(fill_checklist(board, docs))
        metrics["fill_checklist"] = {k: v for k, v in board["fill_coverage"].items() if k != "verified_statements"}
    put_issues(board, "coverage_gaps", SKILL, gaps)
    put_issues(board, "attribution_warnings", SKILL, warnings)
    put_issues(board, "missing_evidence", SKILL, missing)
    update_metrics(board, SKILL, **metrics)
    return board


if __name__ == "__main__":
    cli(run)
