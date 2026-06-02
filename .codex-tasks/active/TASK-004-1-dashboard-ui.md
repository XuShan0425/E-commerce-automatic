# TASK-004-1: Dashboard 前端重构

## Parent Epic
- Epic: `REP-004`
- Epic file: `docs/exec-plans/active/REP-004-operator-console.md`

## Goal
重构 Dashboard 前端，ROI 趋势图 (Recharts)、SKU 选择器、警报摘要卡片、消费 REP-002 的 /api/v1/dashboard/aggregate API。

## Allowed Files
- frontend/src/pages/Dashboard.tsx
- frontend/src/components/

## Forbidden Files
- App/

## Dependencies
无

## Acceptance Criteria
1. Dashboard 显示 ROI 趋势折线图
2. SKU 下拉选择器
3. 警报摘要卡片（未处理数量 + 严重度分布）
4. MCP Chrome E2E 验证：导航 Dashboard 验证组件渲染

## Verification Commands
cd frontend && npx tsc --noEmit

## Branch
codex/TASK-004-1-dashboard-ui

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
修改后的 Dashboard.tsx
