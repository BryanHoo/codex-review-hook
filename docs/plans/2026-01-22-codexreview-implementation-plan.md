# CodexReview Hooks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Claude Code hooks 中实现“PostToolUse 记账 + Stop 汇总判定（灰区累计）+ 直接调用 codeagent-wrapper 跑 codexreview”的自动化流程。

**Architecture:** PostToolUse 钩子只做增量聚合记账（不跑 review）；Stop 钩子读取聚合状态并按规则决定是否触发 review，触发后清空 pending，否则保留 pending 继续累计。

**Tech Stack:** Python 3 标准库（json/pathlib/subprocess/unittest），Claude Code Hooks（stdin JSON），可选 git（用于 numstat 校准）。

---

### Task 1: 建立脚本骨架与目录

**Files:**
- Create: `bin/codexreview-record`
- Create: `bin/codexreview-stop`

**Step 1: 写一个最小可运行的 record 脚本（先不做任何逻辑）**

```python
#!/usr/bin/env python3
import json
import sys

def main():
    _ = json.load(sys.stdin)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 2: 写一个最小可运行的 stop 脚本（先不做任何逻辑）**

```python
#!/usr/bin/env python3
import json
import sys

def main():
    _ = json.load(sys.stdin)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 3: 让两个脚本可执行**

Run: `chmod +x bin/codexreview-record bin/codexreview-stop`
Expected: exit code 0

**Step 4: 手工 sanity check（模拟 stdin）**

Run: `printf '{"session_id":"s","hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"/tmp/a","old_string":"x","new_string":"y"}}' | bin/codexreview-record`
Expected: exit code 0

Run: `printf '{"session_id":"s","hook_event_name":"Stop","stop_hook_active":false}' | bin/codexreview-stop`
Expected: exit code 0

---

### Task 2: 定义状态文件与聚合结构（record 写入）

**Files:**
- Modify: `bin/codexreview-record`
- Create: `lib/codexreview_state.py`

**Step 1: 写 failing test（状态写入 + 聚合累加）**

**Test:** `tests/test_state.py`

```python
import io
import json
import os
import tempfile
import unittest

from lib.codexreview_state import update_state_from_post_tool_use, load_state

class TestState(unittest.TestCase):
    def test_record_edit_updates_pending(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "s.json")
            event = {
                "session_id": "s",
                "cwd": td,
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": os.path.join(td, "src", "a.py"),
                    "old_string": "a\n",
                    "new_string": "b\n\nc\n",
                },
                "tool_use_id": "toolu_1",
            }
            update_state_from_post_tool_use(event, state_path)
            st = load_state(state_path)
            self.assertEqual(st["pending"]["events"], 1)
            self.assertIn(os.path.join(td, "src", "a.py"), st["pending"]["files"])
            self.assertGreaterEqual(st["pending"]["lines_touched_est"], 3)

if __name__ == "__main__":
    unittest.main()
```

**Step 2: 运行测试，确认失败**

Run: `python3 -m unittest -v tests/test_state.py`
Expected: FAIL（导入或函数不存在）

**Step 3: 写最小实现（state 模块）**

`lib/codexreview_state.py`（最小可用版本，后续再扩展字段）：

```python
import json
import os
from pathlib import Path

DEFAULT_STATE = {
    "pending": {
        "events": 0,
        "files": [],
        "modules": [],
        "lines_touched_est": 0,
        "flags": {"plan_docs": False, "risk_files": False},
    },
    "meta": {"last_review_at": None},
}


def load_state(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return json.loads(json.dumps(DEFAULT_STATE))
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path: str, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _count_lines(s: str) -> int:
    if not s:
        return 0
    return s.count("\n") + 1


def _module_key(file_path: str, cwd: str) -> str:
    # Relative to cwd when possible; fallback to absolute parts.
    try:
        rel = str(Path(file_path).resolve().relative_to(Path(cwd).resolve()))
    except Exception:
        rel = str(Path(file_path))
    parts = [p for p in rel.split(os.sep) if p]
    if len(parts) >= 2:
        return os.path.join(parts[0], parts[1])
    if parts:
        return parts[0]
    return ""


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

    save_state(state_path, st)
```

**Step 4: 让 record 脚本调用 state 模块**

- record 从 stdin 读 JSON event
- 计算 `state_path`：`~/.claude/state/codexreview/<session_id>.json`
- 调用 `update_state_from_post_tool_use`

