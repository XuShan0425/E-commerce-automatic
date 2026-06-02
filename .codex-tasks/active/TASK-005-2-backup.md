# TASK-005-2: 备份/恢复

## Parent Epic
- Epic: `REP-005`
- Epic file: `docs/exec-plans/active/REP-005-production-infrastructure.md`

## Goal
实现自动 pg_dump 备份（保留 30 天）、一键恢复脚本、前端备份管理页面。

## Allowed Files
- scripts/backup.py（新建）
- scripts/restore.py（新建）
- frontend/src/pages/Backup.tsx（新建）

## Forbidden Files
- App/services/
- App/core/

## Dependencies
无

## Acceptance Criteria
1. scripts/backup.py 自动执行 pg_dump，备份文件按日期命名
2. 备份文件保留 30 天，超期自动清理
3. scripts/restore.py 支持一键恢复到指定备份点
4. 前端备份管理页面展示备份列表（时间、大小、状态）
5. 支持在前端触发备份和选择备份点恢复
6. 备份过程写操作日志
7. 备份文件存储路径可配置（环境变量）
8. MCP Chrome E2E 验证：启动 Chrome → 导航到备份管理 → 触发备份 → 确认备份列表更新 → 截图存证据

## Verification Commands
- `python scripts/backup.py --dry-run`
- `python scripts/restore.py --list`

## Branch
codex/TASK-005-2-backup

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
- scripts/backup.py（自动备份）
- scripts/restore.py（一键恢复）
- frontend 备份管理页面
