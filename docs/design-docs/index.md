# 设计文档索引

## 核心理念

- [core-beliefs.md](core-beliefs.md) — 智能体优先的操作原则

## 架构设计

- [../ARCHITECTURE.md](../ARCHITECTURE.md) — 分层架构与模块清单
- [../RELIABILITY.md](../RELIABILITY.md) — 超时、重试、降级策略
- [../SECURITY.md](../SECURITY.md) — 安全底线

## 产品设计

- [../PRODUCT_SENSE.md](../PRODUCT_SENSE.md) — 产品原则与决策哲学
- [../DESIGN.md](../DESIGN.md) — 设计系统参考
- [../FRONTEND.md](../FRONTEND.md) — 前端约定

## 执行计划

- [../exec-plans/active/](../exec-plans/active/) — 进行中的 EPIC 计划
- [../exec-plans/completed/](../exec-plans/completed/) — 已完成的计划
- [../exec-plans/tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md) — 已知技术债务 (待创建)

## 验证状态

| 文档 | 最后验证 | 验证方式 |
|------|---------|---------|
| ARCHITECTURE.md | 2026-05-31 | 人工审查 + 代码对比 |
| SECURITY.md | 2026-05-31 | 人工审查 |
| PRODUCT_SENSE.md | 2026-05-31 | 人工审查 |
| RELIABILITY.md | 2026-05-31 | 人工审查 |
| FRONTEND.md | 2026-05-31 | 代码对比 |
| DESIGN.md | 2026-05-31 | 人工审查 |
| QUALITY_SCORE.md | 2026-05-31 | 人工评估 |

验证状态说明:
- **已验证**: 文档内容与代码行为一致
- **待验证**: 需要人工或自动化确认
- **已过期**: 文档与代码不一致，需要更新
