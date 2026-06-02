# TASK-007-B: 联盟营销

## Parent Epic
- Epic: `REP-007`
- Epic file: `docs/exec-plans/active/REP-007-data-features.md`

## Goal
采集联盟广告数据（推广商品、佣金率、效果数据），实现联盟数据采集和展示

## Allowed Files
- App/services/api_interceptor.py
- App/services/data_collector.py
- App/services/affiliate_collector.py (new)
- frontend/src/pages/Affiliate.tsx

## Forbidden Files
- App/models/

## Dependencies
无

## Acceptance Criteria
1. 联盟广告数据采集工作
2. 联盟数据展示
3. MCP Chrome E2E 验证

## Verification Commands
python -c "from App.services.affiliate_collector import AffiliateCollector; print('ok')"

## Branch
codex/TASK-007-B-affiliate

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
affiliate_collector.py, Affiliate.tsx
