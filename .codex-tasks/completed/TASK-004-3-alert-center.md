# TASK-004-3-alert-center

## Parent Epic

- REP-004: Alert Center (警报中心)

## Goal

实现警报中心前端页面：展示未处理警报列表，提供软边界确认操作入口，支持标记已处理、清除全局停止等功能。

## Scope

- 完善 `App/api/v1/alerts.py` — 警报查询端点（lint 修复）
- 完善 `App/services/alert_service.py` — 警报服务（lint 修复：datetime.UTC, is_(False)）
- 已有 `frontend/src/pages/Alerts.tsx` — 警报中心页面（警报列表 + 待确认操作标签页）
- 已有 `App/models/alert.py` — Alert 模型
- 已有 `App/schemas/alert.py` — Alert schemas

## Allowed Files

- `frontend/src/pages/Alerts.tsx`
- `App/api/v1/alerts.py`
- `App/services/alert_service.py`
- `App/models/alert.py`
- `App/schemas/alert.py`

## Forbidden Files

- `.codex/` 目录下的任何文件
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- 警报中心页面可访问，显示未处理警报列表
- 支持标记警报为已处理
- 支持清除全局停止标志
- 待确认操作列表展示软边界暂停的决策
- 支持确认/拒绝待确认操作
- 所有 lint 检查通过

## Verification Commands

- `ruff check App/services/alert_service.py App/api/v1/alerts.py`
- `python -c "from App.services.alert_service import raise_alert, get_active_alerts; print('OK')"`
- `python -c "from App.api.v1.alerts import router; print('OK')"`

## Branch

Branch: `codex/TASK-004-3-alert-center`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
