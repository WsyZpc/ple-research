import json
import os
import re
import sys
from filecmp import cmp
from pathlib import Path

ARCHIVE_DIRS = {"archive", "archived", "superseded", "obsolete", "归档", "旧版"}
AUTHORITY_HINT = re.compile(r"approv|standards?|definitions?|批准|规范|定义", re.I)
REVISION = re.compile(r"[\s._-]+rev[\s._-]*([a-z]|\d+)$", re.I)


class WorkspaceInputError(ValueError):
    """A configuration or request problem that the caller can correct."""


def resolve_workspace(blackboard):
    if not isinstance(blackboard, dict):
        raise WorkspaceInputError("证据黑板必须是 JSON 对象。")

    setting = os.environ.get("PLE_TASK_ROOT")
    if not setting or not setting.strip():
        raise WorkspaceInputError("请在 IDEA 的 AppTestStarter Windows 启动配置中设置 PLE_TASK_ROOT。")
    try:
        root = Path(setting).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise WorkspaceInputError("PLE_TASK_ROOT 指向的目录不存在或后端无法读取。") from error
    if not root.is_dir():
        raise WorkspaceInputError("PLE_TASK_ROOT 必须指向一个目录。")

    name = blackboard.get("task_dir")
    if not isinstance(name, str) or not name.strip():
        raise WorkspaceInputError("证据黑板需要提供 task_dir。")
    task_dir = Path(name)
    if task_dir.anchor or ".." in task_dir.parts:
        raise WorkspaceInputError("task_dir 必须是 PLE_TASK_ROOT 下的相对路径。")
    try:
        workspace = (root / task_dir).resolve(strict=True)
    except FileNotFoundError as error:
        raise WorkspaceInputError("在 PLE_TASK_ROOT 下找不到 task_dir 指定的任务目录。") from error
    except (OSError, RuntimeError, ValueError) as error:
        raise WorkspaceInputError("后端无法读取 task_dir 指定的任务目录。") from error
    if not workspace.is_relative_to(root) or not workspace.is_dir():
        raise WorkspaceInputError("task_dir 必须指向 PLE_TASK_ROOT 下的目录。")
    if not isinstance(blackboard.get("instruction"), str):
        raise WorkspaceInputError("证据黑板的 instruction 必须是字符串。")
    return workspace


def scan_workspace(blackboard):
    workspace = resolve_workspace(blackboard)
    roots = ()
    if blackboard.get("checklist_review"):
        roots = tuple(path for path in (
            workspace / "environment/files", workspace / "environment/filesystem",
            workspace / "environment/tools/files",
        ) if path.is_dir() and path.resolve() == path)
    roots = roots or (workspace,)

    rows = []
    revisions = []
    latest = {}

    walks = ((root, entry) for root in roots for entry in os.walk(root, followlinks=False))
    for root, (folder, subdirs, files) in walks:
        parent = Path(folder)
        subdirs[:] = sorted(
            name for name in subdirs
            if not (parent / name).is_symlink()
            and (parent / name).resolve() == parent / name
        )

        for name in sorted(files):
            path = parent / name
            if path.is_symlink() or path.resolve() != path or not path.is_file():
                continue
            inside_root = path.relative_to(root)
            if blackboard.get("checklist_review") and inside_root.parts[0] == root.name and len(inside_root.parts) > 1:
                counterpart = root.joinpath(*inside_root.parts[1:])
                if counterpart.is_file() and counterpart.resolve() == counterpart and cmp(path, counterpart, shallow=False):
                    continue

            relative = path.relative_to(workspace)
            archived = any(part.casefold() in ARCHIVE_DIRS for part in relative.parts[:-1])
            row = {"path": relative.as_posix(), "status": "archived" if archived else "active"}
            rows.append(row)

            revision = REVISION.search(path.stem)
            if revision:
                marker = revision.group(1).upper()
                row["revision"] = marker
                if not archived:
                    numeric = marker.isdecimal()
                    order = int(marker) if numeric else ord(marker)
                    base = path.stem[:revision.start()].casefold()
                    group = (parent, base, path.suffix.casefold(), numeric)
                    revisions.append((row, group, order))
                    latest[group] = max(latest.get(group, order), order)

    for row, group, order in revisions:
        if order < latest[group]:
            row["status"] = "superseded"

    blackboard["file_index"] = sorted(rows, key=lambda row: row["path"])
    blackboard["authority_docs"] = [
        row["path"] for row in blackboard["file_index"]
        if row["status"] == "active"
        and (row.get("revision") or AUTHORITY_HINT.search(Path(row["path"]).name))
    ]
    return blackboard


if __name__ == "__main__":
    try:
        blackboard = json.load(sys.stdin.buffer)
        json.dump(scan_workspace(blackboard), sys.stdout)
    except (WorkspaceInputError, json.JSONDecodeError, UnicodeDecodeError) as error:
        message = str(error) if isinstance(error, WorkspaceInputError) else "证据黑板不是有效的 UTF-8 JSON。"
        sys.stderr.buffer.write(("WORKSPACE_RECON_INPUT_ERROR: " + message + "\n").encode("utf-8"))
        sys.exit(1)
