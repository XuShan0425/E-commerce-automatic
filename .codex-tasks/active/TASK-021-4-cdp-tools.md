# TASK-021-4: Chrome DevTools 驱动接入 (MVP)

## Parent Epic

- Epic: `EPIC-021`
- Epic file: `docs/exec-plans/active/EPIC-021-agent-observable-system.md`

## Goal

创建 3 个 CDP 工具脚本，让 opencode 能截图页面、检查 DOM 和录制用户路径。

## Scope

1. 创建 `scripts/cdp-screenshot.py`:
   - 使用 Playwright 连接到运行中的浏览器或启动新实例
   - `python scripts/cdp-screenshot.py --url http://localhost:5173 --output .codex-runs/screenshot.png`
   - 输出: JSON `{"success": true, "path": ".codex-runs/screenshot.png", "viewport": "1920x1080"}`

2. 创建 `scripts/cdp-dom-check.py`:
   - `python scripts/cdp-dom-check.py --url http://localhost:5173 --selector ".app-title" --expect-text "速卖通广告管理"`
   - 输出: JSON `{"found": true, "text": "速卖通广告管理", "exists": true}`

3. 创建 `scripts/cdp-user-journey.py`:
   - 预定义 journey: login-to-products
   - 逐步截图 + 状态验证
   - 输出: JSON `{"steps": [{"name":"navigate","duration_ms":120},...], "success": true}`

所有脚本 JSON 输出到 stdout，便于 Agent 解析。

## Allowed Files

- `scripts/cdp-screenshot.py`
- `scripts/cdp-dom-check.py`
- `scripts/cdp-user-journey.py`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `python scripts/cdp-screenshot.py --url http://localhost:5173 --output .codex-runs/test.png` 语法正确
- 脚本使用 Playwright API（项目已依赖）
- 所有脚本输出 JSON 格式到 stdout

## Verification Commands

- `python -m py_compile scripts/cdp-screenshot.py scripts/cdp-dom-check.py scripts/cdp-user-journey.py`

## Branch

Branch: `codex/TASK-021-4-cdp-tools`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 3 个 CDP 工具脚本
- 保存验证证据到 `.codex-runs/`
