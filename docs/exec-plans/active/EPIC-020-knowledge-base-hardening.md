# EPIC-020: 知识库硬化 (Knowledge Base Hardening)

## 状态
- **创建**: 2026-05-31
- **状态**: 执行中
- **优先级**: P0
- **分支**: `codex/epic-020-knowledge-base-hardening`
- **依赖**: 无

## 目标

将 `docs/` 从被动文档目录升级为可通过 CI 机械验证的"记录系统"。对标 OpenAI 文章原则：**The repository is the source of truth** — 知识库必须是可被 Agent 和 Lint 工具机械检查、而非依赖人类维护的系统。

## 背景

当前状态：
- AGENTS.md 的 Context Map 引用了 `docs/PLANS.md` 但文件不存在
- 文档引用可能过期（代码已更新但文档未更新）
- 文档间链接可能断裂
- QUALITY_SCORE 完全靠人工维护
- Doc-gardening 脚本存在但无 CI 集成

目标状态：
- 7 个 Lint 覆盖文档完整性
- 自动文档花园整理可发起修复 PR
- 计划模板标准化，决策日志可追溯
- 质量评分随 Agent 任务自动更新

## 任务分解

### TASK-020-1: CI Doc Lint — 文档新鲜度自动校验
- 创建 `scripts/lints/check-docs.py`
- 5 项检测：断链、代码引用有效性、文档过期、必需文档存在性、交叉引用完整性
- 集成到 `scripts/lints/run-all.py` 作为第 7 个 lint
- 错误消息包含 FIX 指引

### TASK-020-2: Doc-Gardening 增强 — 自动修复流水线
- 增强 `scripts/doc-gardening.py`
- 实现真正的 `--auto-fix` 模式
- 新增 `--schedule` 模式（定期运行 + 自动 PR）
- 新增 `--ci` 模式（CI 集成）
- 新增重复文档检测

### TASK-020-3: 创建 PLANS.md + 计划模板标准化
- 创建 `docs/PLANS.md`
- 标准化 EPIC 模板（追加 Decision Log section）
- 为现有活跃 EPIC (001-013) 追加空 Decision Log

### TASK-020-4: QUALITY_SCORE 自动更新机制
- 创建 `scripts/update-quality-score.py`
- CLI 更新单个模块的维度评分
- 自动重算均分
- 集成到 Agent 任务完成后自动更新

## 验收标准

1. `python scripts/lints/run-all.py` 包含 check-docs (共 7 checks)
2. `python scripts/doc-gardening.py --ci` 返回 0（无不一致）
3. `docs/PLANS.md` 存在且被 lint 验证
4. 所有活跃 EPIC 包含 Decision Log section
5. `python scripts/update-quality-score.py --check` 验证评分一致性

## Decision Log

| 日期 | 决策 | 决策人 | 理由 | 影响 |
|------|------|--------|------|------|
| 2026-05-31 | 创建 EPIC | opencode | 对标 OpenAI 文章，P0 优先级 | 新增 4 个 TASK |
