"""Wire format, evidence loading and model transport shared by the skills."""

import ast
import json
import math
import os
import re
import ssl
import sys
import time
from itertools import islice
from copy import deepcopy
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULTS = {
    "task_id": "", "task_dir": "", "instruction": "",
    "retry_count": 0, "max_retry": 2, "file_index": [], "authority_docs": [],
    "claims": [], "draft_output": "", "artifact_path": "", "expected_schema": "",
    "entity_conflicts": [], "coverage_gaps": [], "attribution_warnings": [],
    "missing_evidence": [], "route_status": "", "retry_feedback": "",
    "schema_ok": True, "schema_error": "", "trace_metrics": {},
}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".ini",
    ".log", ".inp", ".fds", ".dat", ".cfg", ".rst",
}
MAX_FILES = 24
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_FILE_CHARS = 18000
MAX_EVIDENCE_CHARS = 120000
ANCHOR = re.compile(r"L(\d+)(?:-L?(\d+))?", re.IGNORECASE)


class ModelError(RuntimeError):
    """The configured model could not provide a usable JSON response."""


class TransportError(RuntimeError):
    """A retryable failure between the model client and its endpoint."""


# Each skill CLI handles one board in its own process.
_transport_exception = ModelError


def merge_defaults(value):
    if not isinstance(value, dict):
        raise ValueError("blackboard must be a JSON object")
    board = {**deepcopy(DEFAULTS), **value}
    for key, default in DEFAULTS.items():
        valid = isinstance(board[key], (str, dict)) if key == "expected_schema" else (
            type(board[key]) is type(default)
        )
        if not valid:
            raise ValueError(f"invalid blackboard field type: {key}")
    return board


def cli(run):
    try:
        board = merge_defaults(json.load(sys.stdin.buffer))
        global _transport_exception
        _transport_exception = TransportError if board.get("trace_id") else ModelError
        try:
            result = run(board)
        except TransportError as exc:
            # Java owns the pristine input and the communication attempt budget.
            result = {"transport_failure": {"kind": "model_transport", "message": str(exc)}}
        data = json.dumps(result, ensure_ascii=False, allow_nan=False)
        sys.stdout.buffer.write((data + "\n").encode("utf-8"))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def issue(code, message, *, blocking=True, retryable=False, **details):
    return dict(code=code, message=message, blocking=blocking, retryable=retryable, **details)


def put_issues(board, field, skill, items):
    existing = [
        item for item in board[field]
        if not isinstance(item, dict) or item.get("source_skill") != skill
    ]
    board[field] = existing + [dict(item, source_skill=skill) for item in items]


def update_metrics(board, skill, **metrics):
    previous = board["trace_metrics"].get(skill)
    previous = previous if isinstance(previous, dict) else {}
    metrics["calls"] = previous.get("calls", 0) + 1
    total = metrics.get("total_tokens")
    if total is not None or "cumulative_tokens" in previous:
        metrics["cumulative_tokens"] = previous.get("cumulative_tokens", 0) + (total or 0)
    board["trace_metrics"][skill] = metrics


def task_workspace(board):
    root_setting = os.environ.get("PLE_TASK_ROOT")
    if not root_setting:
        raise ValueError("set PLE_TASK_ROOT to the task root directory")
    task_dir = Path(board["task_dir"])
    if not board["task_dir"].strip() or task_dir.anchor:
        raise ValueError("task_dir must be a relative path under PLE_TASK_ROOT")
    root = Path(root_setting).resolve(strict=True)
    workspace = (root / task_dir).resolve(strict=True)
    if not workspace.is_dir() or not workspace.is_relative_to(root):
        raise ValueError("task_dir must be a directory under PLE_TASK_ROOT")
    return workspace


def submission_root():
    configured = os.environ.get("PLE_ARTIFACT_ROOT")
    return (Path(configured) if configured else Path.home() / "ple-submissions").resolve()


def artifact_location(board, value, *, must_exist):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("artifact_path is required")
    configured = os.environ.get("PLE_ARTIFACT_ROOT")
    # New standalone submissions and existing task-relative artifacts have separate roots.
    if not configured and Path(value).is_absolute():
        exported = Path(value).resolve(strict=must_exist)
        task = Path(board["task_dir"].replace("\\", "/")).parts
        if (task and (task[0] == "les-mesh-resolution" or board.get("checklist_review"))
                and task[0] not in {".", "..", "/"}
                and exported.is_relative_to(submission_root() / task[0])):
            return exported
    root = Path(configured).resolve(strict=True) if configured else task_workspace(board)
    if not root.is_dir():
        raise ValueError("PLE_ARTIFACT_ROOT must be a directory")
    path = (root / value).resolve(strict=must_exist)
    if path == root or not path.is_relative_to(root):
        raise ValueError("artifact_path must be under the configured artifact root")
    return path


