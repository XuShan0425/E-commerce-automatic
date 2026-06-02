# TASK-003-6: E2E 自动化测试

## Parent Epic
- Epic: `REP-003`
- Epic file: `docs/exec-plans/active/REP-003-auto-execution.md`

## Goal
Playwright 验证 1 SKU 的完整执行循环：决策摄取 → 边界检查 → Playwright 操作 → 前后快照 → 操作日志。

## Allowed Files
- tests/test_execution_e2e.py

## Forbidden Files
- App/models/

## Dependencies
TASK-003-5, TASK-003-4

## Acceptance Criteria
1. 模拟 1 SKU 的完整执行循环
2. 验证决策摄取 → 边界检查 → 操作记录 → 日志写入全流程
3. 单元测试通过
4. MCP Chrome E2E 验证

## Verification Commands
python -m pytest tests/test_execution_e2e.py -x -q

## Branch
codex/TASK-003-6-e2e-test

## Base Branch
main

## Parallel Safety
false

## Expected Output Artifacts
tests/test_execution_e2e.py
