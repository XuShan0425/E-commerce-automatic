# EPIC-004 — 成本与费率初始化

## 目标

AI 解析物流/佣金页面 + 人工确认流程 + 商品成本录入界面。

## 架构

```
Product CRUD API ──────────────────────→ products 表
CSV 批量导入 ──────────────────────────→ products 表
Logistics Rates CRUD API ──────────────→ logistics_rates 表
Platform Fees CRUD API ────────────────→ platform_fees 表

Rate Parsing Workflow:
  定时/手动触发
      ↓
  Playwright 抓取帮助中心页面 HTML
      ↓
  Claude API 解析 HTML → 结构化数据
      ↓
  API 返回预览（未确认状态）
      ↓
  人工确认/编辑后调用 confirm 端点
      ↓
  写入 logistics_rates / platform_fees 表
```

## 任务拆分

| 编号 | 任务 | 说明 | 依赖 |
|------|------|------|------|
| TASK-001 | Claude API 客户端 | httpx 调用 Anthropic Messages API | 无 |
| TASK-002 | Schema 补充 | 解析结果/确认请求/CSV导入结果 Schema | 无 |
| TASK-003 | Products CRUD + CSV 导入 | 商品 CRUD + CSV 批量导入 | TASK-002 |
| TASK-004 | Logistics Rates CRUD | 物流费率 CRUD + 批量写入 | TASK-002 |
| TASK-005 | Platform Fees CRUD | 平台佣金 CRUD | TASK-002 |
| TASK-006 | 费率页面抓取服务 | Playwright 抓取帮助中心 HTML | 无 |
| TASK-007 | 费率 AI 解析编排 | scrape → parse → confirm | TASK-001, TASK-006 |
| TASK-008 | 费率解析 API 端点 | parse/confirm 端点 | TASK-007 |
| TASK-009 | 路由注册 + 文档 | 注册路由 + EPIC-004.md | TASK-003~008 |

## 验收标准

1. Products CRUD 完整可用（创建/读取/更新/删除）
2. CSV 批量导入：支持逗号/Tab分隔，自动检测编码(UTF-8/GBK)，逐行校验
3. Logistics Rates CRUD 完整可用，支持按 region 筛选
4. Platform Fees CRUD 完整可用
5. AI 解析管线：抓取页面 → Claude 解析 → 返回结构化预览
6. 确认工作流：确认后数据正确写入对应表
7. 所有端点需要 API Key 鉴权

## 新增 API 端点汇总

| Method | Path | Tag |
|--------|------|-----|
| GET/POST/PUT/DELETE | /api/v1/products/... | products |
| POST | /api/v1/products/import-csv | products |
| GET/POST/PUT/DELETE | /api/v1/logistics-rates/... | logistics-rates |
| POST | /api/v1/logistics-rates/batch | logistics-rates |
| GET/POST/PUT/DELETE | /api/v1/platform-fees/... | platform-fees |
| POST | /api/v1/rates/parse-logistics | rates |
| POST | /api/v1/rates/parse-fees | rates |
| POST | /api/v1/rates/confirm-logistics | rates |
| POST | /api/v1/rates/confirm-fees | rates |

## 新增服务模块

| 模块 | 功能 |
|------|------|
| App/services/ai_client.py | Claude API 客户端 (parse_html_to_json, parse_logistics_html, parse_fees_html) |
| App/services/rate_scraper.py | Playwright 页面抓取 (fetch_page_html, fetch_logistics_page, fetch_fees_page) |
| App/services/rate_parser.py | 编排服务 (parse_logistics_rates, parse_platform_fees, confirm_logistics_rates, confirm_platform_fees) |

## 分支策略

- Base Branch: `main`
- Feature Branch: `feature/epic-004-rates`
