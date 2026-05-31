# TASK-022-1: Golden Rules Lint — 共享工具强制

## Parent Epic

- Epic: `EPIC-022`
- Epic file: `docs/exec-plans/active/EPIC-022-automated-quality-systems.md`

## Goal

创建 `scripts/lints/check-shared-utils.py`，用 AST 分析强制执行"使用共享工具而非手写重复代码"的品味规则。

## Scope

创建 `scripts/lints/check-shared-utils.py`:

1. **HTTP 调用统一 (error)** — 禁止 services/ 中直接 `import httpx` 或 `import requests`，应使用 `App/core/http.py` 封装（若存在）或至少统一模式。当前先检测 `import httpx` outside core/

2. **日志调用统一 (error)** — 禁止 `import logging` 直接使用，应使用 `from App.core.logging import get_logger`

3. **重复工具函数检测 (warning)** — AST 分析跨文件函数体相似度 > 90% → 建议提取到 shared/

4. **配置访问统一 (error)** — 禁止直接 `os.environ.get()` 或 `os.getenv()`，应使用 `from App.core.config import settings`

5. 集成到 `scripts/lints/run-all.py`

错误消息包含 FIX 指引，仿照 check-architecture.py 风格。

## Allowed Files

- `scripts/lints/check-shared-utils.py`
- `scripts/lints/run-all.py`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `python scripts/lints/check-shared-utils.py` 扫描所有 App/ 目录
- 在当前代码库至少检测出 1+ 违规（如 services 中直接的 httpx import）
- 错误消息包含 `FIX:` 指引
- 集成到 `run-all.py`

## Verification Commands

- `python scripts/lints/check-shared-utils.py`

## Branch

Branch: `codex/TASK-022-1-shared-utils-lint`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 lint 脚本
- 更新 `run-all.py`
- 保存验证证据
