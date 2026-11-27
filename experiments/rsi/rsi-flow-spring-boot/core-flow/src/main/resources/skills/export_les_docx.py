"""Write the LES review note to an isolated PLE submission directory."""
import json
import os
import tempfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from skill_common import cli, schema_spec, submission_root, update_metrics

TASK = "les-mesh-resolution"
FILENAME = "CFDME-2025-041_resolution_note_revA.docx"
HOLD = "Keep the resolution-basis item open pending evidence review."


def add_draft(doc, draft):
    for line in draft.splitlines():
        line = line.strip()
        if line.startswith(("# ", "## ", "### ")):
            doc.add_heading(line.lstrip("# "), level=2)
        elif line.startswith(("- ", "* ")):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif line:
            doc.add_paragraph(line)


def run(board):
    parts = Path(board["task_dir"].replace("\\", "/")).parts
    if parts not in {(TASK,), (TASK, "environment", "files")}:
        raise ValueError("LES review export requires the LES task directory")
    spec = dict(schema_spec(board["expected_schema"]))
    if str(spec.get("format", "docx")).lower().lstrip(".") != "docx":
        raise ValueError("LES review export requires DOCX")
    status = board["route_status"]
    if status not in {"PASS", "EVIDENCE_HOLD", "MAX_RETRY_REACHED"}:
        raise ValueError("review must finish before export")
    draft = board["draft_output"].strip()
    if not draft:
        raise ValueError("review has no draft to export")

    doc = Document()
    doc.core_properties.title = "Ocotillo LES resolution review"
    doc.core_properties.author = "RSI engineering review"
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    border = doc.styles["Title"].element.find(".//" + qn("w:pBdr"))
    if border is not None:
        border.getparent().remove(border)
    title = doc.add_paragraph(style="Title")
    title.add_run("Ocotillo LES resolution review").font.color.rgb = RGBColor(0, 0, 0)
    doc.add_paragraph("CFDME-2025-041   |   Phase 1 revision B   |   Review note A")
    if status == "EVIDENCE_HOLD":
        spec.setdefault("hold_statement", HOLD)
        if not isinstance(spec["hold_statement"], str) or not spec["hold_statement"].strip():
            raise ValueError("expected_schema.hold_statement must contain text")
        doc.add_paragraph(spec["hold_statement"])
    elif status == "MAX_RETRY_REACHED":
        doc.add_paragraph("Review limit reached. Outstanding findings require a decision before closure.")
    doc.add_heading("Review findings", level=1)
    add_draft(doc, draft)
    # The hold draft lists missing evidence, but may omit conflicts and coverage findings.
    if status != "PASS" and board["retry_feedback"]:
        findings = json.loads(board["retry_feedback"]).get("findings", [])
        extra = dict.fromkeys(f["message"].strip() for f in findings
                              if isinstance(f.get("message"), str) and f["message"].strip()
                              and f["message"].strip() not in draft)
        if extra:
            doc.add_heading("Outstanding review items", level=1)
            for message in extra:
                doc.add_paragraph(message, style="List Bullet")

    parent = submission_root() / TASK
    parent.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
    workspace = run_dir / "filesystem"
    workspace.mkdir()
    path = workspace / FILENAME
    pending = workspace / ".review.tmp"
    try:
        doc.save(pending)
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)
    board["expected_schema"] = spec
    board["artifact_path"] = str(path)
    update_metrics(board, "docx_export", status="ok", bytes=path.stat().st_size)
    return board


if __name__ == "__main__":
    cli(run)
