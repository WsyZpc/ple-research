"""Reopen and check the actual artifact without calling a model."""

import json

from skill_common import artifact_location, cli, schema_spec, update_metrics

SKILL = "roundtrip_schema_guard"


def strings(spec, name):
    values = spec.get(name, [])
    if not isinstance(values, list) or not all(isinstance(x, str) and x.strip() for x in values):
        raise ValueError(f"expected_schema.{name} must be an array of nonempty strings")
    return values


def folded(text):
    return " ".join(text.casefold().split())


def check_docx(path, spec):
    from docx import Document
    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    table_cells = [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    text = folded(" ".join([*paragraphs, *table_cells]))
    if not text:
        raise ValueError("DOCX body is empty")
    headings = {
        folded(p.text) for p in doc.paragraphs
        if p.style and (p.style.name.startswith("Heading") or p.style.style_id.startswith("Heading"))
    }
    for section in strings(spec, "required_sections"):
        if folded(section) not in headings:
            raise ValueError(f"missing DOCX section: {section}")
    for term in [*strings(spec, "required_text"), *strings(spec, "required_keywords")]:
        if folded(term) not in text:
            raise ValueError(f"missing DOCX statement: {term}")
    return {"paragraphs": len(paragraphs), "tables": len(doc.tables)}


def check_ifc(path, spec):
    import ifcopenshell
    model = ifcopenshell.open(str(path))
    minimum = spec.get("required_entities", {})
    if not isinstance(minimum, dict) or not all(
        isinstance(name, str) and name.startswith("Ifc") and type(count) is int and count >= 0
        for name, count in minimum.items()
    ):
        raise ValueError("required_entities must map IFC entity names to nonnegative minimum counts")
    minimum = {**minimum, "IfcBuilding": max(1, minimum.get("IfcBuilding", 1))}
    counts = {name: len(model.by_type(name)) for name in minimum}
    for name, expected in minimum.items():
        if counts[name] < expected:
            raise ValueError(f"{name}: found {counts[name]}, expected at least {expected}")

    require_geometry = spec.get("require_geometry", False)
    if type(require_geometry) is not bool:
        raise ValueError("require_geometry must be a boolean")
    if require_geometry:
        from ifcopenshell import geom
        settings = geom.settings()
        for product in model.by_type("IfcProduct"):
            if getattr(product, "Representation", None) is None:
                continue
            try:
                shape = geom.create_shape(settings, product)
                if len(shape.geometry.verts) >= 3 and len(shape.geometry.faces) >= 3:
                    break
            except (RuntimeError, ValueError, AttributeError):
                continue
        else:
            raise ValueError("no represented IFC product has recoverable mesh geometry")
        counts["geometry_verified"] = True
    return counts


def check_text(path, spec, kind):
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError("artifact text is empty")
    if kind == "json":
        content = json.loads(text)
        if content is None or content == "" or content == [] or content == {}:
            raise ValueError("JSON artifact contains no data")
        required = strings(spec, "required_keys")
        if required and (not isinstance(content, dict) or any(key not in content for key in required)):
            raise ValueError("JSON artifact is missing required keys")
    for term in strings(spec, "required_text"):
        if folded(term) not in folded(text):
            raise ValueError(f"missing artifact statement: {term}")
    return {"chars": len(text)}


def check_xlsx(path, spec):
    from openpyxl import load_workbook
    required = {folded(value) for value in strings(spec, "required_headers")}
    name, header_row = spec.get("sheet"), spec.get("header_row")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError("expected_schema.sheet must be a sheet name")
    if header_row is not None and (type(header_row) is not int or header_row < 1):
        raise ValueError("expected_schema.header_row must be a positive integer")
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        if name is not None and name not in book.sheetnames:
            raise ValueError(f"missing XLSX sheet: {name}")
        sheets = [book[name]] if name is not None else book.worksheets
        for sheet in sheets:
            rows = enumerate(sheet.iter_rows(values_only=True), 1)
            for number, row in rows:
                if header_row is not None and number != header_row:
                    continue
                cells = {folded(str(value)) for value in row if value is not None and folded(str(value))}
                if cells:
                    if required <= cells:
                        return {"sheet": sheet.title, "header_row": number}
                    break
        raise ValueError("XLSX is empty or has no matching required headers")
    finally:
        book.close()


def run(board):
    measurements = {}
    try:
        spec = dict(schema_spec(board["expected_schema"]))
        path = artifact_location(board, board["artifact_path"], must_exist=True)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("artifact must be a nonempty regular file")

        kind = path.suffix.lstrip(".").casefold()
        expected = spec.get("format", kind)
        if not isinstance(expected, str) or expected.lstrip(".").casefold() != kind:
            raise ValueError(f"artifact format {kind} does not match expected_schema.format")
        if board["route_status"] == "EVIDENCE_HOLD":
            hold = spec.get("hold_statement", "")
            if not isinstance(hold, str) or not hold.strip():
                raise ValueError("EVIDENCE_HOLD requires expected_schema.hold_statement")
            spec["required_text"] = [*strings(spec, "required_text"), hold]

        if kind == "docx":
            measurements = check_docx(path, spec)
        elif kind == "ifc":
            if spec.get("required_text"):
                raise ValueError("textual acceptance or hold statements require a document artifact")
            measurements = check_ifc(path, spec)
        elif kind == "xlsx":
            if spec.get("required_text") or spec.get("required_keywords"):
                raise ValueError("use a document artifact for textual acceptance or hold statements")
            measurements = check_xlsx(path, spec)
        elif kind in {"txt", "md", "csv", "tsv", "json"}:
            measurements = check_text(path, spec, kind)
        else:
            raise ValueError(f"unsupported artifact format: {kind or '(none)'}")
        board["schema_ok"], board["schema_error"] = True, ""
    except ModuleNotFoundError as exc:
        package = {"docx": "python-docx", "openpyxl": "openpyxl",
                   "ifcopenshell": "ifcopenshell"}.get(exc.name, exc.name)
        board["schema_ok"], board["schema_error"] = False, (
            f"缺少回读依赖 {package}，请安装到 Java 调用的 Python 环境"
        )
    except Exception as exc:
        board["schema_ok"], board["schema_error"] = False, f"{type(exc).__name__}: {exc}"

    update_metrics(board, SKILL, status="ok" if board["schema_ok"] else "failed", checks=measurements)
    return board


if __name__ == "__main__":
    cli(run)