def _source_lines(path):
    suffix = path.suffix.casefold()
    if suffix in TEXT_EXTENSIONS:
        with path.open("rb") as source:
            data = source.read(MAX_FILE_CHARS * 4 + 4)
        encodings = ("utf-16",) if data.startswith((b"\xff\xfe", b"\xfe\xff")) else (
            "utf-8-sig", "gb18030", "cp1252"
        )
        for encoding in encodings:
            try:
                yield from data.decode(encoding).splitlines()
                return
            except UnicodeDecodeError:
                continue
        raise ValueError("unsupported text encoding")
    elif suffix == ".pdf":
        from pypdf import PdfReader
        for index, page in enumerate(PdfReader(str(path), strict=False).pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                yield f"[page {index}]"
                yield from text.splitlines()
    elif suffix == ".docx":
        from docx import Document
        doc = Document(str(path))
        yield from (paragraph.text for paragraph in doc.paragraphs)
        for table in doc.tables:
            yield from (" | ".join(cell.text for cell in row.cells) for row in table.rows)
    elif suffix == ".xlsx":
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in book.worksheets:
                yield f"[sheet {sheet.title}]"
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(cell) if cell is not None else "" for cell in row]
                    if any(cells):
                        yield " | ".join(cells)
        finally:
            book.close()
    else:
        raise ValueError(f"unsupported document format {suffix or '(none)'}")


# Search terms come from the current task, never from benchmark answers.
STOP_WORDS = set("the and for that this from with have what where whether tell behind then into about "
                 "there would could should can our our on are its was were put file filesystem task "
                 "environment files need already nothing give short note saved under does settles "
                 "which them those their rests take taken item lands behind will any".split())


def search_terms(text):
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text).casefold()
    words = set(re.findall(r"[a-z0-9]{2,}", text)) - STOP_WORDS
    for phrase in re.findall(r"[\u3400-\u9fff]+", text):
        words.update(phrase[i:i+2] for i in range(max(1, len(phrase)-1)))
    return words


def relevant_excerpt(body, budget, query, *, requirements=False):
    if len(body) <= budget:
        return body
    lines = body.splitlines()
    # Preserve source line numbers. Keep the opening definitions, then rank small
    # passages rather than spending the whole budget on front matter.
    chunks = ["\n".join(lines[i:i + 5]) for i in range(0, len(lines), 5)]
    scores = [len(search_terms(chunk) & query) for chunk in chunks]
    if requirements:
        required_terms = re.compile(r"\b(?:shall|must|required|prior to|subject to|no later than)\b", re.I)
        scores = [
            2 * score + max(scores[max(0, i - 1):i + 2]) + min(3, len(required_terms.findall(chunks[i])))
            for i, score in enumerate(scores)
        ]
    order = sorted(range(len(chunks)), key=lambda i: (i != 0, -scores[i], i))
    picked = {}
    for i in order:
        chunk = chunks[i]
        if len(chunk) + 1 <= budget:
            picked[i] = chunk
            budget -= len(chunk) + 1
        elif i == 0:
            picked[i] = chunk[:budget]
            break
    return "\n".join(picked[i] for i in sorted(picked))


def add_retrieved_lines(documents, workspace, hits, eligible, *, limit=12):
    # Reopen original files: all consumers validate the same numbered lines,
    # even if the normal first-pass excerpts omitted them.
    spans = {}
    for candidates in list(hits.values())[:limit]:
        for hit in candidates[:3]:
            name, first, last = hit["path"], hit["start_line"], hit["end_line"]
            if (name in eligible and type(first) is int and type(last) is int
                    and 1 <= first <= last <= 6000 and last - first < 4):
                spans.setdefault(name, set()).update(range(first, last + 1))
    added, errors, remaining = {}, [], 16000
    for name, numbers in spans.items():
        try:
            path = (workspace / name).resolve(strict=True)
            if Path(name).anchor or not path.is_relative_to(workspace) or path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("invalid source path or size")
            lines = []
            for n, value in enumerate(islice(_source_lines(path), max(numbers)), 1):
                if n in numbers:
                    line = f"L{n}: {value[:1600]}"
                    if len(line) + 1 <= remaining:
                        lines.append(line)
                        remaining -= len(line) + 1
            if lines:
                added[name] = [line.partition(":")[0] for line in lines]
                known = {line.partition(":")[0]: line for line in documents.get(name, "").splitlines()
                         if re.match(r"^L\d+:", line)}
                for line in lines:
                    known.setdefault(line.partition(":")[0], line)
                documents[name] = "\n".join(known[key] for key in sorted(known, key=lambda k: int(k[1:])))
        except Exception as exc:
            errors.append({"path": name, "reason": str(exc)})
    return added, errors


