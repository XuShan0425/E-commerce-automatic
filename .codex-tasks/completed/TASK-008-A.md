# TASK-008-A-feedback-loop

## Parent Epic

- Epic: `REP-008`
- Epic file: `docs/exec-plans/active/REP-008.md`

## Goal

实现反馈闭环机制：AI 决策的执行结果（成功/失败、ROI 变化）被记录并反馈到下一次 AI 分析上下文中，形成"决策→执行→观察→反馈→再决策"的闭环。

## Scope

1. 创建 `App/services/feedback_service.py`：查询近 N 天的操作日志，汇总决策历史（含执行结果、前后 ROI 对比）
2. 修改 `App/services/decision_engine.py`：在 AI 输入中包含决策历史，让 AI 可以感知过去操作的结果
3. 修改 `App/services/analysis_pipeline.py`：在分析管线中调用反馈服务，将历史数据传递到决策引擎
4. 新增 `tests/test_feedback_service.py`：覆盖反馈服务的单元测试

## Allowed Files

- `App/services/feedback_service.py` (新增)
- `App/services/decision_engine.py`
- `App/services/analysis_pipeline.py`
- `tests/test_feedback_service.py`
- `.codex-tasks/active/TASK-008-A-feedback-loop.md`
- `docs/exec-plans/active/REP-008.md`

## Forbidden Files

- `App/main.py`
- `App/core/config.py`

## Acceptance Criteria

1. `feedback_service.get_decision_history()` 返回 SKU 近 N 天的决策记录，包含操作类型、新旧值、执行状态
2. 决策历史包含 ROI 变化对比（操作前后的 ROI 变化）
3. AI 决策 prompt 中包含决策历史上下文
4. `analyze_single_sku` 调用反馈服务并将历史传入决策引擎
5. 所有代码通过 ruff lint 检查

## Verification Commands

- `ruff check App/services/feedback_service.py App/services/decision_engine.py App/services/analysis_pipeline.py`
- `python -m pytest tests/test_feedback_service.py -x -v 2>&1 || echo "tests not yet available"`

## Branch

Branch: `codex/TASK-008-A-feedback-loop`

## Base Branch

Base branch: `main`

## Output Requirements

- Update this task file with concise execution notes.
- Save logs and verification evidence under `.codex-runs/`.
- Open or update a GitHub PR.
- Do not auto-merge.
