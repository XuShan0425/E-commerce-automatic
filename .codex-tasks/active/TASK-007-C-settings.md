# TASK-007-C: 系统设置面板

## Parent Epic
- Epic: `REP-007`
- Epic file: `docs/exec-plans/active/REP-007-data-features.md`

## Goal
实现 system_config 表、KV 持久化服务、设置 API、前端设置页面

## Allowed Files
- App/services/system_config_service.py (new)
- App/api/v1/system.py
- App/core/config.py
- frontend/src/pages/Settings.tsx

## Forbidden Files
- db/init.sql

## Dependencies
无

## Acceptance Criteria
1. system_config 持久化工作，重启保留
2. 前端设置页可以读取/写入配置
3. MCP Chrome E2E 验证

## Verification Commands
python -c "from App.services.system_config_service import SystemConfigService; print('ok')"

## Branch
codex/TASK-007-C-settings

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
system_config_service.py, Settings.tsx
