# TASK-004-collection-error-handling

## Parent Epic

- Epic: `EPIC-003`
- Epic file: `docs/exec-plans/active/EPIC-003.md`

## Goal

采集异常处理：Cookie 缺失/失效 → 跳过 + 警报；页面访问失败 → 记录错误继续下一页；采集无数据 → 记录日志不报警；采集崩溃 → critical 警报 + 邮件。

异常处理逻辑已内置在 `collect_ad_data()` 和 `CollectionScheduler._collection_job()` 中：

- `no_cookie` → warning 警报（不触发 global_stop，因为这意味着还没登录）
- `global_stop` → 静默跳过
- `collection_failed` → warning 警报
- `collection_crash` → critical 警报 + 邮件 + global_stop
- 单页面异常不中断整体流程
