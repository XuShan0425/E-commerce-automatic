# TASK-001-playwright-cookie-storage

## Parent Epic

- Epic: `EPIC-002`
- Epic file: `docs/exec-plans/active/EPIC-002.md`

## Goal

搭建 Playwright 自动化环境，创建 Cookie 数据模型和持久化存储服务，为后续的健康检查和登录流程提供基础。

## Scope

- 在 `requirements.txt` 追加 `playwright` 依赖
- 创建 `App/services/browser.py` — Playwright 浏览器实例管理（启动/关闭/上下文创建）
- 创建 `App/services/cookie_manager.py` — Cookie 的存储、读取、序列化/反序列化
- 创建 `App/models/cookie.py` — `CookieStore` 数据模型
- 创建 `App/schemas/cookie.py` — Cookie 相关 Pydantic schemas
- 更新 `App/models/__init__.py` 和 `App/schemas/__init__.py`
- 创建 `App/services/__init__.py`

## Allowed Files

- `App/services/`
- `App/models/cookie.py`
- `App/schemas/cookie.py`
- `App/models/__init__.py`
- `App/schemas/__init__.py`
- `requirements.txt`

## Forbidden Files

- `.codex/` 目录下的任何文件
- `App/api/`（TASK-003 范围）
- `App/core/` 已有文件（只读参考）
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- `playwright` 已安装，`python -c "from playwright.sync_api import sync_playwright"` 通过
- `CookieStore` 模型包含字段：id, domain, cookies_json (JSONB), created_at, updated_at, is_valid
- `cookie_manager.py` 提供 `save_cookies(domain, cookies)` 和 `load_cookies(domain)` 方法
- `browser.py` 提供 `create_context_with_cookies()` 方法：自动加载已保存的 Cookie 到浏览器上下文
- 所有服务函数使用 async，与现有 FastAPI 架构一致
- Playwright 浏览器默认以 headless 模式运行（可通过配置切换）

## Verification Commands

- `python -c "from playwright.sync_api import sync_playwright; print('OK')"`
- `python -c "from App.models.cookie import CookieStore; print('OK')"`
- `python -c "from App.services.cookie_manager import save_cookies, load_cookies; print('OK')"`
- `ruff check App/services/ App/models/cookie.py App/schemas/cookie.py`

## Branch

Branch: `codex/TASK-001-playwright-cookie-storage`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
