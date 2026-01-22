# CodexReview Hook 安装

目标：在 Claude Code 中启用 hooks，让本仓库的 `bin/codexreview-record` 与 `bin/codexreview-stop` 自动运行。

## 前置条件

- Claude Code（支持 hooks）。
- `python3`（建议 `3.10+`）。
- git（用于克隆仓库）。

## 安装到用户目录

推荐安装到：`$HOME/.claude/tools/codex-review-hook`

### 1）克隆仓库

macOS / Linux：

```bash
mkdir -p "$HOME/.claude/tools"
git clone https://github.com/BryanHoo/codex-review-hook.git "$HOME/.claude/tools/codex-review-hook"
```

Windows（PowerShell 示例）：

```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\tools" | Out-Null
git clone https://github.com/BryanHoo/codex-review-hook.git "$HOME\.claude\tools\codex-review-hook"
```

### 2）写 hooks 配置

编辑（或新建）：

- macOS / Linux：`~/.claude/settings.json`
- Windows：`C:\Users\<你的用户名>\.claude\settings.json`

把以下 `"hooks"` 合并进去（不要覆盖你已有的其它配置项）。配置完成后，对所有项目生效。

> 只想对某个项目生效：把同样的 `"hooks"` 放到 `<项目>/.claude/settings.json` 或 `<项目>/.claude/settings.local.json`。

macOS / Linux（推荐：显式用 `python3` 调用，避免依赖脚本可执行位/`env` PATH）：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $HOME/.claude/tools/codex-review-hook/bin/codexreview-record"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 $HOME/.claude/tools/codex-review-hook/bin/codexreview-stop"
          }
        ]
      }
    ]
  }
}
```

如果你的 Claude Code hooks 环境里找不到 `python3`（常见于从 GUI 启动导致 PATH 不完整），用 `command -v python3` 找到绝对路径后替换掉上面命令里的 `python3`（例如 `/opt/homebrew/bin/python3`）。

Windows（建议显式用 `python` 或 `py -3` 调用；JSON 里路径需要写双反斜杠）：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "py -3 C:\\\\Users\\\\<你的用户名>\\\\.claude\\\\tools\\\\codex-review-hook\\\\bin\\\\codexreview-record"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "py -3 C:\\\\Users\\\\<你的用户名>\\\\.claude\\\\tools\\\\codex-review-hook\\\\bin\\\\codexreview-stop"
          }
        ]
      }
    ]
  }
}
```

## 验收要点（在 Claude Code 内）

- 只聊天不改文件：不会触发 review。
- 少量 `Edit|Write`：通常先累计，不到阈值不跑。
- 修改以下任意一类文件：下一次 `Stop` 应触发 review：
  - `docs/plans/**` 或命中 design/spec/requirement/implementation/proposal/adr/rfc 的 `.md`
  - `package.json`、文件名含 `lock`、`.github/workflows/**`、`Dockerfile`
