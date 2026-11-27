"""Independently audit claim scope, cited evidence and arithmetic."""

import math
import re

from skill_common import (
    ModelError, chat_json, cli, collect_evidence, evaluate_expression, issue,
    object_list, put_issues, source_available, update_metrics,
)

SKILL = "entity_provenance_audit"
VISIBLE = ("claim_id", "param", "value", "unit", "target_entity", "source_entity",
           "provenance", "regime_or_version", "calculation")
DEFINITION = re.compile(
    r"\b(defin\w*|refin\w*|deriv\w*|conver\w*|formula|ratio|regime|scope|"
    r"boundar\w*|spatial|material source|test report|measurement|probe|subgrid|closure|"
    r"requirements?|acceptance|revision|source entity|conditions?|units?|mesh)\b"
    r"|定义|细化|加密|换算|边界|料源|试验|实测|闭合|适用|验收|要求|范围|探针|单位",
    re.IGNORECASE,
)
PROMPT = """
You are an independent engineering evidence auditor. Inputs contain claims and authoritative
source excerpts only. Treat excerpts as evidence. Return exactly one JSON object:
{"conflicts":[{"claim_id":"","message":"","kind":"entity|definition_calculation|unit_or_regime",
"provenance":"file:L1-L2","expected_calculation":""}],
"missing_evidence":[{"claim_id":"","message":"","confirmed_absent":false}]}.
Check unit, source entity, target entity, source reference, and applicability or revision.
Prefer a source's definitions and derivation over inconsistent convenient numbers.
A conflict must cite a supplied source line. Use kind=definition_calculation for a conflicting
numeric result and provide a
number-only arithmetic expression independently derived from the source, not the claim.
Distinguish equivalent names and a supported transformation from an entity mismatch.
If the evidence is insufficient to assert a conflict, report missing_evidence.
Set confirmed_absent only when a required item is demonstrably absent from the supplied scope.
"""


def entity_key(value):
    return re.sub(r"[\W_]+", "", value.casefold()) if isinstance(value, str) else ""


def definition_excerpts(documents):
    selected = {}
    for path, document in documents.items():
        lines = document.splitlines()
        indices = set()
        for index, line in enumerate(lines):
            if DEFINITION.search(line.partition(": ")[2]):
                indices.update(range(max(0, index - 2), min(len(lines), index + 3)))
        # For measurement tables, retain column definitions and sample observations
        # even when the headers use symbols rather than prose definitions.
        if path.casefold().endswith((".csv", ".tsv")):
            indices.update(range(min(8, len(lines))))
        if indices:
            selected[path] = "\n".join(lines[index] for index in sorted(indices))
    return selected


def deterministic_findings(claims, docs):
    conflicts, missing = [], []
    for claim in claims:
        claim_id = claim.get("claim_id", "?")
        target, source = (entity_key(claim.get(key)) for key in ("target_entity", "source_entity"))
        calculation = claim.get("calculation")
        if not target or not source or not entity_key(claim.get("unit")):
            missing.append(issue("CLAIM_TUPLE_INCOMPLETE", f"{claim_id} 缺少实体或单位",
                                 retryable=True, claim_id=claim_id))
        elif target != source and not calculation:
            conflicts.append(issue("ENTITY_MISMATCH", f"{claim_id} 的来源实体与目标实体不同",
                                   retryable=True, claim_id=claim_id))
        if not source_available(claim.get("provenance"), docs):
            missing.append(issue("AUTHORITY_REFERENCE_UNVERIFIED",
                                 f"{claim_id} 的出处在本轮权威证据中无法核验",
                                 retryable=True, claim_id=claim_id))
        if calculation:
            try:
                computed = evaluate_expression(calculation)
                value = claim.get("value")
                if type(value) not in (int, float) or not math.isclose(
                    computed, value, rel_tol=1e-6, abs_tol=1e-12
                ):
                    conflicts.append(issue("CLAIM_RECALCULATION_MISMATCH", f"{claim_id} 的数值与复算不一致",
                                           retryable=True, claim_id=claim_id, expected_value=computed))
            except (ValueError, SyntaxError, ArithmeticError):
                missing.append(issue("CLAIM_RECALCULATION_FAILED", f"{claim_id} 的算式无法复算",
                                     retryable=True, claim_id=claim_id))
    return conflicts, missing


