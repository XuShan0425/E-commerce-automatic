# TASK-021-2: 本地可观测性堆栈 (Docker Compose)

## Parent Epic

- Epic: `EPIC-021`
- Epic file: `docs/exec-plans/active/EPIC-021-agent-observable-system.md`

## Goal

创建 `docker-compose.obs.yml` 和配套配置文件，启动 Loki + Grafana 本地可观测性堆栈。

## Scope

1. 创建 `docker-compose.obs.yml`:
   - loki: grafana/loki:latest, port 3100
   - grafana: grafana/grafana:latest, port 3000, 匿名访问
   - 应用日志通过 volume mount 接入

2. 创建 `deploy/loki-config.yaml`:
   - 基础本地配置
   - 日志保留 7 天
   
3. 创建 `deploy/grafana-datasources.yaml`:
   - 预配置 Loki 数据源

4. 创建 `deploy/promtail-config.yaml`:
   - 抓取 `.codex-runs/logs/` 目录下的 JSON 日志

## Allowed Files

- `docker-compose.obs.yml`
- `deploy/loki-config.yaml`
- `deploy/grafana-datasources.yaml`
- `deploy/promtail-config.yaml`

## Forbidden Files

- `App/`
- `frontend/`
- 不修改现有 `docker-compose.yml`

## Acceptance Criteria

- `docker compose -f docker-compose.obs.yml config` 通过
- 配置文件语法正确（YAML 可解析）
- 目录结构清晰

## Verification Commands

- `python -c "import yaml; yaml.safe_load(open('docker-compose.obs.yml')); print('YAML OK')"`

## Branch

Branch: `codex/TASK-021-2-obs-stack`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 `docker-compose.obs.yml`
- 创建 `deploy/` 目录下 3 个配置文件
- 保存验证证据到 `.codex-runs/`
