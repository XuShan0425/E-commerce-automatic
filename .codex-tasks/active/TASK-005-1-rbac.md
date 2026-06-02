# TASK-005-1: 多用户 + RBAC

## Parent Epic
- Epic: `REP-005`
- Epic file: `docs/exec-plans/active/REP-005-production-infra.md`

## Goal
JWT 登录/注册 API、角色权限系统、API 级权限检查、前端路由守卫

## Allowed Files
- App/api/v1/auth.py
- App/models/auth.py
- App/services/auth_service.py (new)
- frontend/src/pages/Settings.tsx
- App/core/security.py

## Forbidden Files
- db/init.sql

## Dependencies
无

## Acceptance Criteria
1. JWT 登录/注册 API 工作正常
2. 角色权限系统 (管理员/运营者)
3. API 级权限检查
4. 前端路由守卫
5. MCP Chrome E2E 验证：登录不同账号验证权限隔离

## Verification Commands
python -c "from App.services.auth_service import AuthService; print('ok')"

## Branch
codex/TASK-005-1-rbac

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
auth_service.py, 修改后的 auth.py, security.py
