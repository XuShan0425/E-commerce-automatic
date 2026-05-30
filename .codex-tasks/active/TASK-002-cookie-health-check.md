# TASK-002-cookie-health-check

## Parent Epic

- Epic: `EPIC-002`
- Epic file: `docs/exec-plans/active/EPIC-002.md`

## Goal

实现 Cookie 定时健康检查服务：定期携带已保存的 Cookie 访问速卖通，检测是否仍然有效，失效时触发全局停止。

## Scope

- 创建 `App/services/cookie_health.py` — 健康检查核心逻辑
  - 用 Playwright 加载 Cookie 后访问速卖通后台 URL
  - 检测登录状态（是否被重定向、页面是否包含登录表单）
  - 有效 → 更新 `is_valid=True` + 记录检查时间
  - 无效 → 设置 `is_valid=False` + 触发停止标志 + 写警报
- 创建 `App/models/system_state.py` — `SystemState` 模型（全局状态管理）
  - 字段：key (unique), value (JSONB), updated_at
  - 用于存储 `global_stop` 等全局标志
- 创建 `App/schemas/system_state.py`
- 注册一个 `/api/v1/system/status` 端点（只读，免鉴权），返回当前系统状态
- 更新模型/schema 导出

## Allowed Files

- `App/services/cookie_health.py`
- `App/models/system_state.py`
- `App/schemas/system_state.py`
- `App/api/v1/system.py`（只读状态端点）
- `App/api/v1/__init__.py`（注册路由）
- `App/models/__init__.py`
- `App/schemas/__init__.py`

## Forbidden Files

- `.codex/` 目录下的任何文件
- `App/api/v1/auth.py`（只读参考）
- 已有的 EPIC/TASK 文件

## Acceptance Criteria

- `cookie_health.py` 的 `check_cookie_health()` 能检测三种状态：
  - `valid` — Cookie 正常，页面正常加载
  - `invalid` — 被重定向到登录页 / 出现登录表单
  - `error` — 网络错误或其他异常
- Cookie 失效时自动写入 `SystemState(global_stop=True)`
- `GET /api/v1/system/status` 返回 `{"global_stop": false, "cookie_valid": true, "last_check": "..."}`
- 所有函数支持 async

## Verification Commands

- `python -c "from App.services.cookie_health import check_cookie_health; print('OK')"`
- `python -c "from App.models.system_state import SystemState; print('OK')"`
- `ruff check App/services/cookie_health.py App/models/system_state.py App/api/v1/system.py`

## Branch

Branch: `codex/TASK-002-cookie-health-check`

## Base Branch

Base branch: `main`

## Output Requirements

- 更新本任务文件，添加执行摘要
- 保存运行日志到 `.codex-runs/`
- 创建或更新 GitHub PR
- 不要自动合并
