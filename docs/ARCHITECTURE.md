# 系统架构

> 最后更新: 2026-05-31 | 维护者: 人类工程师 + opencode

## 分层架构

```
┌────────────────────────────────────────────────┐
│                  Frontend (React 18)            │
│   Pages → Components → api/client.ts → REST    │
├────────────────────────────────────────────────┤
│              FastAPI Backend (:8000)            │
│                                                │
│  api/v1/  ← 路由层，只做参数解析和响应封装      │
│     ↓                                          │
│  services/  ← 业务逻辑层，编排各个能力          │
│     ↓                                          │
│  models/  ← ORM 模型，对应 PostgreSQL 表        │
│     ↓                                          │
│  schemas/  ← Pydantic 模型，API 请求/响应结构   │
│     ↓                                          │
│  core/  ← 基础设施：配置、数据库、鉴权、错误码  │
├────────────────────────────────────────────────┤
│              PostgreSQL 14+                     │
│  10 张表 (见 docs/generated/db-schema.md)       │
├────────────────────────────────────────────────┤
│          外部依赖                               │
│  Playwright (Chromium)  │  Redis 6+            │
│  Anthropic Messages API │  Gmail SMTP          │
└────────────────────────────────────────────────┘
```

## 依赖方向（强制规则）

```
api/v1/  →  services/  →  models/  +  schemas/
                ↓
            core/  (只被 services/ 和 api/ 依赖, 不依赖它们)
```

**禁止的依赖**:
- `models/` import `services/` 或 `api/`
- `schemas/` import `services/` 或 `api/`
- `core/` import `services/` 或 `api/`（`core/security.py` 的延迟导入除外）
- `services/` import `api/`

这些规则由 `scripts/lints/check-architecture.py` 机械强制执行。

## 模块清单

### core/ — 基础设施

| 文件 | 职责 |
|------|------|
| `config.py` | Pydantic Settings, .env 加载, 所有配置项 |
| `database.py` | SQLAlchemy async engine, session factory, Base 类 |
| `security.py` | API Key 验证、生成、哈希, FastAPI 依赖注入 |
| `errors.py` | ErrorCode 枚举、`error_response()` 统一错误格式 |

### models/ — 数据表 (ORM)

| 文件 | 表 | 关键字段 |
|------|-----|---------|
| `base.py` | `products`, `logistics_rates`, `platform_fees`, `ad_snapshots`, `price_snapshots`, `profit_analysis` | SKU ID, ROI, 成本 |
| `auth.py` | `api_keys` | key_hash (SHA-256), is_active |
| `alert.py` | `alerts` | alert_type, severity, is_resolved |
| `cookie.py` | `cookie_store` | cookies_json, health_status |
| `system_state.py` | `system_state` | global_stop, last_login_at |
| `operation_log.py` | `operation_logs` | action_type, status, details_json |

### services/ — 业务逻辑

| 文件 | 职责 | 关键函数 |
|------|------|---------|
| `browser.py` | Playwright 实例管理, stealth 注入 | `BrowserService.new_context()` |
| `stealth.py` | 反检测 JS 脚本 | `STEALTH_JS` (常量) |
| `login_flow.py` | 速卖通登录流程 (Playwright) | `perform_login()` |
| `cookie_manager.py` | Cookie 持久化/加载 | `save_cookies()`, `load_cookies()` |
| `cookie_health.py` | Cookie 有效性检测 | `check_health()` |
| `api_interceptor.py` | 拦截速卖通广告 API 响应 | `intercept_ad_responses()` |
| `data_collector.py` | 采集编排 — 登录/拦截/保存 | `run_collection()` |
| `product_scraper.py` | 店铺商品页面抓取 | `extract_products()` |
| `adjuster.py` | Playwright 操作执行 — 调价/暂停 | DOM 选择器字典 |
| `scheduler.py` | APScheduler 定时任务管理 | `init_scheduler()`, `start()`, `stop()` |
| `profit_calculator.py` | 利润 = 售价 - 成本 - 物流 - 佣金 | `calculate_profit()` |
| `decision_engine.py` | AI prompt 构建 → LLM 调用 → 决策解析 | `analyze_single_sku()` |
| `boundary_checker.py` | 硬/软边界验证 (5+2 种) | `check_boundaries()` |
| `execution_engine.py` | 决策 → 边界检查 → dispatch → 日志 | `execute_decision()` |
| `analysis_pipeline.py` | 采集 → 利润 → AI → 执行 全流水线 | `run_pipeline()` |
| `operation_logger.py` | 操作日志写入/更新 | `log_operation()` |
| `alert_service.py` | 警报创建/查询/解决 | `raise_alert()` |
| `email_notifier.py` | SMTP 邮件发送 (含 SOCKS5 代理) | `send_email()` |
| `ai_client.py` | Anthropic Messages API 客户端 | `_call_claude()` |
| `rate_scraper.py` | 物流/佣金费率页面抓取 | |
| `rate_parser.py` | AI 解析费率 HTML → 结构化数据 | |

### api/v1/ — HTTP 路由

| 文件 | 端点前缀 | 关键端点 |
|------|---------|---------|
| `health.py` | `/health` | `GET /`, `GET /db` |
| `auth.py` | `/api-keys` | CRUD API Key |
| `auth_flow.py` | `/login` | 登录流程触发 |
| `alerts.py` | `/alerts` | 警报 CRUD + stop/restart |
| `collect.py` | `/collect` | `POST /run` |
| `scheduler_api.py` | `/scheduler` | `POST /start`, `/stop`, `/status` |
| `system.py` | `/system` | `GET /status` |
| `products.py` | `/products` | CRUD + CSV import |
| `store_products.py` | `/store-products` | `POST /fetch` |
| `logistics_rates.py` | `/logistics-rates` | CRUD |
| `platform_fees.py` | `/platform-fees` | CRUD |
| `rate_parsing.py` | `/rates` | AI 解析 |
| `analysis.py` | `/analysis` | `POST /run` |
| `execution.py` | `/execution` | `POST /run` |

## 数据流

### 采集 → 分析 → 执行 主循环

```
1. POST /collect/run
   → scheduler.py 触发
   → login_flow.py (如果需要)
   → browser.py 创建 context + 注入 stealth
   → api_interceptor.py 拦截广告 API 响应
   → data_collector.py 解析 → 写入 ad_snapshots + price_snapshots

2. POST /analysis/run
   → analysis_pipeline.py
   → profit_calculator.py (计算利润)
   → decision_engine.py (AI 决策)
   → boundary_checker.py (边界验证)
   → profit_analysis 写入数据库

3. POST /execution/run
   → execution_engine.py
   → boundary_checker.py (二次验证)
   → adjuster.py (Playwright 操作)
   → operation_logger.py (记录操作)
   → alert_service.py (异常时告警)
```

## 技术栈版本

| 组件 | 版本 |
|------|------|
| FastAPI | 0.115+ |
| SQLAlchemy (async) | 2.0+ |
| PostgreSQL | 14+ |
| Redis | 6+ |
| Playwright | 1.51+ |
| React | 18.3 |
| TypeScript | 5.6 |
| Vite | 6.0 |
| Tailwind CSS | 3.4 |
| APScheduler | 3.10+ |
| Ruff | 0.9+ |
