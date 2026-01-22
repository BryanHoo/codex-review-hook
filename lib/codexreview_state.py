import copy
import json
import os
import uuid
from pathlib import Path

DEFAULT_STATE = {
    "pending": {
        "events": 0,
        "files": [],
        "modules": [],
        "lines_touched_est": 0,
        "lines_touched_git": None,
        "flags": {"plan_docs": False, "risk_files": False},
    },
    "meta": {"last_review_at": None},
}


def load_state(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return copy.deepcopy(DEFAULT_STATE)
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path: str, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Best-effort atomic write: write to a unique temp file then replace.
    tmp = p.with_name(f"{p.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _count_lines(s: str) -> int:
    if not s:
        return 0
    return s.count("\n") + 1


def _module_key(file_path: str, cwd: str) -> str:
    # Use Path.parts for cross-platform stability. We intentionally normalize the
    # key separator to "/" so the same codebase yields the same module keys.
    try:
        rel = Path(file_path).resolve().relative_to(Path(cwd).resolve())
        parts = rel.parts
    except (ValueError, OSError):
        parts = Path(file_path).parts

    # Drop drive/anchor segments if present (e.g. Windows drive, absolute root).
    parts = tuple(p for p in parts if p not in (os.sep, "") and not p.endswith(":\\"))

    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    if parts:
        return parts[0]
    return ""


def _is_plan_doc(file_path: str) -> bool:
    from pathlib import Path
    p = Path(file_path)
    path_str = str(p)
    basename = p.name.lower()
    stem = p.stem.lower()

    # Path contains docs/plans/
    if "docs/plans/" in path_str or "/docs/plans/" in path_str:
        return True

    # Filename contains keywords and extension is .md
    keywords = ["design", "spec", "requirement", "implementation", "proposal", "adr", "rfc"]
    if p.suffix.lower() == ".md":
        for kw in keywords:
            if kw in stem:
                return True

    return False


def _is_risk_file(file_path: str) -> bool:
    from pathlib import Path
    p = Path(file_path)
    path_str = str(p)
    basename = p.name.lower()

    # basename is package.json
    if basename == "package.json":
        return True

    # basename contains lock
    if "lock" in basename:
        return True

    # path contains .github/workflows/
    if ".github/workflows/" in path_str or "/.github/workflows/" in path_str:
        return True

    # basename is Dockerfile
    if basename == "dockerfile":
        return True

    return False


def update_state_from_post_tool_use(event: dict, state_path: str, write_cap: int = 200) -> None:
    st = load_state(state_path)
    tool = event.get("tool_name")
    tool_input = event.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    cwd = event.get("cwd") or ""

    if tool not in ("Edit", "Write") or not file_path:
        return

    st["pending"]["events"] += 1

    if file_path not in st["pending"]["files"]:
        st["pending"]["files"].append(file_path)

    mk = _module_key(file_path, cwd)
    if mk and mk not in st["pending"]["modules"]:
        st["pending"]["modules"].append(mk)

    if tool == "Edit":
        old_s = tool_input.get("old_string", "")
        new_s = tool_input.get("new_string", "")
        st["pending"]["lines_touched_est"] += max(_count_lines(old_s), _count_lines(new_s))

    if tool == "Write":
        content = tool_input.get("content", "")
        st["pending"]["lines_touched_est"] += min(_count_lines(content), int(write_cap))

    # Set flags based on file path
    if _is_plan_doc(file_path):
        st["pending"]["flags"]["plan_docs"] = True
    if _is_risk_file(file_path):
        st["pending"]["flags"]["risk_files"] = True

    save_state(state_path, st)