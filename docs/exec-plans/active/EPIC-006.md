# EPIC-006 — Playwright 执行层

## 目标

将 EPIC-005 的 AI 决策"落地"——通过 Playwright 在速卖通后台实际执行广告出价调整、价格修改和推广活动管理。

**安全第一**: 所有操作先经边界检查；软边界需人工确认；操作全程记录日志。

## 架构

```
analysis_result (EPIC-005 output)
    ↓
execution_engine.execute_decision()
    ├── decision_type = no_action → 日志 (success)
    ├── boundary.hard = block → 日志 (failed) + 告警
    ├── boundary.soft = block → 日志 (pending_confirmation) + 告警 → 等待 API 确认
    └── boundary.passed → adjuster.execute_*() → 日志 (success/failed) + 告警
```

## 任务拆分

| 编号 | 任务 | 说明 | 依赖 |
|------|------|------|------|
| TASK-001 | Operation Log 模型 + DB | ORM 模型 + init.sql 表 | 无 |
| TASK-002 | Playwright Adjuster | 4 类执行器 + 选择器字典 | 无 |
| TASK-003 | Operation Logger | 日志写入/查询/格式化 | TASK-001 |
| TASK-004 | Execution Engine | 决策→执行→日志编排 | TASK-001~003 |
| TASK-005 | Execution API | 6 端点 + 路由 | TASK-004 |

## 验收标准

1. operation_logs 表创建成功，ORM 可正常读写
2. Adjuster 4 类执行器（adjust_bid/price/stop_ad/switch_ad_type）可被调用
3. Execution Engine 正确处理 5 种决策路径（no_action/hard/soft/passed/failed）
4. 操作日志包含完整上下文（旧值→新值、AI 置信度、推理、执行状态）
5. 待确认操作可被 confirm/reject
6. 所有端点和内部路径已验证导入

## 新增 API 端点 (6)

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/execution/run | 分析+执行所有商品 (支持 dry_run) |
| POST | /api/v1/execution/run/{sku_id} | 分析+执行单个 SKU |
| GET | /api/v1/execution/pending | 列出待确认操作 |
| POST | /api/v1/execution/pending/{log_id}/confirm | 确认并执行 |
| POST | /api/v1/execution/pending/{log_id}/reject | 拒绝操作 |
| GET | /api/v1/execution/logs | 操作日志 (按 SKU/状态/类型筛选) |

## 新增模块

| 模块 | 功能 |
|------|------|
| App/models/operation_log.py | OperationLog ORM 模型 |
| App/services/adjuster.py | Playwright 执行器 (4 类) + 选择器字典 + 反爬延迟 |
| App/services/operation_logger.py | 日志写入 + 查询 + 格式化 |
| App/services/execution_engine.py | 决策执行编排 + 确认/拒绝 |

## 端到端链路

```
POST /execution/run
  → analyze_all_skus()        ← EPIC-005
  → execute_all_passed()
    → for each result:
      → execute_decision()
        → boundary.passed?
          hard → log_operation(failed) + raise_alert
          soft → log_operation(pending_confirmation) + raise_alert
          yes  → _run_adjuster() [BrowserService → adjust_bid/price/stop/switch]
                 → log_operation(success/failed)
```

人工确认链路:
```
GET /execution/pending         → 查看待确认列表
POST /execution/pending/{id}/confirm → _run_adjuster() → 更新状态
POST /execution/pending/{id}/reject  → 标记为 rejected
```

## 注意事项

- Adjuster 选择器为占位符，需根据实际速卖通后台 DOM 更新 `SELECTORS` 字典
- 执行器在 `asyncio.to_thread` 中运行（同步 Playwright）
- 建议生产环境先用 `dry_run=true` 验证日志流转，确认无误后再关闭 dry_run
- 反爬延迟 500-2000ms，可通过修改 MIN_DELAY_MS/MAX_DELAY_MS 调整
