# TASK-008-C: 投资组合优化

## Parent Epic
- Epic: `REP-008`
- Epic file: `docs/exec-plans/active/REP-008-ai-evolution.md`

## Goal
跨 SKU 预算重新分配优化

## Allowed Files
- App/services/portfolio_optimizer.py (new)
- App/services/decision_engine.py

## Forbidden Files
- App/models/

## Dependencies
TASK-008-A

## Acceptance Criteria
1. 组合优化输出非空推荐
2. 约束: 单 SKU 不超过 20%
3. MCP Chrome E2E 验证

## Verification Commands
python -c "from App.services.portfolio_optimizer import PortfolioOptimizer; print('ok')"

## Branch
codex/TASK-008-C-portfolio

## Base Branch
codex/TASK-008-A-feedback-loop

## Parallel Safety
true (可与 008-B 并行)

## Expected Output Artifacts
portfolio_optimizer.py