def requirement_documents(board, documents):
    instruction = "\n".join(f"L{i}: {line}" for i, line in enumerate(board["instruction"].splitlines(), 1))
    return {**documents, "@instruction": instruction}


def add_required_lines(documents, workspace, checks, eligible):
    """Make the source ranges supplied by the checklist available to downstream nodes."""
    hits = {}
    for check in checks[:80]:
        reference = check.get("provenance") if isinstance(check, dict) else None
        if not isinstance(reference, str):
            continue
        name, _, anchor = reference.strip().replace("\\", "/").rpartition(":")
        match = ANCHOR.fullmatch(anchor)
        if name not in eligible or not match or source_available(reference, documents):
            continue
        start, end = int(match[1]), int(match[2] or match[1])
        if 1 <= start <= end <= 6000 and end - start < 12:
            for number in range(start, end + 1, 4):
                hits[(name, number)] = [{"path": name, "start_line": number,
                                         "end_line": min(number + 3, end)}]
    return add_retrieved_lines(documents, workspace, hits, eligible, limit=240)


def collect_evidence(board, *, authority_only, required_checks=None):
    workspace = task_workspace(board)
    active = {}
    for entry in board["file_index"]:
        if isinstance(entry, dict) and entry.get("status") in {"archived", "superseded"}:
            continue
        name = entry.get("path") if isinstance(entry, dict) else entry
        if isinstance(name, str):
            active[name] = None
    authority = {p for p in board["authority_docs"] if isinstance(p, str)}
    # After a solve, audit exactly the source set the solver actually received.
    prior = board["trace_metrics"].get("engineering_solver", {}).get("evidence", {})
    replay = authority_only and isinstance(prior.get("read_paths"), list)
    if replay:
        names = list(dict.fromkeys(prior["read_paths"]))
    elif authority_only:
        names = sorted(authority)
    else:
        names = list(dict.fromkeys([*active, *sorted(authority)]))
    query = search_terms(board["instruction"] + " " + board["task_dir"])
    # Link engineering vocabulary in a question to the labels used by primary records.
    concepts = (
        ({"mesh", "plume", "网格", "羽流"}, {"mesh", "grid", "refinement", "logs", "verification"}),
        ({"ambient", "weather", "气象", "环境"}, {"ambient", "site", "met", "weather", "temperature"}),
        ({"compaction", "压实"}, {"compaction", "density", "proctor", "test"}),
        ({"estimate", "估算"}, {"estimate", "quantity", "takeoff", "cost"}),
    )
    for triggers, synonyms in concepts:
        if query & triggers:
            query.update(synonyms)
    if board.get("checklist_review"):
        review_terms = (
            ({"revision", "resubmittal", "approval"}, {"approval", "condition", "conditions", "approved", "review",
             "hearing", "calendar", "deadline", "determination", "association", "common", "ownership",
             "significant", "design", "staff", "commission"}),
            ({"compaction", "density", "proctor"}, {"gradation", "placement", "retest", "subgrade",
             "inspection", "stockpile", "specification", "register"}),
        )
        for triggers, terms in review_terms:
            if query & triggers:
                query.update(terms)

    def path_priority(name):
        if not board.get("checklist_review"):
            return 0
        if Path(name).name.casefold() in board["instruction"].casefold():
            return 0
        return 1 if name in authority else 2

    def administrative_only(name):
        parts = {part.casefold() for part in Path(name).parts}
        subject = search_terms(Path(name).stem)
        admin = {"hr", "billing", "compensation", "payroll", "staffing"}
        return bool((parts | subject) & admin) and not bool(query & admin)

    def path_score(name):
        path = Path(name)
        return 8 * len(query & search_terms(path.stem)) + len(query & search_terms(str(path.parent)))
    if not replay:
        names.sort(key=lambda n: (administrative_only(n), path_priority(n), -path_score(n), n not in authority, n))
    samples, errors = {}, []
    # Bound the discovery pass separately from the model's context budget.
    for name in names[:MAX_FILES * 4]:
        try:
            path = (workspace / name).resolve(strict=True)
            if Path(name).anchor or not path.is_relative_to(workspace) or not path.is_file():
                raise ValueError("document must be a relative file in the task directory")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("document exceeds read size limit")
            lines, cost, limited = [], 0, False
            for number, line in enumerate(_source_lines(path), 1):
                rendered = f"L{number}: {line}"
                if cost + len(rendered) + 1 > MAX_FILE_CHARS:
                    if not lines:
                        lines.append(rendered[:MAX_FILE_CHARS-1])
                    limited = True
                    break
                lines.append(rendered)
                cost += len(rendered) + 1
            if not any(line.partition(": ")[2].strip() for line in lines):
                raise ValueError("no readable text")
            body = "\n".join(lines)
            samples[name] = (body, limited, search_terms(body) & query)
        except Exception as exc:
            errors.append({"path": name, "reason": str(exc)})
    order = list(samples)
    if not replay:
        weights = {term: math.log1p(len(samples) / (1 + sum(term in v[2] for v in samples.values())))
                   for term in query}
        def relevance(name):
            return path_score(name) + sum(weights[t] for t in sorted(samples[name][2])) / math.log2(2 + len(samples[name][0]) / 1000)
        order.sort(key=lambda n: (administrative_only(n), path_priority(n), -relevance(n), n not in authority, n))
    documents, truncated = {}, []
    remaining = MAX_EVIDENCE_CHARS
    selected = order[:MAX_FILES]
    # Reserve space for each selected record. Short records return their unused quota.
    quota = {}
    weights = {name: 2 if board.get("checklist_review") and path_priority(name) < 2 else 1 for name in selected}
    remaining_weight = sum(weights.values())
    for name in sorted(selected, key=lambda n: len(samples[n][0]) / weights[n]):
        quota[name] = min(len(samples[name][0]), remaining * weights[name] // remaining_weight - 1)
        remaining -= quota[name] + 1
        remaining_weight -= weights[name]
    for name in selected:
        body, limited, _ = samples[name]
        excerpt = relevant_excerpt(body, quota[name], query, requirements=board.get("checklist_review") is True)
        if limited or len(excerpt) < len(body):
            truncated.append(name)
        documents[name] = excerpt
    added = {}
    if board.get("entity_review_extensions") and board.get("targeted_evidence"):
        excluded = {e.get("path") for e in board["file_index"] if isinstance(e, dict)
                    and e.get("status") in {"archived", "superseded"}}
        added, lookup_errors = add_retrieved_lines(documents, workspace, board["targeted_evidence"],
                                                 (set(active) | authority) - excluded)
        errors.extend(lookup_errors)
    checks = board.get("required_checks", []) if required_checks is None else required_checks
    if checks:
        required_lines, lookup_errors = add_required_lines(documents, workspace, checks, set(active))
        added.update(required_lines)
        errors.extend(lookup_errors)
    return documents, {
        "targeted_lines": added,
        "candidate_count": len(names), "read_count": len(documents), "read_paths": list(documents),
        "read_errors": errors, "truncated": truncated,
        "scope_limited": (bool(prior.get("scope_limited")) if replay else False)
                         or len(documents) < len(names) or bool(truncated or errors),
    }


def source_available(reference, documents):
    if not isinstance(reference, str):
        return False
    path, separator, anchor = reference.strip().replace("\\", "/").rpartition(":")
    if not separator or path not in documents or not anchor.strip():
        return False
    match = ANCHOR.fullmatch(anchor.strip())
    if match:
        first, last = int(match[1]), int(match[2] or match[1])
        numbers = {int(line[1:].split(":", 1)[0]) for line in documents[path].splitlines()
                   if re.match(r"^L\d+:", line)}
        return 1 <= first <= last and last - first < len(numbers) and all(
            number in numbers for number in range(first, last + 1)
        )
    return anchor.casefold() in documents[path].casefold()


def chat_json(system, data, *, model_env="PLE_LLM_MODEL", timeout_seconds=None):
    started = time.monotonic()
    base = os.environ.get("PLE_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    key = (os.environ.get("PLE_LLM_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
           or os.environ.get("OPENAI_API_KEY"))
    model = os.environ.get(model_env) or os.environ.get("PLE_LLM_MODEL") or "qwen3.5-plus"
    if not base or not key:
        raise ModelError("configure PLE_LLM_BASE_URL and PLE_LLM_API_KEY")
    url = base.rstrip("/")
    if urlsplit(url).scheme not in {"https", "http"} or not urlsplit(url).hostname:
        raise ModelError("invalid model base URL")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
        ],
    }
    request = Request(
        url, method="POST", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        timeout = float(os.environ.get("PLE_LLM_TIMEOUT_SECONDS", "90"))
        if timeout_seconds is not None:
            timeout = min(timeout, timeout_seconds)
        with urlopen(request, timeout=timeout) as response:
            raw = json.load(response)
        choices = raw.get("choices") if isinstance(raw, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ModelError("MODEL_RESPONSE_SHAPE: missing choices[0]")
        choice = choices[0]
        reason = choice.get("finish_reason")
        if reason not in ("stop", "length", "content_filter", "tool_calls", "function_call", None):
            reason = "other"
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        size = len(content) if isinstance(content, str) else 0
        diagnostic = f"finish_reason={reason}, content_chars={size}"
        if reason == "length":
            raise ModelError(f"MODEL_TRUNCATED: {diagnostic}")
        if not isinstance(content, str) or not content.strip():
            raise ModelError(f"MODEL_CONTENT_MISSING: {diagnostic}")
        content = content.strip()
        fence = chr(96) * 3
        if content.startswith(fence):
            content = re.sub(r"^" + fence + r"(?:json)?\s*|\s*" + fence + r"$", "", content, flags=re.I)
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelError(f"MODEL_INVALID_JSON: {exc.msg} at {exc.lineno}:{exc.colno}; {diagnostic}") from None
        if not isinstance(result, dict):
            raise ModelError(f"MODEL_JSON_NOT_OBJECT: {diagnostic}")
        usage = raw.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        metrics = {"model": model, "latency_ms": round((time.monotonic() - started) * 1000),
                   "finish_reason": reason, "content_chars": size}
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if type(usage.get(field)) is int:
                metrics[field] = usage[field]
        return result, metrics
    except HTTPError as exc:
        if exc.code in (408, 429, 502, 503, 504):
            raise _transport_exception(f"model endpoint returned HTTP {exc.code}") from None
        raise ModelError(f"model endpoint returned HTTP {exc.code}") from None
    except ssl.SSLError as exc:
        detail = getattr(exc, "reason", None) or type(exc).__name__
        raise _transport_exception(f"model endpoint TLS failure: {detail}") from None
    except (URLError, TimeoutError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        errno = getattr(reason, "errno", None)
        suffix = f" ({errno})" if errno is not None else ""
        raise _transport_exception(f"model endpoint request failed: {type(reason).__name__}{suffix}") from None
    except (ConnectionError, HTTPException) as exc:
        raise _transport_exception(f"model endpoint connection or response failed: {type(exc).__name__}") from None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ModelError(f"MODEL_ENVELOPE_INVALID: {type(exc).__name__} at offset {getattr(exc, 'pos', getattr(exc, 'start', 0))}") from None


def object_list(data, key):
    values = data.get(key)
    if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
        raise ModelError(f"model output field {key} must be an array of objects")
    return values


def schema_spec(value):
    if isinstance(value, dict):
        return value
    value = value.strip()
    if value.startswith("{"):
        spec = json.loads(value)
        if not isinstance(spec, dict):
            raise ValueError("expected_schema must encode a JSON object")
        return spec
    return {"format": value.lstrip(".").casefold()} if value else {}


def evaluate_expression(expression):
    """Evaluate short arithmetic expressions containing only numbers and operators."""
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 160:
        raise ValueError("calculation must be a short arithmetic expression")
    tree = ast.parse(expression, mode="eval")

    def value(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            result = float(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = value(node.operand)
            result = -operand if isinstance(node.op, ast.USub) else operand
        elif isinstance(node, ast.BinOp):
            left, right = value(node.left), value(node.right)
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Div):
                result = left / right
            elif isinstance(node.op, ast.Pow) and abs(right) <= 32:
                result = left ** right
            else:
                raise ValueError("unsupported calculation operator")
        else:
            raise ValueError("unsupported calculation expression")
        if not isinstance(result, (int, float)) or not math.isfinite(result):
            raise ValueError("calculation did not produce a finite real number")
        return result

    return value(tree.body)
