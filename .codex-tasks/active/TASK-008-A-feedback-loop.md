# TASK-008-A: AI 反馈循环

## Parent Epic
- Epic: `REP-008`
- Epic file: `docs/exec-plans/active/REP-008-ai-evolution.md`

## Goal
决策历史追踪 + prompt 注入历史上下文 + 效果回溯

## Allowed Files
- App/services/decision_history.py (new)
- App/services/decision_engine.py

## Forbidden Files
- App/models/

## Dependencies
无

## Acceptance Criteria
1. 历史决策追踪工作
2. prompt 注入历史上下文
3. 决策结果回溯
4. MCP Chrome E2E 验证

## Verification Commands
python -c "from App.services.decision_history import DecisionHistory; print('ok')"

## Branch
codex/TASK-008-A-feedback-loop

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
decision_history.py
