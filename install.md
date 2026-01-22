# CodexReview Hook 安装文档（仅指导，无脚本）

目标：在 Claude Code 中启用 hooks，让本仓库的 `bin/codexreview-record` 与 `bin/codexreview-stop` 在合适时机自动运行。

---

## 前置条件

- 已安装 Claude Code（支持 hooks）。
- 已安装 `python3`（建议 `3.10+`）。

---

## 全局安装（推荐）

说明：本文档所有路径都使用“绝对路径示例”。请将示例中的 `/Users/<你的用户名>` 替换为你机器上家目录的绝对路径（例如 macOS 通常是 `/Users/<用户名>`，Linux 通常是 `/home/<用户名>`）。

### Step 1：把本仓库放到固定目录

推荐安装目录：`/Users/<你的用户名>/.claude/tools/codex-review-hook`

用 git：

```bash
mkdir -p /Users/<你的用户名>/.claude/tools
git clone https://github.com/BryanHoo/codex-review-hook.git /Users/<你的用户名>/.claude/tools/codex-review-hook
```

### Step 2：确保 hooks 脚本可执行

```bash
chmod +x /Users/<你的用户名>/.claude/tools/codex-review-hook/bin/codexreview-record
chmod +x /Users/<你的用户名>/.claude/tools/codex-review-hook/bin/codexreview-stop
```

### Step 3：在目标项目写 hooks 配置

在目标项目根目录编辑（或新建）：

- `<项目>/.claude/settings.json`（团队共享，通常会提交到仓库）
- 或 `<项目>/.claude/settings.local.json`（个人本地，不建议提交）

把以下 `"hooks"` 合并进去（不要覆盖你已有的其它配置项）：

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

---

## 可选：指定 review agent 命令

默认情况下，Stop hook 会优先使用本仓库 `codeagent/` 目录下随附的 `codeagent-wrapper-*`。

如果你想强制指定（例如使用 PATH 里的 `codeagent`），可设置环境变量：

```bash
export CODEXREVIEW_AGENT_CMD="codeagent"
```

---

## 验收要点（在 Claude Code 内）

- 只聊天不改文件：不会触发 review。
- 少量 `Edit|Write`：通常先累计，不到阈值不跑。
- 修改以下任意一类文件：下一次 `Stop` 应触发 review：
  - `docs/plans/**` 或命中 design/spec/requirement/implementation/proposal/adr/rfc 的 `.md`
  - `package.json`、文件名含 `lock`、`.github/workflows/**`、`Dockerfile`