**Step 5: 运行测试，确认通过**

Run: `python3 -m unittest -v tests/test_state.py`
Expected: PASS

---

### Task 3: 实现“文档必审 / 风险文件必审”标志

**Files:**
- Modify: `lib/codexreview_state.py`
- Test: `tests/test_rules_flags.py`

**Step 1: 写 failing test（命中文档/风险文件会设置 flags）**

```python
import os
import tempfile
import unittest

from lib.codexreview_state import update_state_from_post_tool_use, load_state

class TestRuleFlags(unittest.TestCase):
    def test_plan_docs_sets_flag(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "s.json")
            event = {
                "session_id": "s",
                "cwd": td,
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": os.path.join(td, "docs", "plans", "2026-01-22-x-design.md"),
                    "old_string": "a\n",
                    "new_string": "b\n",
                },
                "tool_use_id": "toolu_1",
            }
            update_state_from_post_tool_use(event, state_path)
            st = load_state(state_path)
            self.assertTrue(st["pending"]["flags"]["plan_docs"])

    def test_risk_files_sets_flag(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = os.path.join(td, "s.json")
            event = {
                "session_id": "s",
                "cwd": td,
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": os.path.join(td, "package.json"),
                    "content": "{}\n",
                },
                "tool_use_id": "toolu_2",
            }
            update_state_from_post_tool_use(event, state_path)
            st = load_state(state_path)
            self.assertTrue(st["pending"]["flags"]["risk_files"])

if __name__ == "__main__":
    unittest.main()
```

**Step 2: 运行测试，确认失败**

Run: `python3 -m unittest -v tests/test_rules_flags.py`
Expected: FAIL（flag 未设置）

**Step 3: 写最小实现（路径匹配）**

在 `update_state_from_post_tool_use` 里，对 `file_path` 做简单匹配（默认规则）：

- `plan_docs`: 包含 `docs/plans/` 或文件名包含 `design|spec|requirement|implementation|proposal|adr|rfc` 且扩展名为 `.md`
- `risk_files`: basename 命中 `package.json` 或包含 `lock`，或路径包含 `.github/workflows/`，或 basename 为 `Dockerfile`

**Step 4: 运行测试，确认通过**

Run: `python3 -m unittest -v tests/test_rules_flags.py`
Expected: PASS

---

### Task 4: 实现 Stop 决策与灰区累计（不触发外部命令）

**Files:**
- Create: `lib/codexreview_decider.py`
- Modify: `bin/codexreview-stop`
- Test: `tests/test_decider.py`

**Step 1: 写 failing test（score 与阈值判定）**

```python
import unittest

from lib.codexreview_decider import should_run_review

class TestDecider(unittest.TestCase):
    def test_hard_trigger_plan_docs(self):
        st = {"pending": {"events": 1, "files": ["x"], "modules": ["m"], "lines_touched_est": 1, "flags": {"plan_docs": True, "risk_files": False}}}
        decision = should_run_review(st)
        self.assertTrue(decision["run"])
        self.assertEqual(decision["reason"], "plan_docs")

    def test_gray_zone_accumulates(self):
        st = {"pending": {"events": 2, "files": ["a"], "modules": ["src"], "lines_touched_est": 10, "flags": {"plan_docs": False, "risk_files": False}}}
        decision = should_run_review(st)
        self.assertFalse(decision["run"])  # score should be low

if __name__ == "__main__":
    unittest.main()
```

**Step 2: 运行测试，确认失败**

Run: `python3 -m unittest -v tests/test_decider.py`
Expected: FAIL（模块不存在）

**Step 3: 写最小实现（硬触发 + 打分 + 阈值）**

`lib/codexreview_decider.py`：

- 输入：state dict
- 输出：`{"run": bool, "reason": str, "score": int, "metrics": {...}}`
- 硬触发：`plan_docs` / `risk_files`
- 否则按约定打分，`score >= 4` 才 run

**Step 4: stop 脚本实现只做“读 state + 决策 + 打印摘要”**

- 从 stdin 读 event；如果 `stop_hook_active == true` 直接 exit 0
- 读取 state；若 `pending.events==0` exit 0
- 调用 decider；暂时只 `print()` 一行摘要（便于手工验收）
- 不清零 pending（因为尚未触发外部 review）

**Step 5: 运行测试，确认通过**

Run: `python3 -m unittest -v tests/test_decider.py`
Expected: PASS

---

### Task 5: Stop 触发 codeagent-wrapper，并在成功后清空 pending

