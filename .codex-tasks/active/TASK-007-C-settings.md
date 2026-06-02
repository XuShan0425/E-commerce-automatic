<<<<<<< HEAD
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
=======
# TASK-007-C-settings — System Settings Enhancement

## Parent Epic

- Epic: `REP-007`
- Epic file: `docs/exec-plans/active/REP-007.md`

## Goal

Enhance the system settings page with collection frequency (scheduler interval) configuration capability.

## Scope

- Backend: Add `POST /system/global-stop` endpoint to manually toggle the global stop flag (complements the existing `POST /alerts/clear-stop` which only clears it).
- Backend: `POST /system/global-stop` accepts `{ "enabled": true/false }` and sets/clears global stop.
- Frontend: Add a global stop toggle switch in the Settings page, replacing the current read-only status display.
- Frontend: Add scheduler interval input in the Settings page's scheduler controls, passing the interval to `POST /scheduler/start`.
- Tests: Add test coverage for the new `/system/global-stop` endpoint.

## Allowed Files

- `App/api/v1/system.py`
- `frontend/src/pages/Settings.tsx`
- `tests/test_system_settings.py`
- `.codex-tasks/active/TASK-007-C-settings.md`

## Forbidden Files

- `App/models/`
- `App/services/alert_service.py`
- `App/services/boundary_checker.py`
- `App/services/execution_engine.py`
- `docs/`

## Acceptance Criteria

1. `POST /system/global-stop` with `{ "enabled": true }` sets global_stop in system_state.
2. `POST /system/global-stop` with `{ "enabled": false }` clears global_stop.
3. Frontend Settings page shows a toggle for global stop that calls the new endpoint.
4. Frontend Settings page includes an input for scheduler interval (minutes) when starting the scheduler.
5. `python -m pytest tests/test_system_settings.py -v` passes.

## Verification Commands

- `python -m pytest tests/test_system_settings.py -v`
- `python -m pytest tests/ -v --ignore=tests/test_stop_auto_pr.py`

## Branch

Branch: `codex/TASK-007-C-settings`

## Base Branch

Base branch: `main`

## Execution Notes

### Changes Made

1. **Backend - `App/api/v1/system.py`**:
   - Added `GlobalStopRequest` Pydantic model for request validation
   - Added `POST /system/global-stop` endpoint that accepts `{ "enabled": true/false }`
   - Creates or updates the `global_stop` key in `system_state` table
   - Logs the toggle action with reason "manual_toggle"
   - Requires API key authentication (via `verify_api_key` dependency)
   - Lint clean (ruff passes)

2. **Frontend - `frontend/src/pages/Settings.tsx`**:
   - Added global stop toggle button next to the global stop status badge
   - Added `handleGlobalStopToggle()` function calling `POST /system/global-stop`
   - Added `schedulerInterval` state (default 30) and input field before scheduler buttons
   - Updated `handleScheduler()` to pass `interval_minutes` query parameter
   - Added `globalStopToggling` state for loading indicator

3. **Tests - `tests/test_system_settings.py`**:
   - `TestGlobalStopRequest`: 2 tests for Pydantic model validation
   - `TestSetGlobalStop`: 3 async tests with mocked DB (new record, existing record, disable)
   - All tests use `unittest.mock` (no database dependency)

### Verification

- `python -m pytest tests/test_system_settings.py -v`: 5/5 passed
- `python -m ruff check App/api/v1/system.py`: All checks passed
- `python -m ruff check tests/test_system_settings.py`: All checks passed
- `python -m pytest tests/ -v --ignore=tests/test_stop_auto_pr.py`: passed (background, exit 0)

### Untracked / New Files

- `.codex-tasks/active/TASK-007-C-settings.md` (this file)
- `tests/test_system_settings.py`

### Modified Files

- `App/api/v1/system.py`
- `frontend/src/pages/Settings.tsx`
>>>>>>> origin/codex/task-007-c
