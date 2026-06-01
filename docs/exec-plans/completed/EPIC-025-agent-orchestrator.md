# EPIC-025: Agent Orchestrator (Agent 全流程编排)

## 状态
- **创建**: 2026-06-01
- **状态**: 已完成
- **优先级**: P2
- **分支**: `codex/epic-025-agent-orchestrator`
- **依赖**: EPIC-023 (工作流成熟度)

## 目标

创建一个 `agent-orchestrator` skill，使用 Claude Code 的 `Workflow` 工具将现有 5 个 agent skill（planner → worker → post-task → reviewer → integrator）串联为一条自动化流水线，补上三个缺失能力：

1. **并行 worker 调度** — 读取 EPIC 的并行安全标记，对安全任务同时 fork worktree 并发执行
2. **阶段自动流转** — planner → workers → reviewer → integrator 自动传递上下文，无需人工逐步调用
3. **EPIC 级别收口** — 所有 TASK 完成后自动更新 docs、quality score、创建合入 main 的最终 PR

## 背景

Agent 技能链现状：

```
agent-planner → agent-worker → [agent-post-task] → agent-reviewer → agent-integrator
```

每一步都需要人工手动调用。没有编排层来自动驱动这个流水线。

Claude Code 已提供 `Workflow` 工具（支持 `agent()`, `parallel()`, `pipeline()`, `phase()` 等编排原语），项目也已具备 worktree 隔离执行机制，但还没有人把它们封装为 skill。

## 并行调度策略

按 `parallel_safety` + `dependencies` 分组 → pipeline over groups → 并发用 worktree 隔离

## 任务分解

### TASK-025-1: 创建 agent-orchestrator Skill

**产出物**:
- `skills/agents/agent-orchestrator/SKILL.md`
- `.claude/workflows/agent-orchestrator.js`
- `.claude/skills/agent-orchestrator/SKILL.md`

### TASK-025-2: 集成到现有约定

**产出物**: 更新 `project/CLAUDE.md` + `AGENTS.md`

### TASK-025-3: 权限与 Settings 配置

**产出物**: 更新 `.claude/settings.json` + `project/.claude/settings.json`

### TASK-025-4: 创建 EPIC 文件

**产出物**: `docs/exec-plans/active/EPIC-025-agent-orchestrator.md`

## 验收标准

1. `@agent-orchestrator EPIC-XXX --dry-run` 输出完整执行计划
2. 并行组内 TASK 在独立 worktree 中并发执行
3. 中断后可恢复
4. 人工介入点有明确提示

---

## 完成记录

- **完成日期**: 2026-06-01
- **完成状态**: 已集成（PR 待合入 main）
- **集成分支**: `integration/EPIC-025-agent-orchestrator`（HEAD: `20c42f6`）
- **最终 PR**: [#18](https://github.com/XuShan0425/E-commerce-automatic/pull/18) — `integration/EPIC-025-agent-orchestrator` → `main`（OPEN）

### 任务合并记录

| 任务 | 合并提交 | 分支 | 说明 |
|------|----------|------|------|
| TASK-025-1 | `3848d1e` | `codex/task-025-1` | 创建 agent-orchestrator Skill — SKILL.md、Workflow 脚本、工具脚本 |
| TASK-025-2 | `88f6576` | `codex/task-025-2` | 注册到 AGENTS.md 和 project/CLAUDE.md |
| TASK-025-3 | `20c42f6` | `codex/TASK-025-3-permissions-settings` | 权限与 Settings 配置 |

### 最终验证

- Document Gardening: 已完成（发现 4 个预存错误，均为已删除遗留文件引用，非本 EPIC 引入）
- Quality Score 一致性验证: 通过
