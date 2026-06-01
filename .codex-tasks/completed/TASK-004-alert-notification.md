# TASK-004-alert-notification

## Parent Epic

- Epic: `EPIC-002`
- Epic file: `docs/exec-plans/active/EPIC-002.md`

## Goal

实现警报通知服务：当 Cookie 失效等异常事件发生时，自动写入警报日志、设置全局停止标志，并提供警报查询端点。

## Scope

- 创建 `App/services/alert_service.py` — 警报服务
  - `raise_alert(alert_type, message, severity)` — 写入警报记录 + 设置全局停止标志（如果是 critical）
  - `resolve_alert(alert_id)` — 标记警报为已处理
  - `get_active_alerts()` — 获取所有未处理警报
- 创建 `App/models/alert.py` — `Alert` 模型
  - 字段：id, alert_type, severity (critical/warning/info), message, is_resolved, created_at, resolved_at
- 创建 `App/schemas/alert.py` — Alert schemas
- 创建 `App/api/v1/alerts.py` — 警报查询端点
  - `GET /api/v1/alerts` — 获取未处理警报列表
  - `POST /api/v1/alerts/{alert_id}/resolve` — 手动标记已处理
- 更新 `App/models/__init__.py`、`App/schemas/__init__.py`、`App/api/v1/__init__.py`

## Allowed Files

- `App/services/alert_service.py`
- `App/models/alert.py`
- `App/schemas/alert.py`
- `App/api/v1/alerts.py`
- `App/api/v1/__init__.py`
- `App/models/__init__.py`
- `App/schemas/__init__.py`

## Forbidden Files

- `.codex/` 目录下的任何文件
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- Cookie 失效时（TASK-002 调用 `raise_alert`），自动生成一条 `critical` 级别的警报
- 警报写入 `alerts` 表，包含类型、严重级别、消息、时间戳
- `GET /api/v1/alerts` 返回所有未处理警报
- `POST /api/v1/alerts/{id}/resolve` 标记警报为已处理
- 全局停止标志 `SystemState(global_stop=true)` 在 critical 警报触发时自动设置
- 所有端点需要鉴权

## Verification Commands

- `python -c "from App.services.alert_service import raise_alert, get_active_alerts; print('OK')"`
- `python -c "from App.models.alert import Alert; print('OK')"`
- `python -c "from App.api.v1.alerts import router; print('OK')"`
- `ruff check App/services/alert_service.py App/models/alert.py App/api/v1/alerts.py`

## Branch

Branch: `codex/TASK-004-alert-notification`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
