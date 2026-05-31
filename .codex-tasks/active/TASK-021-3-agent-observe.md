# TASK-021-3: Agent 查询 Skill — agent-observe

## Parent Epic

- Epic: `EPIC-021`
- Epic file: `docs/exec-plans/active/EPIC-021-agent-observable-system.md`

## Goal

创建 Agent 可观测性 Skill 和配套 CLI 脚本，让 opencode 能够查询应用日志、指标和健康状态。

## Scope

1. 创建 `skills/agents/agent-observe/SKILL.md`:
   - 描述 Skill 触发条件：Agent 需要确认服务状态、排查错误、验证性能时
   - 列出可用查询能力
   
2. 创建 `scripts/agent-query.sh`:
   - `bash scripts/agent-query.sh health` — 调用 API 健康检查
   - `bash scripts/agent-query.sh logs --service <name> --last 5m` — 查看日志（从 .codex-runs/logs/ 读取）
   - `bash scripts/agent-query.sh errors --last 5m` — 查看最近错误

3. 更新 `skills/agents/agent-observe/` 目录:
   - 确保 `find-skills` 和 `auto-skill-installer` 能发现此 Skill

## Allowed Files

- `skills/agents/agent-observe/SKILL.md`
- `scripts/agent-query.sh`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `skills/agents/agent-observe/SKILL.md` 存在且格式正确
- `bash scripts/agent-query.sh health` 输出 JSON 状态
- Skill 可被 opencode 的 Skill 系统识别

## Verification Commands

- `bash scripts/agent-query.sh health`

## Branch

Branch: `codex/TASK-021-3-agent-observe`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 Agent 查询 Skill
- 创建配套 CLI 脚本
- 保存验证证据到 `.codex-runs/`
