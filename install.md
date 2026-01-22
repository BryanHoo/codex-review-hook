# CodexReview Hook 安装（给 AI 执行的简洁版）

目标：把“当前仓库”安装为 Claude Code hooks，并把 hooks 写入指定项目的 `.claude/settings.local.json`。

---

## 前置条件

- 已安装 Claude Code（支持 hooks）。
- 已安装 `python3`（建议 `3.10+`）。

---

## 一键安装（推荐：全局安装 + 项目配置）

在终端执行（把 `PROJECT_DIR` 改成你的目标项目根目录；如果就是当前仓库本身也可以）：

```bash
set -euo pipefail

# 1) 参数：当前仓库路径 + 目标项目路径
REPO_DIR="$(pwd)"
PROJECT_DIR="/ABS/PATH/TO/YOUR/PROJECT"

# 2) 安装目录（全局）
INSTALL_DIR="$HOME/.claude/tools/codex-review-hook"
mkdir -p "$HOME/.claude/tools"

# 3) 同步安装（不依赖 git；用 rsync 保证幂等）
rsync -a --delete "$REPO_DIR/" "$INSTALL_DIR/"

# 4) 确保可执行
chmod +x "$INSTALL_DIR/bin/codexreview-record" "$INSTALL_DIR/bin/codexreview-stop"

# 5) 写入/合并 hooks 配置到项目的 .claude/settings.local.json（保留原有其它配置）
mkdir -p "$PROJECT_DIR/.claude"
python3 - "$PROJECT_DIR/.claude/settings.local.json" "$INSTALL_DIR" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
install_dir = Path(sys.argv[2])

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

data = load_json(settings_path)
hooks = data.get("hooks", {})

hooks["PostToolUse"] = [
    {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": str(install_dir / "bin" / "codexreview-record")}],
    }
]
hooks["Stop"] = [
    {"hooks": [{"type": "command", "command": str(install_dir / "bin" / "codexreview-stop")}]}
]

data["hooks"] = hooks
save_json(settings_path, data)
print(f"[ok] wrote {settings_path}")
PY
```

完成后：

- 全局安装位置：`~/.claude/tools/codex-review-hook`
- 项目 hooks 配置：`<PROJECT_DIR>/.claude/settings.local.json`

---

## 可选：指定 review agent 命令

默认会优先使用仓库内 `codeagent/` 目录的 `codeagent-wrapper-*`；也可以强制指定：

```bash
export CODEXREVIEW_AGENT_CMD="codeagent"
```

---

## 快速验证（不依赖 Claude Code）

```bash
set -euo pipefail
INSTALL_DIR="$HOME/.claude/tools/codex-review-hook"

# 1) 造一次很小的 Edit 事件（应当只累计，不触发 review）
printf '{"session_id":"install-check","cwd":"/tmp","hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"/tmp/a.py","old_string":"a\\n","new_string":"b\\n"},"tool_use_id":"toolu_1"}' \
  | "$INSTALL_DIR/bin/codexreview-record"

# 2) 触发一次 Stop（预期输出 run=N）
printf '{"session_id":"install-check","cwd":"/tmp","hook_event_name":"Stop","stop_hook_active":false}' \
  | "$INSTALL_DIR/bin/codexreview-stop"
```

