# TASK-023-3: Agent 能力矩阵 (AGENT_CAPABILITIES.md)

## Parent Epic

- Epic: `EPIC-023`
- Epic file: `docs/exec-plans/active/EPIC-023-workflow-maturity.md`

## Goal

创建 `docs/AGENT_CAPABILITIES.md`，明确定义 Agent 能自主完成什么、需要人工审查什么、绝对禁止什么。这是 Stop Hook 安全策略的行为基础。

## Scope

创建 `docs/AGENT_CAPABILITIES.md`:

1. 任务类型四级分类表:
   - ✅ 完全自主: 代码格式化、lint 修复、新增 CRUD 端点、文档更新
   - ⚠️ 需审查: 新增 Service、DB 迁移、配置修改
   - ❗ 需人工: 定价逻辑、调价下限、安全逻辑
   - ❌ 禁止: .env 修改、密钥管理、部署到生产

2. 决策框架:
   - 破坏性变更 → EPIC plan + 人工 approve
   - 仅新增代码 → agent-worker 自主
   - 修改现有逻辑 → agent-reviewer + 人工 approve
   - 删除代码 → agent-reviewer 确认无引用
   - 数据迁移 → dry-run + 人工 confirm

3. 信任梯度 (Level 0-3):
   - Level 0: 禁止 (.env, secrets, 部署)
   - Level 1: 保守 (必须人工 — 定价、迁移)
   - Level 2: 辅助 (Agent 自主 + 人工 approve — 新功能)
   - Level 3: 自主 (Agent 自主 PR + 可自动合并 — lint, docs)

4. 更新 AGENTS.md Context Map 引用此文件

## Allowed Files

- `docs/AGENT_CAPABILITIES.md`
- `AGENTS.md` (仅追加 Context Map 条目)

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `docs/AGENT_CAPABILITIES.md` 存在且包含四级分类和信任梯度
- `AGENTS.md` Context Map 引用此文件
- Stop Hook 能根据信任梯度自动决定行为

## Verification Commands

- `python scripts/lints/check-docs.py`

## Branch

Branch: `codex/TASK-023-3-agent-capabilities`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 Agent 能力矩阵文档
- 更新 AGENTS.md
- 保存验证证据
