# TASK-002-fastapi-skeleton

## Parent Epic

- Epic: `EPIC-001`
- Epic file: `docs/exec-plans/active/EPIC-001.md`

## Goal

搭建 FastAPI 项目骨架：目录结构、配置管理、数据库连接和项目入口，为后续业务开发提供基础框架。

## Scope

- 在 `App/` 下创建项目目录结构
- 创建 `App/main.py` — FastAPI 应用入口（app factory 模式）
- 创建 `App/core/config.py` — pydantic-settings 配置管理（从 .env 读取）
- 创建 `App/core/database.py` — SQLAlchemy async engine + session 管理
- 创建 `App/api/v1/` — API 路由注册（含 `/health` 健康检查端点）
- 创建 `App/__init__.py` 和子模块的 `__init__.py`
- 配置 CORS 中间件
- 配置生命周期事件（启动/关闭时连接/断开数据库）

## Allowed Files

- `App/` 目录下的所有文件
- `docker-compose.yml`（可修改以映射 volume）
- `requirements.txt`（可追加依赖）
- `pyproject.toml`（如需要）

## Forbidden Files

- `.codex/`目录下的任何文件
- `App/models/`（TASK-003 的范围）
- `App/core/security.py`（TASK-004 的范围）
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- `uvicorn App.main:app --reload` 启动后 `/health` 返回 `{"status": "ok"}`
- 配置从 `.env` 和环境变量读取，有合理的默认值
- 项目结构符合 EPIC-001.md 中定义的目录布局
- 支持异步数据库连接（asyncpg）
- `docker-compose up -d` 后 app 服务能正常启动并连接到数据库

## Verification Commands

- `python -c "from App.main import app; print('OK')"`
- `python -c "from App.core.config import settings; print(settings.model_dump())"`
- `python -c "from App.core.database import engine; print('OK')"`
- `ruff check App/`

## Branch

Branch: `codex/TASK-002-fastapi-skeleton`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
