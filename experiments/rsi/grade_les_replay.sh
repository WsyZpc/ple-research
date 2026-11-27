#!/usr/bin/env bash
# Run in Ubuntu. The only positional argument is a prepared PLE replay entry.
set -euo pipefail
entry=$(realpath "${1:?Usage: bash grade_les_replay.sh /path/to/prepared-entry}")
[[ -f "$entry/submission.yaml" ]] || { echo "Missing submission.yaml in $entry" >&2; exit 1; }
cd "$HOME/ple_harness/ple"
export PATH="$HOME/.local/bin:$PATH"
docker info --format 'Docker {{.ServerVersion}}' || exit 1
export JUDGE_BASE_URL="https://uniapi.thingo.com.cn/v1"
export JUDGE_MODEL="qwen3.5-plus"
if [[ -z ${JUDGE_API_KEY:-} ]]; then
    read -r -s -p 'Judge API key (hidden): ' JUDGE_API_KEY
    printf '\n'
fi
[[ -n $JUDGE_API_KEY ]] || { echo 'Judge key is empty' >&2; exit 1; }
export JUDGE_API_KEY
out=$(mktemp -d "$HOME/ple-rsi-replays/grade-les-XXXXXXXX")
echo "Run directory: $out"
.venv/bin/python eval/run.py --artifacts "$entry" --tasks les-mesh-resolution \
    --tasks-dir "$HOME/ple_harness/data/tasks" --attempts 1 --out "$out"
.venv/bin/python - "$out" "$entry" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

out, entry = map(Path, sys.argv[1:])
grades = list(out.glob("attempt*/jobs/*/*/verifier/grade.json"))
if len(grades) != 1:
    raise SystemExit(f"No unique LES grade. Inspect the verifier/grade.log under {out}")
path = grades[0]
name = "CFDME-2025-041_resolution_note_revA.docx"
original = entry / "artifacts/les-mesh-resolution/files/filesystem" / name
submitted = path.parent / "submission" / name
if hashlib.sha256(original.read_bytes()).digest() != hashlib.sha256(submitted.read_bytes()).digest():
    raise SystemExit("The graded document differs from the replay entry")
grade = json.loads(path.read_text())
print("Grade:", path)
print("Points:", grade["weighted_points"], "/", grade["possible_weighted_points"])
print("Reward:", grade["reward"])
PY
