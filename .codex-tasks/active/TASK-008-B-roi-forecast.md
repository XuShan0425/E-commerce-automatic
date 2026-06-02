# TASK-008-B: ROI 预测

## Parent Epic
- Epic: `REP-008`
- Epic file: `docs/exec-plans/active/REP-008-ai-evolution.md`

## Goal
30天历史预测未来 ROI，带置信区间

## Allowed Files
- App/services/roi_forecaster.py (new)
- App/services/analysis_pipeline.py
- frontend Dashboard

## Forbidden Files
- App/models/

## Dependencies
TASK-008-A

## Acceptance Criteria
1. ROI 预测返回带置信区间的结果
2. Dashboard 显示预测曲线
3. MCP Chrome E2E 验证

## Verification Commands
python -c "from App.services.roi_forecaster import RoiForecaster; print('ok')"

## Branch
codex/TASK-008-B-roi-forecast

## Base Branch
codex/TASK-008-A-feedback-loop

## Parallel Safety
false

## Expected Output Artifacts
roi_forecaster.py
