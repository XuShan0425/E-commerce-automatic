# TASK-007-A: 竞品数据

## Parent Epic

- Epic: `REP-007`
- Epic file: `docs/exec-plans/active/REP-007-data-features.md`

## Goal

检查 CSP 后台竞品数据可导出性，被动从推荐 API 提取竞品数据，为竞品对比分析提供数据基础。

## Scope

1. **CSP 后台侦察**：浏览器遍历 CSP 后台竞品相关页面，确认哪些竞品数据可导出以及导出格式（CSV/XLSX/PDF/无）
2. **API 拦截增强**：在 `App/services/api_interceptor.py` 中识别推荐接口中的竞品数据响应路径，被动提取竞品信息
3. **数据收集**：在 `App/services/data_collector.py` 中实现竞品数据采集逻辑
4. **API 端点**：新增 `App/api/v1/competitors.py`，提供竞品数据查询接口

## Allowed Files

- `App/services/api_interceptor.py`
- `App/services/data_collector.py`
- `App/api/v1/competitors.py` (new)
- `frontend/src/pages/Competitors.tsx`

## Forbidden Files

无

## Dependencies

无

## Acceptance Criteria

1. CSP 竞品数据导出能力已确认并记录
2. 推荐 API 响应中的竞品数据能被动提取并结构化
3. 竞品数据 API 端点正常返回数据
4. 前端竞品页面展示基础数据
5. MCP Chrome E2E 验证：浏览器打开 CSP 相关页面 → 触发采集 → 查看 API 响应 → 验证竞品字段完整 → 截图存证据

## Verification Commands

```bash
python -m pytest tests/test_competitors.py -v
python scripts/lints/run-all.py
```

## Branch

codex/TASK-007-A-competitor

## Base Branch

main

## Parallel Safety

true

## Expected Output Artifacts

- CSP 竞品数据导出能力报告
- 修改后的 `api_interceptor.py` 和 `data_collector.py`
- 新增 `App/api/v1/competitors.py`
- 新增 `frontend/src/pages/Competitors.tsx`
- MCP Chrome E2E 截图存 `.codex-runs/`