**Files:**
- Modify: `bin/codexreview-stop`
- Modify: `lib/codexreview_state.py`
- Test: `tests/test_stop_runner.py`

**Step 1: 先确定 codeagent-wrapper 的实际调用命令**

选择一个固定命令（示例，需以你的实际 wrapper 为准）：

- `codeagent --backend codex --model ...` 或 `codeagent <task>`

在 stop 脚本中以环境变量形式配置：

- `CODEXREVIEW_AGENT_CMD`：例如 `codeagent`（可含固定 flags）

**Step 2: 写 failing test（mock subprocess，成功后清空 pending）**

```python
import os
import tempfile
import unittest
from unittest import mock

from lib.codexreview_state import save_state, load_state

class TestStopRunner(unittest.TestCase):
    def test_run_clears_pending_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            # Prepare state
            sp = os.path.join(td, "s.json")
            save_state(sp, {
                "pending": {
                    "events": 1,
                    "files": [os.path.join(td, "a.py")],
                    "modules": ["src/a"],
                    "lines_touched_est": 50,
                    "flags": {"plan_docs": True, "risk_files": False},
                },
                "meta": {"last_review_at": None},
            })

            # Mock agent cmd
            with mock.patch("subprocess.run") as mrun:
                mrun.return_value.returncode = 0
                # Call a helper you will add in stop script/module
                from lib.codexreview_stop_runner import run_review_if_needed
                run_review_if_needed(state_path=sp, cwd=td, agent_cmd=["codeagent"], prompt="x")

            st = load_state(sp)
            self.assertEqual(st["pending"]["events"], 0)
            self.assertEqual(st["pending"]["files"], [])

if __name__ == "__main__":
    unittest.main()
```

**Step 3: 运行测试，确认失败**

Run: `python3 -m unittest -v tests/test_stop_runner.py`
Expected: FAIL（模块/函数不存在）

**Step 4: 实现 stop runner（最小：subprocess.run + 清空 pending）**

- 新增 `lib/codexreview_stop_runner.py`：
  - `run_review_if_needed(state_path, cwd, agent_cmd, prompt)`
  - `subprocess.run(agent_cmd, input=prompt, text=True, cwd=cwd, capture_output=True)`
  - returncode==0：清空 pending + 更新 `meta.last_review_at`
  - 非 0：保留 pending（可把 stderr 写到 `~/.claude/state/codexreview/<session_id>.last_error.txt`）

**Step 5: stop 脚本串起来**

- 读 stdin event
- `stop_hook_active` 防循环
- 读 state -> decider
- 如果 `run==true`：生成 prompt（包含文件列表/指标/flags/score），调用 runner

**Step 6: 运行测试，确认通过**

Run: `python3 -m unittest -v tests/test_stop_runner.py`
Expected: PASS

---

### Task 6: 配置 hooks 并做端到端手工验证

**Files:**
- Create: `examples/claude-hooks-settings.json`（仅示例片段，最终应合并进你的 Claude Code settings）

**Step 1: 写配置示例**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "bin/codexreview-record" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "bin/codexreview-stop" }
        ]
      }
    ]
  }
}
```

**Step 2: 手工验证用例**

- 只聊天不编辑：Stop 不触发 review
- 单次小 Edit：Stop 不跑，pending 累计
- 多次小 Edit 累计跨阈值：Stop 跑一次并清零
- 改动 `docs/plans/...design.md`：Stop 立刻跑
- 改动 `package.json` 或 `.github/workflows/...`：Stop 立刻跑
- Stop 再次触发且无新 Edit/Write：不重复跑

---

### Task 7:（可选）git numstat 校准行数

**Files:**
- Modify: `lib/codexreview_state.py`
- Modify: `lib/codexreview_decider.py`

**Step 1: 写 failing test（在 git repo 时用 numstat 覆盖估算）**

- 用临时 git repo 初始化一个文件变更
- 断言 `lines_touched` 使用 numstat 值

**Step 2: 最小实现**

- Stop 侧：若 `git rev-parse --is-inside-work-tree` 成功，则对 pending.files 执行：
  - `git diff --numstat -- <files...>`
- 将 numstat 结果写入 state 的 `pending.lines_touched_git`
- decider 优先用 `lines_touched_git`，否则退回 `lines_touched_est`

---

## 执行交接

Plan complete and saved to `docs/plans/2026-01-22-codexreview-implementation-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
