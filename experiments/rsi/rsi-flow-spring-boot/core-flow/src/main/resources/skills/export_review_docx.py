"""Export a checklist review to Word with the task's template when requested."""

import re
from pathlib import Path
from tempfile import mkdtemp

from skill_common import cli, issue, put_issues, schema_spec, submission_root, task_workspace, update_metrics

SKILL = "docx_export"
HOLD = "Provisional review. Do not treat this document as approval or release."
NUMBERED_HEADING = re.compile(r"^\s*\d+[.)]\s*(\S.*?)\s*$")
TARGET = re.compile(r'''(?:^|[\s`'"])/(filesystem|output)/([^/\\\n`'"]+?\.docx)\b''', re.I)
DOCX_NAME = re.compile(r'^[^<>:"/\\|?*\x00-\x1f]+\.docx$', re.I)


def template_path(board, workspace, spec):
    instruction = board["instruction"].casefold()
    explicit = spec.get("template_path")
    candidates = [
        entry["path"] for entry in board["file_index"] if entry["status"] == "active"
        and (entry["path"] == explicit if explicit else
             Path(entry["path"]).suffix.casefold() == ".docx"
             and "template" in Path(entry["path"]).name.casefold()
             and Path(entry["path"]).name.casefold() in instruction)
    ]
    if not candidates and not explicit and not re.search(r"\buse the template\b", instruction):
        return None
    if len(candidates) != 1:
        raise ValueError("expected one active Word template referenced by the task")
    path = (workspace / candidates[0]).resolve(strict=True)
    if not path.is_relative_to(workspace) or not path.is_file() or path.suffix.casefold() != ".docx":
        raise ValueError("Word template must be a task-local DOCX file")
    return path


def heading(text):
    clean = text.strip().strip("#* ").strip(":").strip()
    numbered = NUMBERED_HEADING.fullmatch(clean)
    return (numbered[1] if numbered else clean).casefold()


def write_template(doc, draft, provisional):
    entries = {
        heading(p.text): doc.paragraphs[i + 1]
        for i, p in enumerate(doc.paragraphs[:-1])
        if NUMBERED_HEADING.fullmatch(p.text) and doc.paragraphs[i + 1].text.strip()
    }
    if not entries:
        raise ValueError("Word template has no numbered section placeholders")
    metadata = {p.text.strip().casefold(): p for p in doc.paragraphs
                if re.fullmatch(r"\s*(?:to|from|date|subject):\s*", p.text, re.I)}
    sections, current = {}, None
    for line in draft.splitlines():
        key = heading(line)
        field = line.partition(":")[0].strip().casefold() + ":"
        if key in entries:
            current = sections.setdefault(key, [])
        elif field in metadata and current is None:
            metadata[field].text = line.strip()
        elif current is not None:
            current.append(line)
    missing = []
    for key, target in entries.items():
        content = "\n".join(sections.get(key, [])).strip()
        if not content:
            missing.append(key)
        decision = re.search(r"conclusion|determination|disposition|recommendation", key)
        if provisional and decision:
            target.text = HOLD + ("\nDraft analysis for review:\n" + content if content else "")
        else:
            target.text = content or "Pending review."
    if missing and draft:
        doc.add_paragraph(draft)
    return missing


def run(board):
    from docx import Document

    board["artifact_path"] = ""
    try:
        spec = dict(schema_spec(board["expected_schema"]))
        if spec.get("format", "docx").casefold().lstrip(".") != "docx":
            raise ValueError("checklist review currently exports DOCX")
        task = Path(board["task_dir"].replace("\\", "/")).parts[0]
        workspace = task_workspace(board)
        template = template_path(board, workspace, spec)
        target = TARGET.search(board["instruction"])
        filename = (spec.get("artifact_filename") or (target[2] if target else None)
                    or board.get("artifact_plan", {}).get("filename") or "Review.docx")
        if not isinstance(filename, str) or not DOCX_NAME.fullmatch(filename):
            raise ValueError("artifact_filename must be a DOCX basename")
        layout = target[1].lower() if target else "output"
        draft = board["draft_output"].strip()
        if not draft:
            raise ValueError("no review draft available to export")
        provisional = board["route_status"] != "PASS"
        doc = Document(str(template)) if template else Document()
        blockers = []
        if template:
            missing = write_template(doc, draft, provisional)
            if missing:
                blockers.append(issue("WORD_TEMPLATE_CONTENT_MISSING",
                                      "Missing template sections: " + ", ".join(missing)))
        else:
            for paragraph in re.split(r"\n\s*\n", draft):
                doc.add_paragraph(paragraph.strip())
        if provisional or blockers:
            board["route_status"] = "EVIDENCE_HOLD"
            spec["hold_statement"] = HOLD
            doc.paragraphs[0].insert_paragraph_before(HOLD)
            if board.get("hold_output"):
                doc.add_paragraph(board["hold_output"])

        spec["format"] = "docx"
        spec["required_text"] = list(dict.fromkeys([
            *spec.get("required_text", []), *board.get("required_check_quotes", []),
        ]))
        parent = submission_root() / task
        parent.mkdir(parents=True, exist_ok=True)
        run_dir = Path(mkdtemp(prefix="run-", dir=parent))
        output = run_dir / layout
        output.mkdir()
        path = output / filename
        temporary = run_dir / ".review.tmp"
        try:
            doc.save(temporary)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        board.update(expected_schema=spec, artifact_path=str(path))
        put_issues(board, "missing_evidence", SKILL, blockers)
        update_metrics(board, SKILL, status="ok", bytes=path.stat().st_size)
    except (OSError, ValueError, IndexError, AttributeError, TypeError) as exc:
        board["route_status"] = "EVIDENCE_HOLD"
        put_issues(board, "missing_evidence", SKILL, [issue("WORD_EXPORT_FAILED", str(exc))])
        update_metrics(board, SKILL, status="error", error=str(exc))
    return board


if __name__ == "__main__":
    cli(run)
