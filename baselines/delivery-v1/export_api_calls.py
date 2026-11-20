"""Export PLE model-call metadata as one JSONL and CSV row per attempt."""

import argparse
import csv
import json
from pathlib import Path

PREFIX = "PLE_API_TRACE "
COLUMNS = (
    "run_id", "task_id", "trial", "session_id", "turn", "harness_try",
    "http_try", "attempt_kind", "model", "purpose", "started_at", "finished_at",
    "duration_ms", "transport_status", "http_status", "transport_error_type",
    "provider_request_id", "redirect_count", "model_status", "model_error_type",
    "retry_scheduled", "finish_reason", "input_tokens", "output_tokens",
    "cached_input_tokens", "selected_tools", "tool_results", "source_log",
)


def records_for_log(run_dir, log_path):
    relative = log_path.relative_to(run_dir)
    rows = {}
    with log_path.open(encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.strip() == "... [cut] ...":
                raise SystemExit(f"PLE truncated {log_path}. The call log is incomplete.")
            if not line.startswith(PREFIX):
                continue
            try:
                item = json.loads(line[len(PREFIX):])
                key = tuple(item[field] for field in (
                    "session_id", "turn", "harness_try", "http_try",
                ))
                event = item["event"]
            except (TypeError, ValueError, KeyError) as exc:
                raise SystemExit(f"Invalid trace at {log_path}:{line_number}") from exc
            if event == "request_started":
                rows[key] = {
                    "run_id": run_dir.name,
                    "task_id": log_path.parent.parent.name.split("__", 1)[0],
                    "trial": relative.parent.parent.as_posix(),
                    "source_log": f"{relative.as_posix()}:{line_number}",
                    "started_at": item["timestamp"],
                    "transport_status": "started_no_end",
                    "tool_results": [],
                    **{field: item[field] for field in (
                        "session_id", "turn", "harness_try", "http_try",
                        "attempt_kind", "model", "purpose",
                    )},
                }
                continue
            row = rows.get(key)
            if row is None:
                continue
            if event == "request_finished":
                row["finished_at"] = item["timestamp"]
                row.update({field: item[field] for field in (
                    "duration_ms", "transport_status", "http_status",
                    "transport_error_type", "provider_request_id", "redirect_count",
                ) if field in item})
            elif event == "model_reply":
                row["model_status"] = "response_parsed"
                row.update({field: item[field] for field in (
                    "finish_reason", "input_tokens", "output_tokens",
                    "cached_input_tokens", "selected_tools",
                )})
            elif event == "model_error":
                row["model_status"] = item["status"]
                row["model_error_type"] = item["error_type"]
                row["retry_scheduled"] = item["retry_scheduled"]
            elif event == "tool_result":
                row["tool_results"].append({
                    "tool": item["tool"], "outcome": item["outcome"],
                    "output_chars": item["output_chars"], "exit_code": item["exit_code"],
                })
    return rows.values()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    rows = [
        row
        for path in sorted(run_dir.glob("attempt*/jobs/*/*/agent/serve.log"))
        for row in records_for_log(run_dir, path)
    ]
    if not rows:
        raise SystemExit(f"No model-attempt events found in {run_dir}/attempt*/jobs/*/*/agent/serve.log")

    jsonl_path = run_dir / "api_calls.jsonl"
    csv_path = run_dir / "api_calls.csv"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as jsonl:
        for row in rows:
            jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                for key, value in row.items()
            })
    print(f"Exported {len(rows)} HTTP attempts to {jsonl_path} and {csv_path}")


if __name__ == "__main__":
    main()
