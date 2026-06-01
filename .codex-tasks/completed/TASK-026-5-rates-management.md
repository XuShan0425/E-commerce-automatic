# TASK-026-5: 费率管理前端 + 费率解析服务

## Parent Epic
- Epic: `EPIC-026`
- Epic file: `docs/exec-plans/active/EPIC-026-legacy-features.md`

## Goal
将 feature/migrate-to-claude-code 分支中的费率管理功能合入 main：费率管理页面、前端路由、requests 版费率解析服务和错误处理。

## Allowed Files
- `frontend/src/pages/RatesSettings.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`
- `App/services/rate_parser_service.py`
- `App/api/v1/rate_parsing.py`
- `App/core/errors.py`

## Forbidden Files
- 不在 Allowed Files 列表中的任何文件

## Acceptance Criteria
- 费率管理页面 `RatesSettings.tsx` 创建成功
- 前端路由配置了 `/rates-settings` 路径
- 费率解析服务 `rate_parser_service.py` 创建成功
- `rate_parsing.py` 包含新版端点（logistics/fetch, commission/fetch）
- `errors.py` 新增错误处理
- 改动与 feature/migrate-to-claude-code 分支一致

## Branch
Branch: `codex/TASK-026-5-rates-management`
Base branch: `main`
