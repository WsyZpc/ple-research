"""Replay registered RSI nodes against a saved blackboard on the local backend."""

import argparse
import json
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PREFIX = "@com.horsecoder.common.whuTalent.flowTesting.core/FLOW_"
FLOWS = {
    "physics": "PHYSICAL_RECALCULATION",
    "word": "PLE_LES_DELIVERY",
    "solver": "ENGINEERING_SOLVER",
    "entity": "ENTITY_PROVENANCE_AUDIT",
    "coverage": "COVERAGE_ATTRIBUTION_AUDIT",
    "gate": "EPISTEMIC_HOLD_GATE",
    "retention": "REVISION_RETENTION",
    "lookup": "TARGETED_EVIDENCE_LOOKUP",
    "schema": "ROUNDTRIP_SCHEMA_GUARD",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def call(uri, flow, board):
    request = {"flowId": PREFIX + flow, "params": {"blackboard": json.dumps(board, ensure_ascii=False)}}
    req = Request(uri, data=json.dumps(request).encode(), headers={"Content-Type": "application/json; charset=utf-8"})
    with urlopen(req) as response:
        result = json.load(response)["data"]["value"]["result"]
    return json.loads(result) if isinstance(result, str) else result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="input, output, first-solver.json or final.json")
    parser.add_argument("nodes", nargs="+", choices=[*FLOWS, "resume"])
    parser.add_argument("--uri", default="http://127.0.0.1:18080/api/engine/flow")
    args = parser.parse_args()
    board = load(args.snapshot)
    if not isinstance(board, dict) or not board.get("task_dir") or "instruction" not in board:
        parser.error("Expected a full review board with task_dir and instruction.")
    if "resume" in args.nodes:
        if args.nodes != ["resume"] or board.get("route_status") != "TRANSPORT_PAUSED":
            parser.error("Use resume alone with the final.json of a TRANSPORT_PAUSED run.")
        paused = board
        board = load(Path(paused["resume_input"]))
        if paused["trace_id"] != board.get("trace_id"):
            parser.error("Input checkpoint and paused run do not match.")
        entries = {"entity_provenance_audit": "AUDIT_1", "coverage_attribution_audit": "AUDIT_2",
                   "engineering_solver": board.get("solver_entry", "SOLVE")}
        board["review_entry"] = entries[paused["failed_node"]]
        flows = ["PLE_CONTINUE_ENTITY_REVIEW"]
    else:
        if board.get("route_status") == "TRANSPORT_PAUSED":
            parser.error("Use resume or explicitly select an earlier input checkpoint.")
        flows = [FLOWS[n] for n in args.nodes]

    parent = board.get("trace_id")
    trace_id = str(uuid.uuid4())
    board.update(trace_id=trace_id, trace_seq=0)
    board.pop("trace_dir", None)
    board["replay_source"] = str(args.snapshot.resolve())
    if parent:
        board["parent_trace_id"] = parent
    for flow in flows:
        try:
            board = call(args.uri, flow, board)
        except HTTPError as exc:
            raise SystemExit(f"{flow} returned HTTP {exc.code}. Inspect the matching IDEA log. Replay ID {trace_id}.") from None
        if board.get("trace_id") != trace_id or not board.get("trace_dir") or not board.get("trace_seq"):
            raise SystemExit("Backend did not record the replay. Rebuild and restart AppTestStarter Windows.")
        if board.get("route_status") == "TRANSPORT_PAUSED":
            break
    directory = Path(board["trace_dir"])
    # A partial replay gets its own filename; final.json denotes a completed orchestration or pause.
    target = directory / ("paused-replay.json" if board.get("route_status") == "TRANSPORT_PAUSED" else "replay-result.json")
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
    temp.replace(target)
    print("Saved", target)
    for key in ("route_status", "retry_count", "schema_ok", "failed_node", "artifact_path"):
        if board.get(key) is not None:
            print(f"{key}: {board[key]}")


if __name__ == "__main__":
    main()
