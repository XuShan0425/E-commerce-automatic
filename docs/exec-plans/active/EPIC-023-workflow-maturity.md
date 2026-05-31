# EPIC-023: 工作流成熟度 (Workflow Maturity)

## 状态
- **创建**: 2026-05-31
- **状态**: 规划中
- **优先级**: P2
- **分支**: `codex/epic-023-workflow-maturity`
- **依赖**: EPIC-020 + EPIC-022

## 目标

提升 Agent 自主性和团队吞吐量。对标 OpenAI 文章：**"Pull Request 的生命周期很短...纠错成本低，而等待成本高"**和**"智能体现在可以：验证代码库的当前状态、重现已报告的漏洞、录制演示视频、实施修复、验证修复、打开 PR、回应反馈、检测并修复构建故障、合并更改"**。

## 背景

当前状态：
- Stop Hook 刚性阻塞（任何验证失败 → 完全阻止）
- 无 Bug 复现 → 修复自动化
- 无 Agent 能力矩阵定义人机分工
- 任务完成状态手动管理

目标状态：
- 柔性合入门（Hard fail 阻塞，Soft fail 重试）
- Bug 到 PR 全自动流水线
- Agent 能力等级和信任梯度明确
- 任务完成后自动更新 Epic 状态和质量评分

## 任务分解

### TASK-023-1: 柔性合入门
- 增强 `.codex/hooks/stop_auto_pr.py`
- 验证命令分级（hard/soft severity）
- Soft 失败重试 3 次机制
- PR body 区分 Hard/Soft 状态

### TASK-023-2: Bug → Fix → Verify 自动化
- 创建 `scripts/bug-to-pr.py`
- 6 步流水线: Reproduce → Investigate → Fix → Verify → PR → Notify
- 截图证据前后对比

### TASK-023-3: Agent 能力矩阵
- 创建 `docs/AGENT_CAPABILITIES.md`
- 任务类型四级分类（自主/需审查/需人工/禁止）
- 信任梯度 Level 0-3

### TASK-023-4: 任务完成自动通知
- 创建 `scripts/task-complete.py`
- 自动迁移 Task/EPIC 状态
- 自动更新 QUALITY_SCORE
- 生成完成摘要

## 验收标准

1. Stop Hook 支持 soft fail retry
2. `python scripts/bug-to-pr.py --dry-run "描述"` 输出完整流程
3. `docs/AGENT_CAPABILITIES.md` 存在且被 AGENTS.md 引用
4. TASK 完成后状态自动迁移

## Decision Log

| 日期 | 决策 | 决策人 | 理由 | 影响 |
|------|------|--------|------|------|
| 2026-05-31 | 创建 EPIC | opencode | 对标 OpenAI 文章工作流成熟度原则 | 新增 4 个 TASK |
