# TASK-020-4: QUALITY_SCORE 自动更新机制

## Parent Epic

- Epic: `EPIC-020`
- Epic file: `docs/exec-plans/active/EPIC-020-knowledge-base-hardening.md`

## Goal

创建 `scripts/update-quality-score.py`，使 Agent 完成任务后能自动更新 `docs/QUALITY_SCORE.md` 中的模块评分。

## Scope

创建 `scripts/update-quality-score.py`:
1. 读取 `docs/QUALITY_SCORE.md` 当前内容并解析 Markdown 表格
2. CLI 接口:
   - `python scripts/update-quality-score.py --module App/services/browser.py --dim D --score 4` — 更新单个维度
   - `python scripts/update-quality-score.py --module App/services/browser.py --note "新: CDP 集成完成"` — 追加备注
   - `python scripts/update-quality-score.py --check` — dry-run 验证一致性
3. 更新策略:
   - 维度评分变化 → 更新表格 + 更新时间戳 → 自动重算项目均分
   - 仅备注变化 → 仅更新备注列
4. 确保表格格式不变，人类仍可手动编辑

## Allowed Files

- `scripts/update-quality-score.py`
- `docs/QUALITY_SCORE.md` (仅通过脚本更新)

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `python scripts/update-quality-score.py --module App/core/errors.py --dim T --score 4` 更新成功
- 更新后 QUALITY_SCORE.md 的表格均分自动重算
- `--check` 模式检测评分与表格一致性
- 脚本幂等性：相同参数执行两次结果一致

## Verification Commands

- `python scripts/update-quality-score.py --check`

## Branch

Branch: `codex/TASK-020-4-quality-score-auto`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 `scripts/update-quality-score.py`
- 保存验证证据到 `.codex-runs/`
