# TASK-002-5: 集成测试

## Parent Epic
- Epic: `REP-002`
- Epic file: `docs/exec-plans/active/REP-002-pipeline-quality.md`

## Goal
创建 tests/test_analysis_pipeline.py，用模拟数据填充 DB，对 3 个 SKU 运行 analyze_all_skus，断言均成功且利润非零。

## Allowed Files
- tests/test_analysis_pipeline.py

## Forbidden Files
- App/models/

## Dependencies
TASK-002-1, TASK-002-4

## Acceptance Criteria
1. 模拟数据填充 DB（3 个 SKU）
2. analyze_all_skus 全部成功
3. 利润非零断言通过
4. MCP Chrome E2E 验证

## Verification Commands
python -m pytest tests/test_analysis_pipeline.py -x -q

## Branch
codex/TASK-002-5-integration-test

## Base Branch
main

## Parallel Safety
false

## Expected Output Artifacts
tests/test_analysis_pipeline.py
