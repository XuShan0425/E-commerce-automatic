# TASK-008-D: A/B 测试

## Parent Epic
- Epic: `REP-008`
- Epic file: `docs/exec-plans/active/REP-008-ai-evolution.md`

## Goal
创建测试变体，80/20 分流，3-14 天，结果对比

## Allowed Files
- App/services/ab_test_service.py (new)
- App/api/v1/ab-test.py (new)
- frontend/src/pages/ABTesting.tsx

## Forbidden Files
- App/models/

## Dependencies
TASK-008-C

## Acceptance Criteria
1. A/B 测试创建/停止工作
2. 结果对比展示
3. MCP Chrome E2E 验证

## Verification Commands
python -c "from App.services.ab_test_service import ABTestService; print('ok')"

## Branch
codex/TASK-008-D-ab-testing

## Base Branch
codex/TASK-008-C-portfolio

## Parallel Safety
false

## Expected Output Artifacts
ab_test_service.py, ABTesting.tsx
