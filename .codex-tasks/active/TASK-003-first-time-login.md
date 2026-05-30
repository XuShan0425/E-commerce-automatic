# TASK-003-first-time-login

## Parent Epic

- Epic: `EPIC-002`
- Epic file: `docs/exec-plans/active/EPIC-002.md`

## Goal

实现首次登录流程：通过 API 触发 Playwright 启动浏览器 → 用户在浏览器中手动登录速卖通 → 系统自动捕获并保存 Cookie。

## Scope

- 创建 `App/services/login_flow.py` — 首次登录编排
  - 启动非 headless 浏览器（用户可见）
  - 导航到速卖通登录页
  - 等待用户完成登录（检测 URL 变化 / Cookie 出现）
  - 登录成功后自动提取所有 Cookie
  - 调用 `cookie_manager.save_cookies()` 保存
  - 关闭浏览器
- 创建 `App/api/v1/auth_flow.py` — 登录流程 API 端点
  - `POST /api/v1/login/start` — 触发登录流程（需鉴权），启动浏览器
  - `GET /api/v1/login/status` — 查询登录流程状态（等待中/进行中/成功/失败）
- 更新 `App/api/v1/__init__.py` 注册新路由

## Allowed Files

- `App/services/login_flow.py`
- `App/api/v1/auth_flow.py`
- `App/api/v1/__init__.py`

## Forbidden Files

- `.codex/` 目录下的任何文件
- `App/models/`（只读参考，不改）
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- `POST /api/v1/login/start` 触发后，Playwright 启动一个**可见**的 Chrome/Chromium 窗口
- 浏览器自动导航到速卖通登录页（`https://login.aliexpress.com`）
- 用户手动完成登录后，系统能够自动检测到登录成功
- Cookie 被完整提取并调用 `cookie_manager.save_cookies()` 保存到数据库
- 登录状态可通过 `GET /api/v1/login/status` 查询
- 登录失败/超时有合理的错误提示

## Verification Commands

- `python -c "from App.services.login_flow import start_login_flow; print('OK')"`
- `python -c "from App.api.v1.auth_flow import router; print('OK')"`
- `ruff check App/services/login_flow.py App/api/v1/auth_flow.py`

## Branch

Branch: `codex/TASK-003-first-time-login`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
