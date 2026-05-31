#!/usr/bin/env bash
# Agent 查询工具 — 让 Codex 能查询应用日志和健康状态
# 用法:
#   bash scripts/agent-query.sh health         # 健康检查
#   bash scripts/agent-query.sh logs --service data_collector --last 5m
#   bash scripts/agent-query.sh errors --last 5m
#   bash scripts/agent-query.sh metrics --name error_rate

set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000/api/v1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

output_json() {
  python3 -c "import json; print(json.dumps($*))" 2>/dev/null || echo "{}"
}

health() {
  python3 -c "
import urllib.request, json, sys
results = {}
try:
    resp = urllib.request.urlopen('${API_BASE}/health', timeout=5)
    results['health'] = {'ok': True, 'body': resp.read().decode()[:500]}
except Exception as e:
    results['health'] = {'ok': False, 'error': str(e)}
try:
    resp = urllib.request.urlopen('${API_BASE}/health/db', timeout=5)
    results['db'] = {'ok': True, 'body': resp.read().decode()[:500]}
except Exception as e:
    results['db'] = {'ok': False, 'error': str(e)}
try:
    resp = urllib.request.urlopen('${API_BASE}/system/status', timeout=5)
    results['system'] = json.loads(resp.read().decode())
except Exception as e:
    results['system'] = {'ok': False, 'error': str(e)}
print(json.dumps(results, indent=2, ensure_ascii=False))
" 2>/dev/null
}

logs() {
  local service="${1:-}"
  local log_dir="${ROOT}/.codex-runs/logs"

  if [ ! -d "$log_dir" ]; then
    echo '{"logs": [], "error": "日志目录不存在", "hint": "启动应用后日志将写入 .codex-runs/logs/"}'
    return 0
  fi

  local files=()
  while IFS= read -r -d '' f; do
    files+=("$f")
  done < <(find "$log_dir" -name "*.log" -type f -print0 2>/dev/null || true)

  if [ ${#files[@]} -eq 0 ]; then
    echo '{"logs": [], "message": "没有日志文件"}'
    return 0
  fi

  echo '{"logs": ['

  local first=true
  for f in "${files[@]}"; do
    while IFS= read -r line; do
      if [ -n "$service" ] && ! echo "$line" | grep -q "\"logger\":\"$service\""; then
        continue
      fi
      if [ "$first" = false ]; then echo ','; fi
      echo -n "  $line"
      first=false
    done < <(tail -50 "$f" 2>/dev/null || true)
  done

  echo ''
  echo ']}'
}

errors() {
  local log_dir="${ROOT}/.codex-runs/logs"

  if [ ! -d "$log_dir" ]; then
    echo '{"errors": []}'
    return 0
  fi

  echo '{"errors": ['
  local first=true
  for f in "$log_dir"/*.log 2>/dev/null; do
    while IFS= read -r line; do
      if echo "$line" | grep -q '"level":"ERROR"'; then
        if [ "$first" = false ]; then echo ','; fi
        echo -n "  $line"
        first=false
      fi
    done < <(tail -100 "$f" 2>/dev/null || true)
  done
  echo ''
  echo ']}'
}

metrics() {
  python3 -c "
import urllib.request, json
try:
    resp = urllib.request.urlopen('${API_BASE}/health', timeout=5)
    data = json.loads(resp.read().decode())
    print(json.dumps({'metrics': data, 'source': 'health_endpoint'}, indent=2))
except Exception as e:
    print(json.dumps({'error': str(e)}, indent=2))
" 2>/dev/null
}

case "${1:-}" in
  health) health ;;
  logs) logs "${3:-}" ;;
  errors) errors ;;
  metrics) metrics ;;
  *)
    echo "用法: bash scripts/agent-query.sh {health|logs|errors|metrics} [args]"
    exit 1
    ;;
esac
