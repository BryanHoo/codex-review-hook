# codexreview Hook 设计（PostToolUse 记账 + Stop 汇总）

## 背景与目标

希望在 Claude Code 的 hooks 中集成 codexreview（通过 `codeagent-wrapper` 触发），并解决以下痛点：

- `Stop` 触发时并不一定发生了代码修改；不应无意义地 review。
- 仅用 `git diff` 判断会导致：同一份 diff 在多个 `Stop` 里重复 review；以及“小改动也频繁 review”。

目标：

- 仅在确有“新改动”且“值得 review”时运行 codexreview。
- 支持多维度判定：方案/设计/需求/实施类文档必审；高风险配置/依赖/CI 变更必审；代码改动按规模/跨度触发；小改动累积到阈值再跑。
- 不依赖“关键功能路径”维护（用户明确不做关键路径判断）。

## 总体方案

采用双 hook 结构：

1. `PostToolUse`（仅匹配 `Edit|Write`）负责“轻量记账”，记录本次会话的增量变更指标。
2. `Stop` 负责“汇总决策并触发 codexreview”，且实现灰区累计，避免噪音。

该方案不依赖 git；若处于 git 仓库，可选用 `git diff --numstat` 校准行数。

## 数据与状态

### Hook 输入（来自 Claude Code）

- `PostToolUse` 输入包含：`hook_event_name`、`tool_name`、`tool_input.file_path`、`tool_use_id`、`session_id`、`transcript_path`、`cwd`。
- `Stop` 输入包含：`hook_event_name`、`session_id`、`transcript_path`、`permission_mode`、`stop_hook_active`。

### 状态存储

为避免每次 Stop 解析长 transcript，采用“聚合状态文件”。建议路径：

- `~/.claude/state/codexreview/<session_id>.json`

状态结构建议：

- `pending.events`: 自上次成功 review 以来的 Edit/Write 次数（累计）
- `pending.files`: 去重后的文件集合（或其 hash）
- `pending.modules`: 按相对路径前两段（例如 `src/auth`）去重后的模块集合，用于“模块跨度”
- `pending.lines_touched_est`: 行数估算累计
- `pending.flags.plan_docs`: 是否命中方案/需求/实施类文档
- `pending.flags.risk_files`: 是否命中高风险配置/依赖/CI/发布文件
- `meta.last_review_at`: 上次成功 review 时间
- `meta.last_review_tool_use_id` 或 `meta.checkpoint`: 用于在 jsonl 方案下做 checkpoint（在聚合方案下可省略）

说明：选择“聚合状态文件”的主要目的：

- 灰区累计不需要保留每条事件，只需要保留聚合值。
- Stop 判定更快、更确定。

## 规则：是否值得运行 codexreview

决策流程按优先级：

### 1) 基础过滤

- 若 `pending.events == 0`：直接跳过。
- 可配置 ignore globs：过滤生成物或不重要目录（例如 `node_modules/**`, `dist/**`, `build/**`），避免误记账。

### 2) 硬触发（必审）

满足任一条直接运行 codexreview（不看规模）：

- 方案/设计/需求/实施类文档：
  - 目录类：`docs/plans/**`, `docs/{design,spec,adr,rfc}/**`
  - 文件名类：`**/*{design,spec,requirement,implementation,proposal}*.md`
- 高风险配置/依赖/CI/发布：
  - 示例：`package.json`, `*lock*`, `.github/workflows/**`, `Dockerfile`, `docker/**`, `deploy/**` 等

### 3) 评分触发（规模/跨度）

当不满足硬触发时，计算 score。

指标：

- `unique_files`: 去重文件数
- `lines_touched_est`: 行数估算（无 git 时按 Edit/Write 估算；有 git 时可选用 numstat 校准）
- `module_spread`: 模块跨度（按相对路径前两段去重，如 `src/auth`, `packages/core`）
- `events`: Edit/Write 次数

建议打分（可配置）：

- 文件数：`>=6` +3；`>=3` +2；`==2` +1
- 行数：`>=200` +3；`>=80` +2；`>=30` +1
- 模块跨度：`>=3` +2；`>=2` +1
- 事件数：`>=10` +2；`>=6` +1

判定阈值：

- `score >= 4`：运行 codexreview
- `score <= 3`：不运行，但 **pending 不清零**（灰区累计到阈值再跑）

可选兜底：`pending.events` 或 Stop 次数累计超过 N 也触发一次（避免永远不跑）。

## 记账：如何估算规模（不依赖 git）

- `Edit`：`lines_touched_est += max(lines(old_string), lines(new_string))`
- `Write`：`lines_touched_est += min(lines(content), write_cap)`，`write_cap` 默认 200

模块跨度：

- 将 `file_path` 转为相对 `cwd`，取前两段作为 module key（例如 `src/auth/login.ts` -> `src/auth`）。
- 对 module key 去重计数。

## Stop 防循环

- `Stop` hook 的 stdin 包含 `stop_hook_active`。
- 若 `stop_hook_active == true`：直接退出（避免 stop hook 触发继续对话造成循环）。

## 触发 codexreview（通过 codeagent-wrapper）

- 当 Stop 判定需要运行时，由 Stop hook **直接运行** `codeagent-wrapper`。
- 传入的上下文：
  - 工作目录使用 `cwd`（来自 stdin）
  - 输入内容包含变更摘要（文件列表、规模指标、文档/风险标志）以及（可选）diff 摘要
- 运行成功：清空 `pending` 并更新 `meta.last_review_at`
- 运行失败：保留 `pending`，可设置 cooldown 防止连续失败反复执行

## hooks 配置示例（伪代码）

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "codexreview-record"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "codexreview-stop"
          }
        ]
      }
    ]
  }
}
```

说明：Stop 不支持 matcher，因此在 Stop 脚本内部自行做条件判断。

## 测试与验证

- 手工验证路径：
  - 仅聊天无 Edit/Write：Stop 不触发 review
  - 少量 Edit：Stop 不跑且累计
  - 累计跨过阈值：Stop 跑一次并清零
  - 改动方案/实施文档：立刻跑
  - 改动依赖/CI：立刻跑
  - `stop_hook_active=true`：Stop 不重复执行

---

Sources:
- https://code.claude.com/docs/en/hooks
- https://docs.anthropic.com/en/docs/claude-code/hooks-guide
