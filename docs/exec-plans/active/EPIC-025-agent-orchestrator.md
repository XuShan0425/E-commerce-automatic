# EPIC-025: Agent Orchestrator (Agent 全流程编排)

## 状态
- **创建**: 2026-06-01
- **状态**: 规划中
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
    计划           实现              收工/PR           审查 PR           合并
```

每一步都需要人工手动调用。没有编排层来自动驱动这个流水线。

Claude Code 已提供 `Workflow` 工具（支持 `agent()`, `parallel()`, `pipeline()`, `phase()` 等编排原语），项目也已具备 worktree 隔离执行机制，但还没有人把它们封装为 skill。

## 并行调度策略

```
EPIC 任务列表
    ↓
按 parallel_safety + dependencies 分组
    ├── 无依赖 + parallel_safe → 并行组 (N 个 worktrees 并发)
    ├── 有依赖 → 等依赖组完成后进入下组
    └── parallel_safe ≠ safe → 串行组 (单独 worktree)
    ↓
pipeline over groups: Group[0] → Group[1] → ...
    ↓
每个 task 完成后 → agent-post-task
```

## 任务分解

### TASK-025-1: 创建 agent-orchestrator Skill

**目标**: 创建 skill 入口文件 + Workflow 脚本 + 工具函数

**产出物**:
- `skills/agents/agent-orchestrator/SKILL.md` — skill 定义、触发方式、workflow 设计
- `.claude/workflows/agent-orchestrator.js` — Workflow 脚本（3 phase: Prepare → Execute → Finalize）
- `.claude/workflows/orch-utils.js` — 共享工具函数（TASK 解析、并行分组、上下文协议）

### TASK-025-2: 集成到现有约定

**目标**: 更新项目文档，让 orchestrator 成为推荐的默认工作流

**产出物**:
- 更新 `project/CLAUDE.md` 技能表
- 更新 `AGENTS.md` 默认工作流描述

### TASK-025-3: EPIC 收口自动化

**目标**: 实现 EPIC 完成后的全自动收口

**产出物**:
- EPIC 迁移脚本（active → completed）
- 完成记录追加
- doc-garden + quality-score 触发

## 验收标准

1. `@agent-orchestrator EPIC-XXX --dry-run` 输出完整执行计划
2. 并行组内 TASK 在独立 worktree 中并发执行
3. planner 输出后 orchestrator 可自动读取 TASK 列表继续
4. EPIC 完成后自动触发 doc-garden + quality-score + final PR
5. 中断后可从中断点恢复（不重跑已完成 task）
6. 人工介入点有明确提示

## Decision Log

| 日期 | 决策 | 决策人 | 理由 | 影响 |
|------|------|--------|------|------|
| 2026-06-01 | 创建 EPIC | XuShan0425 | 补齐 agent 编排层的三个缺口，实现端到端自动化 | 新建 3 个 TASK |
