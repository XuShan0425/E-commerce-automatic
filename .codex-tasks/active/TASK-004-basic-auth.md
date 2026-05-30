# TASK-004-basic-auth

## Parent Epic

- Epic: `EPIC-001`
- Epic file: `docs/exec-plans/active/EPIC-001.md`

## Goal

实现基础鉴权系统：API Key 认证机制，确保所有 API 端点（除健康检查外）都需要有效认证。

## Scope

- 创建 `App/core/security.py` — API Key 验证逻辑
- 创建 API Key 存储模型（数据库表 `api_keys`）
- 创建 FastAPI 认证依赖注入（`get_current_user` / `verify_api_key`）
- 创建 API Key 管理端点（生成/吊销密钥，仅限管理员）
- 注册认证中间件到 FastAPI 应用
- 公开端点（如 `/health`）免鉴权配置

## Allowed Files

- `App/core/security.py`
- `App/models/`（追加 `ApiKey` 模型）
- `App/schemas/`（追加 ApiKey schemas）
- `App/api/v1/auth.py`（认证相关路由）
- `App/api/v1/__init__.py`（注册 auth router）
- `docker-compose.yml`（可追加环境变量）
- `.env.example`（追加 `ADMIN_API_KEY`）

## Forbidden Files

- `.codex/` 目录下的任何文件
- `App/services/` 和 `App/api/v1/` 下的非认证路由
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- 请求头 `X-API-Key: <valid_key>` 可通过鉴权
- 无 Key 或无效 Key 的请求返回 `401 Unauthorized`
- `/health` 端点免鉴权
- API Key 存储在数据库中，支持多 Key 共存
- 支持管理员生成和吊销 API Key
- 所有操作使用 async 数据库会话

## Verification Commands

- `python -c "from App.core.security import verify_api_key; print('OK')"`
- `python -c "from App.models import ApiKey; print('OK')"`
- `ruff check App/core/security.py App/api/v1/auth.py`
- 启动服务后手动测试：`curl -H "X-API-Key: test" http://localhost:8000/health`

## Branch

Branch: `codex/TASK-004-basic-auth`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
