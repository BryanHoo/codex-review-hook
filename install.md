# CodexReview Hook 安装文档

目标：在 Claude Code 中启用 hooks，让本仓库的 `bin/codexreview-record` 与 `bin/codexreview-stop` 在合适时机自动运行。

---

## 前置条件

- 已安装 Claude Code（支持 hooks）。
- 已安装 `python3`（建议 `3.10+`）。
- 已安装 git（用于克隆仓库）。

---

## 全局安装

说明：本文档所有路径都使用“绝对路径示例”。请把示例中的用户名与路径替换为你机器上的真实绝对路径。

### Step 1：把本仓库放到固定目录

推荐安装目录：

- macOS：`/Users/<你的用户名>/.claude/tools/codex-review-hook`
- Linux：`/home/<你的用户名>/.claude/tools/codex-review-hook`
- Windows：`C:\Users\<你的用户名>\.claude\tools\codex-review-hook`

用 git：

macOS / Linux：

```bash
mkdir -p /Users/<你的用户名>/.claude/tools
git clone https://github.com/BryanHoo/codex-review-hook.git /Users/<你的用户名>/.claude/tools/codex-review-hook
```

Windows（PowerShell 示例）：

```powershell
New-Item -ItemType Directory -Force "C:\Users\<你的用户名>\.claude\tools" | Out-Null
git clone https://github.com/BryanHoo/codex-review-hook.git "C:\Users\<你的用户名>\.claude\tools\codex-review-hook"
```

### Step 2：确保 hooks 脚本可执行

macOS / Linux：

```bash
chmod +x /Users/<你的用户名>/.claude/tools/codex-review-hook/bin/codexreview-record
chmod +x /Users/<你的用户名>/.claude/tools/codex-review-hook/bin/codexreview-stop
```

Windows：

- 一般不需要 `chmod`。
- 为保证可运行，建议在 hooks 的 `command` 里显式用 `python`/`py -3` 调用脚本（见下一步）。

### Step 3：写全局 hooks 配置

在用户目录的 Claude Code 全局配置里编辑（或新建）：

- macOS / Linux：`~/.claude/settings.json`
- Windows：`C:\Users\<你的用户名>\.claude\settings.json`

把以下 `"hooks"` 合并进去（不要覆盖你已有的其它配置项）。配置完成后，该 hooks 将对所有项目生效。

> 如果你只想在某个项目启用，也可以把同样的 `"hooks"` 放到 `<项目>/.claude/settings.json` 或 `<项目>/.claude/settings.local.json`，覆盖全局配置。

macOS / Linux（绝对路径）：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/<你的用户名>/.claude/tools/codex-review-hook/bin/codexreview-record"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/<你的用户名>/.claude/tools/codex-review-hook/bin/codexreview-stop"
          }
        ]
      }
    ]
  }
}
```

Windows（建议显式用 `python` 调用；JSON 里路径需要写双反斜杠）：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python C:\\\\Users\\\\<你的用户名>\\\\.claude\\\\tools\\\\codex-review-hook\\\\bin\\\\codexreview-record"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python C:\\\\Users\\\\<你的用户名>\\\\.claude\\\\tools\\\\codex-review-hook\\\\bin\\\\codexreview-stop"
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
