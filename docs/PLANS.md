# 计划系统规范

> 最后更新: 2026-05-31 | 维护者: 人类工程师 + opencode

## EPIC 命名规范

- 格式: `EPIC-XXX-<slug>.md`
- XXX: 三位数字编号（不可重复）
- slug: 英文小写短横线连接，描述 Epic 主题
- 示例: `EPIC-020-knowledge-base-hardening.md`

## 生命周期

```
Draft → Active → Completed
                ↘ Failed
```

| 状态 | 含义 | 文件位置 |
|------|------|---------|
| Draft | 草稿，尚未开始执行 | `docs/exec-plans/active/` |
| Active | 执行中 | `docs/exec-plans/active/` |
| Completed | 所有 TASK 完成并合并 | `docs/exec-plans/completed/` |
| Failed | 已放弃或取消 | `docs/exec-plans/completed/` (标注 failed) |

## EPIC 文件模板

每个 EPIC 文件必须包含以下 section：

```markdown
# EPIC-XXX: <标题>

## 状态
- **创建**: YYYY-MM-DD
- **状态**: 规划中 | 执行中 | 已完成 | 已放弃
- **优先级**: P0 | P1 | P2 | P3
- **分支**: `codex/epic-XXX-slug`
- **依赖**: 无 | EPIC-XXX, EPIC-YYY

## 目标
一句话描述要达成的结果。

## 背景
为什么需要这个 EPIC，当前状态 vs 目标状态。

## 任务分解
### TASK-XXX-1: <标题>
**内容**: 具体要做的事

### TASK-XXX-2: <标题>
...

## 验收标准
1. 可验证的指标 1
2. 可验证的指标 2

## Decision Log

| 日期 | 决策 | 决策人 | 理由 | 影响 |
|------|------|--------|------|------|
| YYYY-MM-DD | 决策描述 | 人名/opencode | 为什么做这个决策 | 影响了什么 |
```

## TASK 文件模板

TASK 文件位于 `.codex-tasks/active/`，格式见 `TASK-template.md`。

## 决策日志规范

- 每次重大决策必须记录在 Decision Log 表格中
- 决策人: 人类姓名 或 "opencode"
- 理由: 简述为什么选择这个方案而非其他
- 影响: 描述决策对后续工作的影响

## 技术债务追踪

不紧急但已知的问题记录在 `docs/exec-plans/tech-debt-tracker.md`。每项债务包含:
- 严重程度 (P0-P3)
- 发现日期
- 关联模块
- 预计修复时间
