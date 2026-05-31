# TASK-023-4: 任务完成自动通知 (task-complete.py)

## Parent Epic

- Epic: `EPIC-023`
- Epic file: `docs/exec-plans/active/EPIC-023-workflow-maturity.md`

## Goal

创建 `scripts/task-complete.py`，在 Agent 完成任务后自动更新 Task/EPIC 状态、更新 QUALITY_SCORE、生成完成摘要。

## Scope

创建 `scripts/task-complete.py`:

1. TASK 状态迁移:
   - `python scripts/task-complete.py --task TASK-020-1`
   - 移动 task 文件: `pr-opened/` → `completed/`

2. EPIC 状态检测:
   - 检测该 EPIC 下所有 TASK 是否均在 completed/ 或 pr-opened/
   - 若全部完成 → 移动 EPIC: active/ → completed/

3. QUALITY_SCORE 自动更新:
   - 若 TASK 文件中包含 "## Quality Impact" section → 调用 `update-quality-score.py`

4. 完成摘要生成:
   - `.codex-runs/TASK-XXX-summary.md`
   - 包含: 完成时间、分支、PR URL、验证状态

5. 支持 `--dry-run`

## Allowed Files

- `scripts/task-complete.py`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `python scripts/task-complete.py --dry-run --task TASK-001` 输出迁移计划
- TASK 完成后状态正确迁移
- EPIC 全 TASK 完成 → EPIC 自动标记 completed

## Verification Commands

- `python scripts/task-complete.py --dry-run --task TASK-001`

## Branch

Branch: `codex/TASK-023-4-task-complete`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 task-complete 脚本
- 保存验证证据到 `.codex-runs/`
