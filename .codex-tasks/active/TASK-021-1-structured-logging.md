# TASK-021-1: 结构化日志系统

## Parent Epic

- Epic: `EPIC-021`
- Epic file: `docs/exec-plans/active/EPIC-021-agent-observable-system.md`

## Goal

创建 `App/core/logging.py` 提供项目级结构化日志，并迁移所有 21 个 Service 的日志调用。

## Scope

1. 创建 `App/core/logging.py`:
   - 封装 `logging` 模块输出 JSON 格式（不引入 structlog 依赖以保持轻量）
   - 提供 `get_logger(name)` → 返回配置好的 logger
   - 提供 `bind_logger(logger, **context)` → 绑定额外字段
   - JSON 输出格式: `{"timestamp":"ISO8601","level":"INFO","logger":"data_collector","event":"collection_start","sku_count":42}`
   - 支持 `LOG_LEVEL` 环境变量（默认 INFO）
   
2. 迁移所有 Service 中的日志调用:
   - `App/services/browser.py`: print → logger.info/error
   - `App/services/data_collector.py`: print → logger
   - `App/services/decision_engine.py`: print → logger
   - `App/services/login_flow.py`: print → logger
   - `App/services/cookie_manager.py`: print → logger
   - `App/services/api_interceptor.py`: print → logger  
   - `App/services/email_notifier.py`: print → logger
   - 其余 Service 文件类似迁移
   
   策略: 每个文件的 `import logging` / `print()` 替换为 `from App.core.logging import get_logger`

3. 在 `App/main.py` 启动时初始化日志系统

## Allowed Files

- `App/core/logging.py` (新建)
- `App/services/*.py` (仅替换日志调用，不改业务逻辑)
- `App/main.py` (初始化)

## Forbidden Files

- `frontend/`
- `docs/`
- 不影响业务逻辑的修改

## Acceptance Criteria

- 启动应用后 stdout 输出为 JSON 格式，非 plain text
- 每个 Service 的 print() 调用已替换为 logger 调用
- 日志包含 logger name 便于 Agent 过滤

## Verification Commands

- `python -c "from App.core.logging import get_logger; l=get_logger('test'); l.info('hello', extra={'k':'v'})"`

## Branch

Branch: `codex/TASK-021-1-structured-logging`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 `App/core/logging.py`
- 迁移所有 Service 日志调用
- 保存验证证据到 `.codex-runs/`

## Quality Impact

- O: 所有 services → O score +2 (结构化日志统一)
