# TASK-026-3: 系统服务化 — 启动器、热重启、日志

## Parent Epic
- Epic: `EPIC-026`
- Epic file: `docs/exec-plans/active/EPIC-026-legacy-features.md`

## Goal
将 feature/migrate-to-claude-code 分支中的系统服务化功能合入 main：一键启动器、开机自启、Web 热重启和日志接口。

## Allowed Files
- `scripts/start.py`
- `scripts/install-service.bat`
- `App/api/v1/system.py`

## Forbidden Files
- 不在 Allowed Files 列表中的任何文件

## Acceptance Criteria
- `python scripts/start.py` 可正常启动（语法通过）
- `scripts/install-service.bat` 存在
- `App/api/v1/system.py` 包含 `/restart` 和 `/logs` 端点
- 改动与 feature/migrate-to-claude-code 分支一致

## Verification Commands
- `python scripts/start.py --help`

## Branch
Branch: `codex/TASK-026-3-system-services`
Base branch: `main`
