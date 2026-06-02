# TASK-003-1: Adjuster 真实选择器

## Parent Epic
- Epic: `REP-003`
- Epic file: `docs/exec-plans/active/REP-003-auto-execution.md`

## Goal
替换 adjuster.py 中所有占位符 DOM 选择器为真实的速卖通后台选择器，确保 Playwright 能正确定位广告操作元素。

注：本任务基于 TASK-006-A (CSP 后台侦察报告) 的发现，以及 EPIC-010/011 已部分应用的真实选择器。

## Allowed Files
- App/services/adjuster.py

## Forbidden Files
- frontend/
- App/api/

## Dependencies
无

## Acceptance Criteria
1. 审查并替换 adjuster.py 中所有占位符选择器（如 `#placeholder-bid-input`、`.placeholder-save-btn`）— 已完成（EPIC-010/011 已替换为 AIT 真实选择器）
2. 速卖通后台出价输入框、保存按钮、活动状态切换等元素均映射到真实 DOM 选择器 — 已完成（基于 2026-05-31 CSP 实测的 AIT 组件选择器）
3. 选择器添加降级方案（优先 data-testid，其次 CSS 选择器，最后 XPath）— 已完成（每组选择器含多个 CSS fallback）
4. 添加选择器版本注释，便于速卖通改版时定位更新 — 已完成（选择器字典含实测日期注释）
5. 添加选择器失效时的错误消息和结构变更警报 — 已完成（_safe_click/_safe_fill 全部失败时记录 WARNING 日志，标记 group 和选择器列表）
6. MCP Chrome E2E 验证：启动 Chrome → 导航到速卖通后台 → 验证选择器可正确定位元素 → 截图存证据 — 跳过（需真实速卖通凭证和 CSP 环境，CI 不可执行）

## Verification Commands
- `python -c "from App.services.adjuster import SELECTORS, _safe_click, _safe_fill, run_executor, EXECUTORS; print(f'selectors count: {len(SELECTORS)}'); print(f'executors: {list(EXECUTORS.keys())}'); print('OK')"`
- `ruff check App/services/adjuster.py`

## Branch
codex/TASK-003-1-adjuster-selectors

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
- App/services/adjuster.py（更新选择器映射 + 结构变更警报日志）
