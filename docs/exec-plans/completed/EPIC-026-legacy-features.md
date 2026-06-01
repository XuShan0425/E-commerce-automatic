# EPIC-026: 遗留特性合并 — feature/migrate-to-claude-code → main

## 状态
- **创建**: 2026-06-01
- **状态**: 已完成
- **优先级**: P1
- **分支**: `codex/epic-026-legacy-features`
- **依赖**: 无

## 目标

将 `feature/migrate-to-claude-code` 分支中尚未合入 main 的有价值内容，拆分为独立 TASK 逐步合并到 main。该分支保存了迁移到 Claude Code 期间积累的全部改动，部分已通过 EPIC-025 的 PR 合入，剩余内容需整理后逐个 PR 引入。

## 任务分解

### TASK-026-1: CLAUDE.md 项目配置文件
- 创建 `CLAUDE.md` — 供 Claude Code 读取的项目规范文件
- 内容：项目概述、技术栈、架构、数据模型、边界规则、AI 规范、协作约定
- 新建文件：`CLAUDE.md`

### TASK-026-2: 额外 Agent Skills
- 安装 yeet/github/gh-fix-ci/gh-address-comments/auto-skill-installer 等 skills
- 添加 `.claude/workflows/orch-utils.js` 工具函数
- 新建文件：`.claude/skills/yeet/*`, `.claude/skills/github/*`, `.claude/skills/gh-fix-ci/*`, `.claude/skills/gh-address-comments/*`, `.claude/skills/auto-skill-installer/*`, `.claude/workflows/orch-utils.js`

### TASK-026-3: 系统服务化 — 启动器、热重启、日志
- 一键启动器 `scripts/start.py`（防双开、热重启、日志归档）
- 开机自启 `scripts/install-service.bat`
- Web 热重启 + 日志端点 `App/api/v1/system.py`

### TASK-026-4: 产品分析模块
- 产品分析数据模型 `App/models/product_analytics.py`
- 产品导入模型 `App/models/product_import.py`
- 分析服务 `App/services/product_analytics_service.py`
- 模型注册 `App/models/__init__.py`

### TASK-026-5: 费率管理前端 + 费率解析服务
- 费率管理页面 `frontend/src/pages/RatesSettings.tsx`
- 前端路由更新 `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`
- Requests 版费率解析服务 `App/services/rate_parser_service.py`
- 费率 API 更新 `App/api/v1/rate_parsing.py`
- 错误处理 `App/core/errors.py`

### TASK-026-6: Phase 1 修复 + 缓存服务
- SKU 分析并发化 `App/services/analysis_pipeline.py`
- 静默错误修复 `App/services/product_scraper.py`
- 前端错误提示 `frontend/src/pages/Settings.tsx`
- Redis 缓存服务 `App/services/cache_service.py`
- `requirements.txt` 启用 Redis

### TASK-026-7: README 重写 + 环境配置
- README.md 重写（面向用户）
- .gitignore 更新
- install.sh 更新

## 并行安全分析

| 任务 | 并行安全 | 理由 |
|------|---------|------|
| TASK-026-1 | safe | 仅新建文档，无交叉文件 |
| TASK-026-2 | safe | 仅新建 skill 文件，无交叉 |
| TASK-026-3 | safe | 仅新建脚本 + 修改 system.py |
| TASK-026-4 | safe | 新模型 + 新服务，不依赖其他任务 |
| TASK-026-5 | unsafe (vs 026-4) | 共享 API 路由但文件不同，可并行 |
| TASK-026-6 | unsafe (vs 026-3) | 修改 settings.tsx 与 026-3 无重叠 |
| TASK-026-7 | safe | 仅文档和环境配置 |

**并行组**: 所有 TASK 可并行执行（文件不重叠）

## 验收标准

1. 每个 TASK 创建独立 PR，有完整的 acceptance criteria 和 verification evidence
2. 所有 PR 合入 main 后，feature/migrate-to-claude-code 分支可安全存档

## Decision Log

| 日期 | 决策 | 决策人 | 理由 | 影响 |
|------|------|--------|------|------|
| 2026-06-01 | 创建 EPIC | opencode | feature/migrate-to-claude-code 内容拆分独立 PR | 7 个 TASK |
| 2026-06-01 | 完成合入 | opencode | 7 个 PR (#20-#26) 全部合并到 main，分支存档 | feature/migrate-to-claude-code 保留存档 |