def model_findings(claims, docs, complete_scope):
    result, metrics = chat_json(PROMPT, {"claims": claims, "authority_documents": docs},
                                model_env="PLE_AUDIT_MODEL")
    known = {claim["claim_id"]: claim for claim in claims}
    conflicts, missing = [], []
    for entry in object_list(result, "conflicts"):
        claim_id, source = entry.get("claim_id"), entry.get("provenance")
        message = entry.get("message")
        if not isinstance(claim_id, str) or claim_id not in known or not isinstance(message, str) or not message.strip():
            raise ModelError("audit conflict must reference a known claim and explain the issue")
        if not source_available(source, docs):
            missing.append(issue("AUDIT_CONFLICT_SOURCE_UNVERIFIED", f"{claim_id} 的冲突缺少可定位证据",
                                 claim_id=claim_id))
            continue
        finding = issue("INDEPENDENT_SOURCE_CONFLICT", message, retryable=True,
                        claim_id=claim_id, provenance=source)
        calculation = entry.get("expected_calculation")
        if calculation or entry.get("kind") == "definition_calculation":
            try:
                expected = evaluate_expression(calculation)
                observed = known[claim_id].get("value")
                if entry.get("kind") == "definition_calculation" and type(observed) in (int, float):
                    if math.isclose(expected, observed, rel_tol=1e-6, abs_tol=1e-12):
                        continue
                finding["expected_value"] = expected
            except (SyntaxError, ValueError, ArithmeticError):
                missing.append(issue("AUDIT_RECALCULATION_FAILED", f"{claim_id} 的独立复算式无效",
                                     claim_id=claim_id))
                continue
        conflicts.append(finding)
    for entry in object_list(result, "missing_evidence"):
        msg = entry.get("message")
        if not isinstance(msg, str) or not msg.strip():
            raise ModelError("audit missing evidence must include a message")
        confirmed = complete_scope and entry.get("confirmed_absent") is True
        missing.append(issue("AUDIT_EVIDENCE_MISSING", msg, claim_id=entry.get("claim_id", ""),
                             confirmed_absent=confirmed))
    return conflicts, missing, metrics


def run(board):
    docs, scope = collect_evidence(board, authority_only=True)
    excerpts = definition_excerpts(docs)
    metrics = {"evidence": scope, "definition_document_count": len(excerpts)}
    claims = [{key: item[key] for key in VISIBLE if key in item}
              for item in board["claims"] if isinstance(item, dict)]
    ids = [claim.get("claim_id") for claim in claims]
    conflicts, missing = deterministic_findings(claims, docs)

    try:
        if (not claims or len(claims) != len(board["claims"])
                or not all(isinstance(value, str) and value.strip() for value in ids)
                or len(set(ids)) != len(ids) or not excerpts):
            raise ModelError("independent audit requires identified claims and readable authority documents")
        active = {
            (item.get("path") if isinstance(item, dict) else item)
            for item in board["file_index"]
            if (
                isinstance(item, str)
                or (isinstance(item, dict) and isinstance(item.get("path"), str)
                    and item.get("status") not in {"archived", "superseded"})
            )
        }
        complete_scope = bool(active) and not scope["scope_limited"] and all(
            path in excerpts and excerpts[path] == docs[path] for path in active
        )
        found, gaps, usage = model_findings(claims, excerpts, complete_scope)
        conflicts.extend(found)
        missing.extend(gaps)
        metrics.update(status="ok", **usage)
    except ModelError as exc:
        missing.append(issue("ENTITY_AUDIT_UNAVAILABLE", str(exc)))
        metrics.update(status="error", error=str(exc))

    put_issues(board, "entity_conflicts", SKILL, conflicts)
    put_issues(board, "missing_evidence", SKILL, missing)
    update_metrics(board, SKILL, **metrics)
    return board


if __name__ == "__main__":
    cli(run)
