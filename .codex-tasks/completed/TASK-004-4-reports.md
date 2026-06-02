# TASK-004-4-reports

## Parent Epic

- Epic: `EPIC-008`
- Epic file: `docs/exec-plans/active/EPIC-008.md`

## Goal

实现报告生成系统：当边界条件触发时，自动生成 ROI 连续为负分析报告和推广活动关闭说明，并提供报告查询 API。

## Scope

- 创建 `App/services/report_service.py` — 报告生成服务
  - `generate_roi_negative_report(db, sku_id)` — 生成 ROI 连续为负分析报告
  - `generate_campaign_close_report(db, sku_id, reason, summary)` — 生成推广活动关闭说明
  - `get_report(db, report_id)` — 获取单个报告
  - `list_reports(db, sku_id, report_type, limit)` — 按条件查询报告
- 创建 `App/models/report.py` — `Report` 模型
  - 字段：id, sku_id, report_type (roi_negative / campaign_close), title, content (JSONB), created_at
- 创建 `App/schemas/report.py` — Report schemas
- 创建 `App/api/v1/reports.py` — 报告查询端点
  - `GET /api/v1/reports` — 获取报告列表（支持按 sku_id / report_type 筛选）
  - `GET /api/v1/reports/{report_id}` — 获取单个报告详情
- 更新 `App/models/__init__.py`、`App/schemas/__init__.py`、`App/api/v1/__init__.py`

## Allowed Files

- `App/services/report_service.py`
- `App/models/report.py`
- `App/schemas/report.py`
- `App/api/v1/reports.py`
- `App/api/v1/__init__.py`
- `App/models/__init__.py`
- `App/schemas/__init__.py`

## Forbidden Files

- `.codex/` 目录下的任何文件
- 已有的 EPIC/TASK 文件
- 核心业务逻辑（profit_calculator, decision_engine, boundary_checker）

## Acceptance Criteria

- ROI 连续为负时，报告包含：近 7 天 ROI 趋势数据、每日广告花费 vs 收入对比、各地区转化率分布、AI 推断的可能原因、建议的人工干预方向
- 推广活动关闭说明包含：活动完整数据摘要、关闭理由、预计影响（流量减少估算）、替代方案建议
- 报告以 JSONB 格式存储，内容可被前端直接消费
- `GET /api/v1/reports` 返回报告列表，支持按 sku_id 和 report_type 筛选
- `GET /api/v1/reports/{id}` 返回单个报告完整内容
- 所有端点需要鉴权

## Verification Commands

- `python -c "from App.services.report_service import generate_roi_negative_report, generate_campaign_close_report, get_report, list_reports; print('OK')"`
- `python -c "from App.models.report import Report; print('OK')"`
- `python -c "from App.api.v1.reports import router; print('OK')"`
- `ruff check App/services/report_service.py App/models/report.py App/api/v1/reports.py App/schemas/report.py`

## Branch

Branch: `codex/TASK-004-4-reports`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并

---

## 执行摘要

### 创建的文件

| 文件 | 用途 |
|------|------|
| `App/models/report.py` | Report ORM 模型 — reports 表（id, sku_id, report_type, title, content JSONB, created_at） |
| `App/schemas/report.py` | Pydantic schemas — ReportRead（完整内容）、ReportListItem（列表摘要） |
| `App/services/report_service.py` | 报告生成服务 — `generate_roi_negative_report`/`generate_campaign_close_report`/`get_report`/`list_reports` |
| `App/api/v1/reports.py` | 报告查询端点 — `GET /api/v1/reports`（列表+筛选）、`GET /api/v1/reports/{id}`（详情） |

### 修改的文件

| 文件 | 变更 |
|------|------|
| `App/models/__init__.py` | 注册 Report 模型 |
| `App/schemas/__init__.py` | 注册 ReportListItem / ReportRead schema |
| `App/api/v1/__init__.py` | 注册 reports 路由 |

### 验收状态

- [x] `generate_roi_negative_report` — 生成含 ROI 趋势、花费 vs 收入、地区转化、原因推断、建议行动的完整报告
- [x] `generate_campaign_close_report` — 生成含活动摘要、关闭理由、流量影响估算、替代方案的报告
- [x] 报告以 JSONB 格式存入 `reports` 表，可直接供前端消费
- [x] `GET /api/v1/reports` — 支持 `sku_id` 和 `report_type` 筛选
- [x] `GET /api/v1/reports/{id}` — 返回单个报告完整 JSONB 内容
- [x] 所有端点通过 `verify_api_key` 鉴权
- [x] lint 通过（ruff 0 errors）
- [x] 所有模块导入验证通过
