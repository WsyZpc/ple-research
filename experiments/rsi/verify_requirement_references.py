import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "rsi-flow-spring-boot/core-flow/src/main/resources/skills"))
import requirement_extraction as extraction
from skill_common import TransportError, merge_defaults

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    (root / "task/records").mkdir(parents=True)
    (root / "task/records/report.txt").write_text("Section A\nReview applies\nTest basis required\n", encoding="utf-8")
    os.environ["PLE_TASK_ROOT"] = str(root)
    original_corpus = {"records/report.txt": "L1: Section A\nL3: Test basis required"}
    extraction.collect_evidence = lambda *_args, **_kwargs: (dict(original_corpus), {})
    base = {"id": "source", "description": "Check test basis", "applies_when": "For the test",
            "acceptance": "Verify whether the test basis is established", "provenance": "report.txt: L1 – L3"}
    invalid = dict(base, id="repair", provenance="records/report.txt:L99")
    assert extraction.canonical_reference("report.txt:L2", {**original_corpus, "other/report.txt": "L2: Other"}) == "report.txt:L2"
    assert extraction.canonical_reference(base["provenance"], original_corpus) == "records/report.txt:L1-L3"

    def run(mode, items, repair=None):
        calls = []
        def chat(prompt, payload, **settings):
            if prompt == extraction.PROMPT:
                calls.append("initial")
                return {"required_checks": deepcopy(items)}, {"total_tokens": 2}
            calls.append("repair")
            assert settings["timeout_seconds"] == 30
            assert [item["id"] for item in payload["unresolved_checks"]] == ["repair"]
            if repair == "transport":
                raise TransportError("local test timeout")
            return {"references": [] if repair is None else [
                {"id": "source", "provenance": "made-up.txt:L1"},
                {"id": "repair", "provenance": repair},
            ]}, {"total_tokens": 3}
        extraction.chat_json = chat
        spec = {"checklist_mode": mode, "required_checks": items}
        return extraction.run(merge_defaults({
            "task_dir": "task", "instruction": "Review test basis.", "expected_schema": spec,
        })), calls

    board, calls = run("auto", [base, invalid], "report.txt:L3")
    assert calls == ["initial", "repair"]
    assert [check["provenance"] for check in board["required_checks"]] == ["records/report.txt:L1-L3", "records/report.txt:L3"]
    assert board["checks_ready"] and not board["missing_evidence"]
    assert board["trace_metrics"]["requirement_extraction"]["total_tokens"] == 5

    for response in (None, "transport", "report.txt:L99"):
        board, calls = run("auto", [base, invalid], response)
        assert board["checks_ready"] and [check["id"] for check in board["required_checks"]] == ["source"]
        assert board["missing_evidence"][0]["code"] == "REQUIRED_CHECK_SOURCE_UNVERIFIED"
        assert board["unresolved_required_checks"][0]["id"] == "repair"
        assert board["trace_metrics"]["requirement_extraction"]["status"] == "partial"

    board, calls = run("manual", [base, invalid])
    assert not calls and board["route_status"] == "EVIDENCE_HOLD" and not board["checks_ready"]
    board, calls = run("auto", [invalid])
    assert board["route_status"] == "EVIDENCE_HOLD" and not board["checks_ready"]

print("Verified recovery of omitted source lines, repair of wrong anchors, partial retention, ambiguity, and manual isolation.")
