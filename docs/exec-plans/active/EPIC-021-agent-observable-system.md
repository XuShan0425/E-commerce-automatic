# EPIC-021: Agent 可观测系统 (Agent-Observable System)

## 状态
- **创建**: 2026-05-31
- **状态**: 规划中
- **优先级**: P1
- **分支**: `codex/epic-021-agent-observable-system`
- **依赖**: EPIC-020 (logging 需要 lint 规则验证)

## 目标

让 opencode Agent 能直接感知应用运行状态。对标 OpenAI 文章：**"赋予 opencode 完整的可观测性堆栈...使用 LogQL/PromQL 查询日志、指标和追踪...使像'确保服务启动在 800ms 内完成'这样的提示变得可行"**。

## 背景

当前状态：
- 应用使用 print() 和基本 logging，无结构化输出
- 无可观测性堆栈
- Agent 无法查询日志或指标
- Agent 无法驱动浏览器验证 UI

目标状态：
- 所有日志输出结构化 JSON
- Docker Compose 启动 Loki + Grafana
- Agent 可通过 Skill 查询日志和指标
- Agent 可通过 CDP 脚本截图和检查 DOM

## 任务分解

### TASK-021-1: 结构化日志系统
- 创建 `App/core/logging.py`（基于 structlog 或 JSON 格式 logging）
- 迁移所有 21 个 Service 中的 print/logging 调用
- 日志包含: service, trace_id, action, duration

### TASK-021-2: 本地可观测性堆栈
- 创建 `docker-compose.obs.yml`（Loki + Grafana + Promtail）
- 创建 `deploy/loki-config.yaml`
- 创建 `deploy/grafana-datasources.yaml`

### TASK-021-3: Agent 查询 Skill — agent-observe
- 创建 `skills/agents/agent-observe/SKILL.md`
- 创建 `scripts/agent-query.sh`
- 支持 LogQL 查询日志、PromQL 查询指标、健康检查

### TASK-021-4: Chrome DevTools 驱动接入
- 创建 `scripts/cdp-screenshot.py`（截图）
- 创建 `scripts/cdp-dom-check.py`（DOM 检查）
- 创建 `scripts/cdp-user-journey.py`（用户路径录制）

## 验收标准

1. 启动应用后所有日志为结构化 JSON
2. Agent 可查询 "最近 5 分钟内 data_collector 的错误日志"
3. Agent 可验证 "首页加载后 #root 元素存在"
4. Agent 可截图前端页面并存档

## Decision Log

| 日期 | 决策 | 决策人 | 理由 | 影响 |
|------|------|--------|------|------|
| 2026-05-31 | 创建 EPIC | opencode | 对标 OpenAI 文章可观测性原则 | 新增 4 个 TASK |
