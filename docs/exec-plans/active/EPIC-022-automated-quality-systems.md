# EPIC-022: 自动化质量系统 (Automated Quality Systems)

## 状态
- **创建**: 2026-05-31
- **状态**: 规划中
- **优先级**: P1
- **分支**: `codex/epic-022-automated-quality-systems`
- **依赖**: EPIC-020 (lint 基础设施)

## 目标

编码"品味不变量"为机械规则 + 建立自动审查循环 + 代码垃圾回收。对标 OpenAI 文章：**"将我们称为'黄金原则'的内容直接编码到代码仓库中...类似垃圾回收...人类的品味一旦被捕捉，就会持续应用于每一行代码"**。

## 背景

当前状态：
- 有架构分层 lint 但缺少"品味"规则
- 无共享工具使用强制检查
- 无 Agent 自动审查循环
- 无代码腐化检测

目标状态：
- 5+ 条 Golden Rules 机械执行
- Agent 审查 → 反馈 → 修复 → 再审查循环（最多 3 轮）
- 定期代码 GC 扫描并发起重构 PR
- 模式一致性检测

## 任务分解

### TASK-022-1: Golden Rules Lint — 共享工具强制
- 创建 `scripts/lints/check-shared-utils.py`
- 规则: HTTP 统一封装、日志统一入口、禁止重复工具函数、配置统一访问
- 集成到 `scripts/lints/run-all.py`

### TASK-022-2: Golden Rules Lint — 数据边界验证增强
- 增强 `scripts/lints/check-boundary-validation.py`
- 规则: 外部数据验证、DB 查询 null 检查、API 响应状态码检查、环境变量裸读
- 所有错误包含 FIX 指引

### TASK-022-3: Agent 审查流水线 (Ralph Wiggum 循环)
- 增强 `skills/agents/agent-reviewer/SKILL.md`
- 创建 `scripts/review-loop.py`
- 实现 3 轮自动审查循环

### TASK-022-4: 代码垃圾回收 (Code GC)
- 创建 `scripts/code-gc.py`
- 死代码检测、模式漂移检测、复杂度检测、测试覆盖率缺口
- `--auto-fix` 和 `--schedule` 模式

## 验收标准

1. `python scripts/lints/run-all.py` 包含至少 2 条新 Golden Rules lint
2. `python scripts/review-loop.py --dry-run` 输出完整审查步骤
3. `python scripts/code-gc.py` 扫描后输出可操作报告
4. 至少 1 个实际发现的问题被检测并修复

## Decision Log

| 日期 | 决策 | 决策人 | 理由 | 影响 |
|------|------|--------|------|------|
| 2026-05-31 | 创建 EPIC | opencode | 对标 OpenAI 文章 Golden Rules + GC 原则 | 新增 4 个 TASK |
