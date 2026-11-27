"""Review the L-4 resubmittal against the original Phase 3 records."""

import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from skill_common import _source_lines, cli, issue, put_issues, schema_spec, submission_root, task_workspace, update_metrics

TASK = "landscape-sheet-revision"
MATERIALS = TASK + "/environment/filesystem"
APPROVAL = "Correspondence/Agency/TM-22-500041_Conditions_of_Approval_03142022.pdf"
TRACKER = "Correspondence/DSR_Ph3_Resubmittal_Tracker.xlsx"
PLAN = "Design-Drafting/Landscape/DSR_Ph3_Landscape_L1-L4.pdf"
HOA = "Tenders-Contracts/DSR_CCRs_CommonArea_Exhibit.pdf"
CALENDAR = "Meeting Notes/EnterpriseTAB_Calendar_Agenda.pdf"
FILENAME = "Memo_to_Callaway_L4_Revision.docx"


def find(path, lines, pattern, *, after=0, count=1):
    for i, line in enumerate(lines):
        if i >= after and re.search(pattern, line, re.I):
            text = " ".join(s.strip() for s in lines[i:i + count])
            return text, f"{path}:L{i + 1}-L{i + count}", i
    raise ValueError(f"Expected passage unavailable in {path}: {pattern}")


def review(board):
    workspace = task_workspace(board)
    if board["task_dir"].replace(chr(92), "/") != MATERIALS:
        raise ValueError(f"landscape review requires {MATERIALS}")
    evidence, findings = {}, []
    try:
        available = {row["path"] for row in board["file_index"] if row.get("status") == "active"}
        docs = {}
        for name in (APPROVAL, TRACKER, PLAN, HOA, CALENDAR):
            path = (workspace / name).resolve(strict=True)
            if name not in available or not path.is_relative_to(workspace):
                raise ValueError(f"Required current record unavailable: {name}")
            docs[name] = list(_source_lines(path))

        def cite(key, name, pattern, **options):
            quote, ref, index = find(name, docs[name], pattern, **options)
            evidence[key] = {"reference": ref, "text": quote}
            return quote, index

        _, section = cite("condition_section", APPROVAL, r"Conditions 14 through 20")
        condition, index = cite("condition_14", APPROVAL, r"^Any significant change to approved plans", after=section, count=3)
        if index != section + 1 or not all(word in condition.lower() for word in
                ("common areas", "town advisory board", "planning commission", "prior to staff-level action")):
            raise ValueError("The first clause under Conditions 14 through 20 does not establish the expected review sequence")
        approval_date, _ = cite("approval_date", APPROVAL, r"^March 14, 2022$")
        ownership, _ = cite("common_area", HOA, r"Section 2\.17.*Streetscape Common Area", count=6)
        if "owned by the association" not in ownership.lower() or "street trees" not in ownership.lower():
            raise ValueError("The CC&Rs excerpt does not link street trees to association-owned common area")

        row, _ = cite("l4_open", TRACKER, r"\| L-4 \|", count=1)
        for index in range(len(docs[PLAN]) - 7):
            total_line = " ".join(docs[PLAN][index:index+7])
            if re.search(r"^Total\s+Phase\s+3\s+street\s+fronta\s*ge\s+[\d,]+ lf \d+", total_line, re.I):
                break
        else:
            raise ValueError("Phase 3 frontage total not found on the current landscape plan")
        plan, _ = cite("plan_count", PLAN, r"^[\d,]+ lf \d+\s*$", after=index)
        totals = re.search(r"([\d,]+) lf (\d+)", plan)
        criteria = re.search(r"1 tree per (\d+) lf.*?([\d,]+) lf frontage, (\d+) required against (\d+) shown", row)
        if not criteria or not totals:
            raise ValueError("The tracker and current plan do not give comparable tree counts")
        spacing, frontage, required, shown = [int(s.replace(",", "")) for s in criteria.groups()]
        if spacing <= 0 or (frontage, shown) != (int(totals[1].replace(",", "")), int(totals[2])) or required != -(-frontage // spacing):
            raise ValueError("The current plan and tracker disagree on frontage or tree count")
        cite("seal", TRACKER, r"sealed by landscape architect of record")
        cite("planning_coordination", TRACKER, r"decision on whether landscape resubmittal", count=1)
        target_row, _ = cite("target", TRACKER, r"^\d+/\d+/\d+ \| Phase 3 resubmittal target")
        lead, _ = cite("filing_window", CALENDAR, r"no later than \d+ days prior to the meeting date", count=2)
        cite("board_authority", CALENDAR, r"^TAB recommendations are advisory", count=5)
        date = lambda text: datetime.strptime(text, "%m/%d/%Y").date()
        date_text = re.search(r"dated (\d+/\d+/\d{4})", board["instruction"], re.I)
        if not date_text:
            raise ValueError("Memo date absent from the task instruction")
        memo_date = date(date_text[1])
        target = date(target_row.split(" | ",1)[0])
        window = int(re.search(r"no later than (\d+) days", lead)[1])
        meetings = []
        for i, line in enumerate(docs[CALENDAR], 1):
            if re.match(r"^\d+ \d{2}/\d{2}/\d{4} Wednesday", line):
                day, _, cutoff = map(date, re.findall(r"\d{2}/\d{2}/\d{4}", line))
                meetings.append((day, cutoff, i))
        upcoming = min(m for m in meetings if m[0] >= memo_date)
        available_meeting = min(m for m in meetings if m[1] >= memo_date)
        for key, meeting in (("november_meeting", upcoming), ("available_meeting", available_meeting)):
            day, cutoff, line = meeting
            if (day - cutoff).days != window:
                raise ValueError("The meeting table disagrees with the filing window")
            evidence[key] = {"reference": f"{CALENDAR}:L{line}", "text": docs[CALENDAR][line-1]}
        findings.append(issue("WRITTEN_PLANNING_DECISION_PENDING",
                              "The reviewed records do not establish a written significant-change determination for this revision."))
        board["landscape_summary"] = dict(memo_date=memo_date.isoformat(), target=target.isoformat(),
            approval_date=approval_date, frontage=frontage, spacing=spacing, required=required, shown=shown,
            lead_days=window, meeting=upcoming[0].isoformat(), cutoff=upcoming[1].isoformat(),
            next_meeting=available_meeting[0].isoformat(), next_cutoff=available_meeting[1].isoformat())
    except (OSError, ValueError) as exc:
        findings.append(issue("LANDSCAPE_EVIDENCE_UNAVAILABLE", str(exc)))
    board["landscape_evidence"] = evidence
    put_issues(board, "missing_evidence", "landscape_review", findings)
    update_metrics(board, "landscape_review", status="reviewed" if "landscape_summary" in board else "incomplete",
                   passages=len(evidence))
    return board


def export(board):
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    summary = board.get("landscape_summary")
    if not summary:
        return board
    spec = dict(schema_spec(board["expected_schema"]))
    if spec.get("format", "docx").lower() != "docx":
        raise ValueError("landscape review exports DOCX")
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(.8)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    for style in ("Title", "Heading 1"):
        doc.styles[style].font.color.rgb = RGBColor(0, 0, 0)
    for element in doc.styles["Title"].element.findall(".//" + qn("w:pBdr")):
        element.getparent().remove(element)
    fmt = lambda key: datetime.fromisoformat(summary[key]).strftime("%m/%d/%Y")
    doc.add_paragraph("L4 Street Tree Resubmittal", style="Title")
    doc.add_paragraph(f"To  Callaway Land Partners\nDate  {fmt('memo_date')}")
    doc.add_paragraph(f"We cannot commit to the {fmt('target')} resubmittal to Yeoman until Clark County "
                      "Comprehensive Planning gives us a written significant-change determination for the L-4 revision. "
                      "The reviewed records do not establish that one has been issued.")
    doc.add_heading("Approval basis", level=1)
    doc.add_paragraph(f"Condition 14 of the {summary['approval_date']} approval letter for TM-22-500041 "
                      "covers landscape and streetscape treatments in common areas. The CC&Rs identify street-tree "
                      "planting strips as HOA-owned Streetscape Common Area, so this revision falls within that scope. "
                      "If Planning finds the change significant, public design review before the Enterprise Town "
                      "Advisory Board and Planning Commission must precede staff-level action on the resubmittal. "
                      "The TAB recommendation is forwarded to the Planning Commission.")
    doc.add_heading("Plan changes and timing", level=1)
    doc.add_paragraph(f"The current sheets show {summary['shown']} trees along {summary['frontage']:,} lf. "
                      f"L-4 requires one tree per {summary['spacing']} lf, or {summary['required']} trees. "
                      f"That is {summary['required'] - summary['shown']} more than shown. Have the landscape architect "
                      "of record revise and seal the planting plan and update the annual irrigation demand.")
    doc.add_paragraph(f"The Enterprise TAB requires applications {summary['lead_days']} days before the meeting. "
                      f"The {fmt('meeting')} deadline was {fmt('cutoff')}. The next available regular meeting is "
                      f"{fmt('next_meeting')}, with filing by {fmt('next_cutoff')}. "
                      "Request the written determination now. If design review is required, revise the schedule "
                      "after Planning confirms the hearing and final action dates.")
    doc.add_paragraph("Basis  Approval letter §C, CC&Rs §2.17, current L1–L4 plan set, "
                      "tracker comment L-4 and outstanding item 9, and the 2026 Enterprise TAB calendar.")
    doc.add_paragraph("Signature  __________________________")
    root = submission_root() / TASK
    root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=root)) / "output"
    output.mkdir()
    path = output / FILENAME
    pending = output / ".memo.tmp"
    try:
        doc.save(pending)
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)
    spec.update(format="docx", required_text=["Callaway", fmt("memo_date"), "Condition 14", "TM-22-500041",
                                             "Streetscape Common Area", "written significant-change determination"])
    board["expected_schema"] = spec
    board["artifact_path"] = str(path)
    update_metrics(board, "landscape_docx_export", status="ok", bytes=path.stat().st_size)
    return board


def verify(board):
    from roundtrip_schema_guard import check_docx

    try:
        path = Path(board["artifact_path"]).resolve(strict=True)
        if not path.is_file() or path.name != FILENAME or not path.is_relative_to(submission_root() / TASK):
            raise ValueError("Unexpected landscape memo path")
        measurements = check_docx(path, schema_spec(board["expected_schema"]))
        board["schema_ok"], board["schema_error"] = True, ""
        update_metrics(board, "roundtrip_schema_guard", status="ok", checks=measurements)
    except (OSError, ValueError) as exc:
        board["schema_ok"], board["schema_error"] = False, str(exc)
        update_metrics(board, "roundtrip_schema_guard", status="failed")
    return board


if __name__ == "__main__":
    cli({"review": review, "export": export, "verify": verify}[sys.argv[1]])
