# TASK-003-sqlalchemy-models

## Parent Epic

- Epic: `EPIC-001`
- Epic file: `docs/exec-plans/active/EPIC-001.md`

## Goal

基于 `project/CLAUDE.md` 的数据模型定义，创建完整的 SQLAlchemy ORM 模型和 Alembic 迁移配置。

## Scope

- 在 `App/models/` 下创建所有 ORM 模型：
  - `Product`（products 表）
  - `LogisticsRate`（logistics_rates 表）
  - `PlatformFee`（platform_fees 表）
  - `AdSnapshot`（ad_snapshots 表）
  - `PriceSnapshot`（price_snapshots 表）
  - `ProfitAnalysis`（profit_analysis 表）
- 创建 `App/models/__init__.py`（导出所有模型 + Base）
- 创建 `App/schemas/` — Pydantic schemas（创建/读取/更新）
- 配置 Alembic（生成初始迁移）
- 配置 `sku_id + snapshot_time` 联合索引

## Allowed Files

- `App/models/`
- `App/schemas/`
- `alembic.ini`
- `alembic/`
- `App/core/database.py`（可追加 Base 声明）
- `requirements.txt`（可追加依赖）

## Forbidden Files

- `.codex/` 目录下的任何文件
- `App/api/`（TASK-002 范围，非本次）
- `App/core/security.py`（TASK-004 范围）
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- 所有模型字段与 `project/CLAUDE.md` 的数据模型完全一致
- 模型使用 SQLAlchemy 2.0 声明方式（`mapped_column`）
- `sku_id + snapshot_time` 联合索引已配置
- 支持 async session（AsyncAttrs mixin）
- Alembic 可以生成迁移文件
- Pydantic schemas 包含创建和读取的序列化/反序列化

## Verification Commands

- `python -c "from App.models import Product, AdSnapshot, ProfitAnalysis; print('OK')"`
- `python -c "from App.schemas import ProductCreate, ProductRead; print('OK')"`
- `alembic check`（检查模型与数据库同步状态）
- `alembic revision --autogenerate -m 'init' && alembic upgrade head`
- `ruff check App/models/ App/schemas/`

## Branch

Branch: `codex/TASK-003-sqlalchemy-models`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
