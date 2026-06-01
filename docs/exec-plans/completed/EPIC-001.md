# EPIC-001 — 项目基础设施

## 目标

搭建项目的完整基础设施：Docker Compose 环境、PostgreSQL 数据库初始化、FastAPI 项目骨架和基础鉴权。这是后续所有 EPIC 的依赖基础。

## 范围

| 编号 | 任务 | 说明 |
|------|------|------|
| TASK-001 | Docker Compose + 数据库初始化 | docker-compose.yml、PostgreSQL 建表脚本、Redis 服务 |
| TASK-002 | FastAPI 项目骨架 | 目录结构、配置管理（pydantic-settings）、依赖注入、项目入口 |
| TASK-003 | SQLAlchemy 数据库模型 | 所有数据表的 ORM 模型定义（products, ad_snapshots, profit_analysis 等） |
| TASK-004 | 基础鉴权 | API Key 认证、用户/密钥管理、认证依赖注入 |

## 技术栈

- **后端框架**: FastAPI (Python)
- **数据库**: PostgreSQL + SQLAlchemy (async) + Alembic
- **容器**: Docker Compose
- **配置**: pydantic-settings + .env
- **鉴权**: API Key（Header 传参）

## 项目结构（目标）

```
project-root/
├── App/
│   ├── api/              # API 路由
│   │   ├── __init__.py
│   │   └── v1/           # API v1 路由
│   ├── core/             # 核心模块
│   │   ├── config.py     # 配置管理
│   │   ├── security.py   # 鉴权
│   │   └── database.py   # 数据库连接
│   ├── models/           # SQLAlchemy 模型
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # 业务逻辑
│   ├── main.py           # FastAPI 入口
│   └── __init__.py
├── db/                   # 数据库脚本
│   └── init.sql          # 初始化建表 SQL
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## 依赖关系

- **TASK-001** (Docker Compose + DB) → 无依赖，最先执行
- **TASK-002** (FastAPI 骨架) → 依赖 TASK-001（需要数据库环境做本地测试）
- **TASK-003** (SQLAlchemy 模型) → 依赖 TASK-002（在 FastAPI 项目结构内定义）
- **TASK-004** (基础鉴权) → 依赖 TASK-002（在 FastAPI 中注册）

## 验收标准

1. `docker-compose up -d` 后 PostgreSQL 和 Redis 正常启动
2. 数据库初始化脚本执行后，所有表创建成功
3. FastAPI 项目可以启动，访问 `/health` 返回 200
4. SQLAlchemy 模型定义与 CLAUDE.md 的数据模型一致
5. 带有效 API Key 的请求可以通过鉴权，无效 Key 返回 401
6. 所有 TASK 都有对应的验证命令（pytest / ruff）

## 分支策略

- 每个 TASK 使用独立的 `codex/TASK-xxx` 分支
- Base Branch: `main`
- 完成后通过 PR 合并

## 参考文档

- `project/CLAUDE.md` — 完整项目规范和数据模型
