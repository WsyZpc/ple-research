"""Fill the original materials acceptance template for the PLE fill task."""
import re
from pathlib import Path
from tempfile import mkdtemp

from docx import Document

from skill_common import cli, issue, put_issues, schema_spec, submission_root, task_workspace, update_metrics

TASK = "fill-compaction-acceptance"
FILENAME = "Thelbridge_Materials_Acceptance_Fill_Compaction_2026-0708.docx"
TEMPLATE = Path("environment/tools/files/ce01-slab-on-grade-fill-compaction-acceptance-3d2c133e/"
                "Thelbridge_Materials_Acceptance_Record_TEMPLATE.docx")
HOLD = "Item 054 remains open pending resolution of the findings below."
SECTIONS = {
    "PURPOSE": "State the verification register item this record closes and what is being determined.",
    "DOCUMENTS REVIEWED": "List each document relied on by title and date.",
    "BASIS OF REVIEW": "Cite the governing specification articles by number and state the basis of acceptance applied.",
    "FINDINGS": "Number each finding. Each finding cites the document and page it rests on.",
    "CONCLUSION AND RECOMMENDATION": "State the determination using ACCEPTED or REJECTED and the action required.",
}


def split_draft(draft):
    headings = "|".join(re.escape(section) for section in SECTIONS)
    pattern = rf"^\s*(?:#{{1,6}}\s*)?(?:[1-5][.)]\s*)?\*{{0,2}}({headings})\*{{0,2}}\s*:?[ \t]*$"
    parts = re.split(pattern, draft, flags=re.MULTILINE | re.IGNORECASE)
    return {heading.upper(): body.strip() for heading, body in zip(parts[1::2], parts[2::2])}


def run(board):
    if board["task_dir"] != TASK or board["route_status"] not in {"PASS", "EVIDENCE_HOLD", "MAX_RETRY_REACHED"}:
        raise ValueError("fill compaction export requires a completed fill task review")
    workspace = task_workspace(board)
    template = (workspace / TEMPLATE).resolve(strict=True)
    if not template.is_relative_to(workspace):
        raise ValueError("template must be inside the task workspace")
    spec = dict(schema_spec(board["expected_schema"]))
    if spec.get("format", "docx").casefold().lstrip(".") != "docx":
        raise ValueError("fill compaction export requires DOCX")
    spec["format"] = "docx"

    draft = board["draft_output"].strip()
    candidate = board.get("fill_candidate_draft", draft)
    sections = split_draft(candidate)
    blockers = []
    if board["route_status"] == "PASS" and (
            not all(sections.get(key) for key in SECTIONS)
            or not re.match(r"^(?:ACCEPTED|REJECTED)\b", sections["CONCLUSION AND RECOMMENDATION"], re.I)):
        blockers.append(issue("FILL_RECORD_INCOMPLETE", "验收记录缺少模板栏目或明确结论。"))
        board["route_status"] = "EVIDENCE_HOLD"
    if board["route_status"] != "PASS":
        spec["hold_statement"] = HOLD
        sections["CONCLUSION AND RECOMMENDATION"] = HOLD
        findings = sections.get("FINDINGS") or candidate
        sections["FINDINGS"] = "\n\n".join(part for part in (
            "Provisional findings for review:\n" + findings if findings else "",
            draft if draft and draft != candidate else "",
        ) if part) or "No review findings are available yet."
    sections.setdefault("PURPOSE", "Review the slab-on-grade fill compaction testing for verification register Item 054.")
    sections.setdefault("DOCUMENTS REVIEWED", "Review record pending confirmation.")
    sections.setdefault("BASIS OF REVIEW", "Specification Section 31 20 00, Earth Moving. Acceptance basis pending confirmation.")
    put_issues(board, "missing_evidence", "fill_docx_export", blockers)

    doc = Document(template)
    placeholders = {p.text.strip(): p for p in doc.paragraphs if p.text.strip()}
    for section, placeholder in SECTIONS.items():
        if placeholder not in placeholders:
            raise ValueError(f"template placeholder missing for {section}")
        placeholders[placeholder].text = sections[section]
    placeholders["Subject:"].text = "Subject: Birchwood Village Expansion, Package A — fill compaction, Item 054"
    parent = submission_root() / TASK
    parent.mkdir(parents=True, exist_ok=True)
    run_dir = Path(mkdtemp(prefix="run-", dir=parent))
    output = run_dir / "filesystem"
    output.mkdir()
    path = output / FILENAME
    temporary = run_dir / ".review.tmp"
    try:
        doc.save(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    board["expected_schema"] = spec
    board["artifact_path"] = str(path)
    update_metrics(board, "docx_export", status="ok", bytes=path.stat().st_size)
    return board


if __name__ == "__main__":
    cli(run)
