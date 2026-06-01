# TASK-001-api-interceptor

## Parent Epic

- Epic: `EPIC-003`
- Epic file: `docs/exec-plans/active/EPIC-003.md`

## Goal

实现 Playwright 网络请求拦截器，捕获速卖通卖家中心后台 API 的 JSON 响应，通过模式匹配识别广告数据和价格数据。

## Scope

- 创建 `App/services/api_interceptor.py`
  - `AdDataInterceptor` 类：注册到 Playwright page 上
  - 监听所有 `response` 事件，过滤 XHR/Fetch 类型
  - 识别 URL 模式（含 `gsp.aliexpress.com`、`/ad/`、`/campaign/` 等广告 API 特征）
  - 解析 JSON body
  - 通过字段名模式匹配检测是否含广告数据
  - 提取：sku_id, impressions, clicks, ctr, orders, conversion_rate, ad_spend, revenue, ad_type, buyer_region_breakdown
  - 提取价格：current_price
  - 返回结构化数据列表
- 创建 `App/schemas/collector.py` — `CollectedAdData`、`CollectedPriceData` 数据类

## Allowed Files

- `App/services/api_interceptor.py`
- `App/schemas/collector.py`
- `App/schemas/__init__.py`

## Forbidden Files

- `.codex/` 目录下的任何文件
- `App/models/`（只读参考）
- 已有 EPIC/TASK 文件

## Acceptance Criteria

- 拦截器能监听 `response` 事件并过滤出 API 调用
- 模式匹配器能从 JSON 中识别广告/价格相关字段（不依赖固定 URL，用字段名推断）
- 支持匹配多种字段命名方式（camelCase / snake_case / PascalCase）
- 至少支持识别这些字段：impressions, clicks, ctr, orders, ad_spend/spend/cost, revenue/sales, ad_type/campaignType
- 提取的数据包含原始响应 URL 和 timestamp，方便调试

## Verification Commands

- `python -c "from App.services.api_interceptor import AdDataInterceptor; print('OK')"`
- `ruff check App/services/api_interceptor.py App/schemas/collector.py`

## Branch

Branch: `codex/TASK-001-api-interceptor`

## Base Branch

Base branch: `main`
