"""Retrieve bounded, line-addressable evidence for the current repair targets."""
import json
from collections import defaultdict
from itertools import islice
from pathlib import Path

from skill_common import MAX_FILE_BYTES, _source_lines, cli, search_terms, task_workspace, update_metrics

SKILL = "targeted_evidence_lookup"
MAX_DOCUMENTS = 32
MAX_LINES = 6000
MAX_TARGETS = 12


def run(board):
    raw = board["retry_feedback"]
    feedback = json.loads(raw) if raw else {}
    claims = {c["claim_id"]: c for c in board["claims"] if isinstance(c, dict) and c.get("claim_id")}
    messages = defaultdict(list)
    for finding in feedback.get("findings", []):
        if finding.get("retryable") is True and finding.get("claim_id") in claims:
            messages[finding["claim_id"]].append(str(finding.get("message", "")))
    ids = list(dict.fromkeys(feedback.get("repair_claim_ids", list(messages))))
    requested = [cid for cid in ids if cid in claims]
    queries = {}
    for cid in requested[:MAX_TARGETS]:
        claim = claims[cid]
        subject = search_terms(" ".join(str(claim.get(k, "")) for k in ("param", "target_entity")))
        terms = search_terms(" ".join(messages[cid]) + " " + str(claim.get("regime_or_version", "")))
        queries[cid] = (subject, terms)

    hits = {cid: [] for cid in queries}
    errors = []
    scanned = []
    if queries:
        root = task_workspace(board)
        active, excluded = set(), set()
        for entry in board["file_index"]:
            name = entry.get("path") if isinstance(entry, dict) else entry
            if isinstance(name, str):
                excluded_entry = isinstance(entry, dict) and entry.get("status") in {"archived", "superseded"}
                (excluded if excluded_entry else active).add(name)
        authority = {p for p in board["authority_docs"] if isinstance(p, str)}
        cited = {str(claims[cid].get("provenance", "")).rpartition(":")[0] for cid in queries}
        subject_terms = set().union(*(s for s, _ in queries.values()))
        names = sorted((active | authority) - excluded, key=lambda name: (
            name not in cited, -len(search_terms(name) & subject_terms), name not in authority, name))
        for name in names[:MAX_DOCUMENTS]:
            try:
                path = (root / name).resolve(strict=True)
                if Path(name).anchor or not path.is_relative_to(root) or not path.is_file():
                    raise ValueError("path outside task or not a file")
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError("file exceeds size budget")
                lines = [line[:1600] for line in islice(_source_lines(path), MAX_LINES)]
                scanned.append(name)
            except Exception as exc:
                errors.append({"path": name, "error": str(exc)})
                continue
            for index in range(0, len(lines), 4):
                window = lines[index:index + 4]
                terms = search_terms(" ".join(window))
                for cid, (subject, context) in queries.items():
                    if not terms & subject:
                        continue
                    score = 3 * len(terms & subject) + len(terms & context)
                    snippets = hits[cid]
                    snippets.append({"score": score, "path": name, "start_line": index + 1,
                                     "end_line": index + len(window),
                                     "excerpt": "\n".join(f"L{i}: {s}" for i, s in enumerate(window, index + 1))})
                    snippets.sort(key=lambda h: (-h["score"], h["path"], h["start_line"]))
                    del snippets[3:]
    board["targeted_evidence"] = hits
    update_metrics(board, SKILL, read_paths=scanned, read_errors=errors,
                   unsearched_targets=requested[MAX_TARGETS:], no_hits=[c for c in hits if not hits[c]],
                   candidate_documents=len(names) if queries else 0)
    return board


if __name__ == "__main__":
    cli(run)
