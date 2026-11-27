"""Check explicitly scoped physical derivations against cited operand values."""
import math
import re

from skill_common import ANCHOR, cli, collect_evidence, issue, put_issues, source_available, update_metrics

SKILL = "physical_recalculation"
UNITS = {"mm": ("length", .001), "cm": ("length", .01), "m": ("length", 1),
         "km": ("length", 1000), "1": ("dimensionless", 1)}
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"


def numeric(claim):
    value = claim.get("value")
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("a finite numeric claim value is required")
    return value


def scoped(claim, entity, regime):
    if claim.get("target_entity") != entity or claim.get("regime_or_version") != regime:
        raise ValueError("claim entity or applicability differs from the declared check")


def read_operand(claim, docs, dimension, entity, regime):
    scoped(claim, entity, regime)
    if claim.get("source_entity") != entity:
        raise ValueError("source entity requires a separately evidenced transformation")
    unit = claim.get("unit")
    if unit not in UNITS or UNITS[unit][0] != dimension:
        raise ValueError("operand unit has unsupported dimension")
    ref = claim.get("provenance")
    if not source_available(ref, docs):
        raise ValueError("operand citation unavailable")
    path, _, anchor = ref.strip().replace(chr(92), "/").rpartition(":")
    span = ANCHOR.fullmatch(anchor.strip())
    if not span:
        raise ValueError("operand citation must specify a line range")
    low, high = int(span[1]), int(span[2] or span[1])
    passage = []
    for line in docs[path].splitlines():
        match = re.match(r"^L(\d+): (.*)", line)
        if match and low <= int(match[1]) <= high:
            passage.append(match[2])
    excerpt = "\n".join(passage)
    if not all(re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", excerpt, re.I) for v in (entity, regime)):
        raise ValueError("cited lines do not establish operand scope")
    param = claim.get("param")
    if not isinstance(param, str) or not param.strip():
        raise ValueError("operand parameter name missing")
    suffix = r"(?:[ \t]+1)?" if unit == "1" else r"[ \t]*" + re.escape(unit)
    suffix += r"[ \t]*(?=$|[;,|\n])"
    pattern = r"(?<!\w)" + re.escape(param) + r"[ \t]*[:=|][ \t]*(" + NUMBER + ")" + suffix
    values = {float(m) for m in re.findall(pattern, excerpt)}
    value = numeric(claim)
    if values != {value}:
        raise ValueError("citation does not uniquely bind the parameter to its value and unit")
    return value * UNITS[unit][1]


def calculate(check, claims, docs):
    entity, regime = check.get("entity"), check.get("regime_or_version")
    if not all(isinstance(s, str) and s.strip() for s in (entity, regime)):
        raise ValueError("declare the entity and applicability of the check")
    result = claims[check["claim_id"]]
    scoped(result, entity, regime)
    operation = check.get("operation")
    if operation not in ("length_ratio", "binary_refinement"):
        raise ValueError("unsupported operation")
    keys = ("numerator", "denominator") if operation == "length_ratio" else ("base", "level")
    operand_ids = [check[k] for k in keys]
    if check["claim_id"] in operand_ids:
        raise ValueError("result cannot serve as its own evidence")
    left = read_operand(claims[operand_ids[0]], docs, "length", entity, regime)
    if left <= 0:
        raise ValueError("length must be positive")
    if operation == "length_ratio":
        right = read_operand(claims[operand_ids[1]], docs, "length", entity, regime)
        if right <= 0 or result.get("unit") != "1":
            raise ValueError("length ratio requires a positive divisor and a dimensionless result")
        expected = left / right
    else:
        level = read_operand(claims[operand_ids[1]], docs, "dimensionless", entity, regime)
        if not level.is_integer() or not 0 <= level <= 60:
            raise ValueError("binary refinement requires an integer level between 0 and 60")
        unit = result.get("unit")
        if unit not in UNITS or UNITS[unit][0] != "length":
            raise ValueError("result must use a supported length unit")
        expected = left / (2 ** int(level)) / UNITS[unit][1]
    if not math.isfinite(expected):
        raise ValueError("non-finite derived value")
    observed = numeric(result)
    return {"status": "consistent" if math.isclose(expected, observed, rel_tol=1e-6, abs_tol=1e-12)
            else "mismatch", "expected_value": expected, "observed_value": observed, "unit": result["unit"],
            "operand_ids": operand_ids, "sources": [claims[i]["provenance"] for i in operand_ids]}


def run(board):
    checks = board.get("physical_checks", [])
    if not isinstance(checks, list):
        raise ValueError("physical_checks must be a list")
    docs = collect_evidence(board, authority_only=True)[0] if checks else {}
    claims = {c["claim_id"]: c for c in board["claims"] if isinstance(c, dict) and c.get("claim_id")}
    rows, conflicts, missing = [], [], []
    for check in checks:
        cid = check.get("claim_id") if isinstance(check, dict) else None
        try:
            if not isinstance(check, dict):
                raise ValueError("check must be an object")
            row = calculate(check, claims, docs)
            if row["status"] == "mismatch":
                conflicts.append(issue("PHYSICAL_VALUE_MISMATCH", f"{cid}: expected {row['expected_value']} {row['unit']}",
                                       retryable=True, claim_id=cid, expected_value=row["expected_value"]))
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            row = {"status": "unverified", "reason": str(exc)}
            missing.append(issue("PHYSICAL_CHECK_UNVERIFIED", str(exc), claim_id=cid,
                                 retryable=isinstance(cid, str) and cid in claims))
        rows.append(dict(row, claim_id=cid))
    board["physical_check_results"] = rows
    put_issues(board, "entity_conflicts", SKILL, conflicts)
    put_issues(board, "missing_evidence", SKILL, missing)
    update_metrics(board, SKILL, status="checked" if rows else "no_checks_requested", checks=len(rows))
    return board


if __name__ == "__main__":
    cli(run)
