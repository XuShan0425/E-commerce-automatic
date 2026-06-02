# TASK-004-5: 价格监控服务

## Parent Epic

- Epic: `REP-004`
- Epic file: (not yet exists)

## Goal

创建价格监控 API 端点和服务模块，支持查询 SKU 价格历史、监测价格异常变动，并能在价格波动超过阈值时发出警报。

## Allowed Files

- `App/api/v1/price_snapshots.py`
- `App/services/price_monitor.py`
- `App/api/v1/__init__.py`
- `App/schemas/price_snapshot.py`

## Forbidden Files

- `App/models/`
- `App/services/data_collector.py`

## Dependencies

- 依赖 PriceSnapshot 模型（已存在）
- 依赖 PriceSnapshotCreate/Read schema（已存在）

## Acceptance Criteria

1. `GET /api/v1/price-snapshots/{sku_id}/history` 返回该 SKU 的价格历史（按时间倒序，支持 limit 参数）
2. `GET /api/v1/price-snapshots/latest` 返回所有 SKU 的最新价格快照
3. `price_monitor.py` 服务提供 `detect_price_change` 函数，能计算某 SKU 最新价格相比前一次记录的变动百分比
4. 价格变动幅度超过阈值（默认 10%）时可以通过 `raise_alert` 发送警报
5. 路由注册到 `api/v1/__init__.py`
6. 价格快照 schema 补充 `PriceSnapshotLatestRead`（不含 snapshot_time 的简化视图）

## Verification Commands

```
python -c "from App.services.price_monitor import detect_price_change; print('import ok')"
python -c "from App.api.v1.price_snapshots import router; print('router ok')"
```

## Branch

codex/TASK-004-5-price-monitor

## Base Branch

main

## Output Requirements

- 保存运行日志到 `.codex-runs/TASK-004-5/`
- 创建 GitHub PR
