# TASK-020-3: 创建 PLANS.md + 计划模板标准化

## Parent Epic

- Epic: `EPIC-020`
- Epic file: `docs/exec-plans/active/EPIC-020-knowledge-base-hardening.md`

## Goal

创建 `docs/PLANS.md`（修复 AGENTS.md Context Map 中已引用但实际不存在的文件），并标准化所有 EPIC 文件的模板格式。

## Scope

1. 创建 `docs/PLANS.md`：
   - EPIC 命名规范: EPIC-XXX-<slug>.md
   - 生命周期: Draft → Active → Completed/Failed
   - 必须包含 section: ## Goal, ## Decision Log, ## Status
   - 决策日志格式为 Markdown 表格
2. 为所有活跃 EPIC 文件追加 `## Decision Log` section（若缺失）:
   - `docs/exec-plans/active/EPIC-001.md` ~ `EPIC-013.md`
   - 每个追加空决策日志表格（保持已有内容不变）

## Allowed Files

- `docs/PLANS.md`
- `docs/exec-plans/active/EPIC-*.md`

## Forbidden Files

- `App/`
- `frontend/`
- `scripts/`

## Acceptance Criteria

- `docs/PLANS.md` 存在，包含 EPIC 命名规范、生命周期、模板要求
- AGENTS.md Context Map 中的 PLANS.md 引用不再断裂
- 所有活跃 EPIC 文件包含 `## Decision Log` section
- `python scripts/lints/check-docs.py` 验证通过

## Verification Commands

- `python scripts/lints/check-docs.py`

## Branch

Branch: `codex/TASK-020-3-plans-md`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 `docs/PLANS.md`
- 更新所有活跃 EPIC 文件追加 Decision Log
- 保存验证证据到 `.codex-runs/`
