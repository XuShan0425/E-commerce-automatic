# TASK-026-4: 产品分析模块

## Parent Epic
- Epic: `EPIC-026`
- Epic file: `docs/exec-plans/active/EPIC-026-legacy-features.md`

## Goal
将 feature/migrate-to-claude-code 分支中的产品分析模块合入 main：数据模型、导入模型和分析服务。

## Allowed Files
- `App/models/product_analytics.py`
- `App/models/product_import.py`
- `App/services/product_analytics_service.py`
- `App/models/__init__.py`

## Forbidden Files
- 不在 Allowed Files 列表中的任何文件

## Acceptance Criteria
- 3 个新文件创建成功
- `App/models/__init__.py` 注册新模型
- 内容与 feature/migrate-to-claude-code 分支一致

## Branch
Branch: `codex/TASK-026-4-product-analytics`
Base branch: `main`
