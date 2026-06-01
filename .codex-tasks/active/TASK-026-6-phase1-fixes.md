# TASK-026-6: Phase 1 修复 + 缓存服务

## Parent Epic
- Epic: `EPIC-026`
- Epic file: `docs/exec-plans/active/EPIC-026-legacy-features.md`

## Goal
将 feature/migrate-to-claude-code 分支中的 Phase 1 修复和缓存服务合入 main：SKU 并发分析、错误修复、前端提示改进和 Redis 缓存。

## Allowed Files
- `App/services/analysis_pipeline.py`
- `App/services/product_scraper.py`
- `App/services/cache_service.py`
- `frontend/src/pages/Settings.tsx`
- `requirements.txt`

## Forbidden Files
- 不在 Allowed Files 列表中的任何文件

## Acceptance Criteria
- `analysis_pipeline.py` 使用 `asyncio.gather` + `Semaphore(5)` 并行
- `product_scraper.py` 移除静默 `except Exception: pass`
- `cache_service.py` 包含 get/set/delete/clear_pattern
- `Settings.tsx` `catch {}` 改为显示错误提示
- `requirements.txt` 启用 redis

## Verification Commands
- `python -c "import ast; ast.parse(open('App/services/analysis_pipeline.py').read()); ast.parse(open('App/services/product_scraper.py').read()); ast.parse(open('App/services/cache_service.py').read())"`

## Branch
Branch: `codex/TASK-026-6-phase1-fixes`
Base branch: `main`
