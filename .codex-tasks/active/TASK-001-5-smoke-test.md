# TASK-001-5: 冒烟测试

## Parent Epic
- Epic: `REP-001`
- Epic file: `docs/exec-plans/active/REP-001-core-pipeline-fix.md`

## Goal
创建 tests/test_critical_path.py，模拟 1 SKU 执行采集→利润→AI→边界→断言非零，在非 Docker 和 Docker 环境下均可运行。

## Allowed Files
- tests/test_critical_path.py
- App/services/profit_calculator.py
- App/services/decision_engine.py

## Forbidden Files
- App/models/

## Dependencies
TASK-001-2, TASK-001-4

## Acceptance Criteria
1. 冒烟测试模拟完整链路并断言非零
2. 可在 Docker 内外运行
3. MCP Chrome E2E 验证：测试通过后验证 API 返回正确数据

## Verification Commands
python -m pytest tests/test_critical_path.py -x -q

## Branch
codex/TASK-001-5-smoke-test

## Base Branch
main

## Parallel Safety
false

## Expected Output Artifacts
tests/test_critical_path.py
