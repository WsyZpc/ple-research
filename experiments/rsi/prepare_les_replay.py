"""Prepare and validate an existing RSI Word note for local PLE artifact replay."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile


TASK = "les-mesh-resolution"
FILENAME = "CFDME-2025-041_resolution_note_revA.docx"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", type=Path, required=True)
    parser.add_argument("--entry", type=Path, required=True)
    parser.add_argument("--kit", type=Path, default=Path.home() / "ple_harness/ple")
    args = parser.parse_args()
    src = args.docx.resolve(strict=True)
    with zipfile.ZipFile(src) as package:
        if "word/document.xml" not in package.namelist() or package.testzip():
            parser.error("input must be an intact Word document")
    sys.path.insert(0, str(args.kit.resolve(strict=True)))
    from kit import artifacts, export, spec

    entry = args.entry.resolve()
    entry.parent.mkdir(parents=True, exist_ok=True)
    if entry.exists():
        parser.error("choose a new entry directory; the requested one already exists")
    target = Path("filesystem") / FILENAME
    with tempfile.TemporaryDirectory(dir=entry.parent) as tmp:
        stage = Path(tmp) / "entry"
        task = stage / "artifacts" / TASK
        copy = task / "files" / target
        copy.parent.mkdir(parents=True)
        shutil.copyfile(src, copy)
        (stage / "submission.yaml").write_text(
            "# Local artifact replay only. No agent server is launched.\n"
            "name: rsi-les-replay\n"
            "model_api: openai-compatible/qwen3.5-plus\n"
            "model_base_url: https://uniapi.thingo.com.cn/v1\n"
            "serve: /bin/false\n",
            encoding="utf-8",
        )
        digest = artifacts.dev_set_digest(args.kit / "eval/dev_set.yaml")
        manifest = {
            "format": artifacts.FORMAT,
            "created": datetime.now(timezone.utc).isoformat(),
            "dev_set": digest,
            "harness": {"name": "rsi-les-replay"},
            "tasks": {TASK: {"dev_set": digest, "files": {
                target.as_posix(): artifacts.file_blob_id(copy)
            }, "deleted": [], "skipped": []}},
        }
        export.write_manifest(stage / "artifacts", manifest)
        spec.load(stage)
        dev = artifacts.load_dev_set(args.kit / "eval/dev_set.yaml")
        review = artifacts.review_directory(stage, dev)
        if not review.accepted or review.tasks[TASK].status != artifacts.OK:
            raise SystemExit("\n".join(review.lines()))
        replay = Path(tmp) / "check"
        artifacts.materialize(review, dev, lambda name: (stage / name).open("rb"), replay, only=[TASK])
        if review.tasks[TASK].status != artifacts.OK:
            raise SystemExit("\n".join(review.lines()))
        recovered = replay / TASK / "files" / target
        checksum = sha256(src)
        if sha256(recovered) != checksum:
            raise SystemExit("replayed Word file differs from the source")
        stage.rename(entry)
    print(f"Entry: {entry}\nTarget: /{target.as_posix()}\nSHA-256: {checksum}")
    print("PLE package review and offline replay file check passed.")


if __name__ == "__main__":
    main()
