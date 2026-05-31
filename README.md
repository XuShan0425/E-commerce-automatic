# 速卖通广告智能管理系统 (AliExpress Ad Manager)

> AI 驱动的速卖通 (AliExpress) 广告数据分析、决策优化与自动化执行平台

## 项目概述

本系统为速卖通卖家提供一站式的广告数据采集、AI 利润分析、自动决策生成的智能化运营工具。核心技术栈：

- **后端**: FastAPI + SQLAlchemy (async) + PostgreSQL + Playwright
- **前端**: React 18 + TypeScript + Tailwind CSS + Recharts
- **AI**: Claude API (Anthropic Messages) 驱动的决策引擎

## 快速开始

### 环境要求

- Python 3.10+ / Node.js 18+
- PostgreSQL 14+ / Redis 6+
- Playwright (Chromium 浏览器)
- GitHub CLI (`gh`)

### 安装

```bash
# 1. 创建 Python 虚拟环境
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env — 填入数据库连接、LLM API Key、SMTP 等信息

# 4. 初始化数据库
alembic upgrade head

# 5. 启动后端
uvicorn App.main:app --reload --port 8000

# 6. 启动前端（新终端）
cd frontend && npm install && npm run dev
```

### 一键安装 Codex 工作流

```bash
curl -sSL https://raw.githubusercontent.com/XuShan0425/-/main/install.sh | bash -s -- --profile python
```

## 系统架构

```
┌────────────────────────────────────────────────┐
│                  React Frontend                 │
│  仪表盘 │ 商品管理 │ 日志中心 │ 警报 │ 报告 │ 设置  │
└──────────────────┬─────────────────────────────┘
                   │ REST API (X-API-Key)
┌──────────────────▼─────────────────────────────┐
│               FastAPI Backend                   │
│ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│ │ API v1   │ │ Services │ │  AI Pipeline     │ │
│ │ routes   │ │ browser  │ │  profit → AI     │ │
│ │ products │ │ scraper  │ │  → boundary      │ │
│ │ analysis │ │ cookie   │ │  → execute       │ │
│ │ alerts   │ │ email    │ │                  │ │
│ └──────────┘ └──────────┘ └──────────────────┘ │
└──────────────────┬─────────────────────────────┘
                   │ asyncpg
┌──────────────────▼─────────────────────────────┐
│              PostgreSQL Database                │
│  products │ ad_snapshots │ profit_analysis     │
│  alerts │ operation_logs │ cookie_store        │
└────────────────────────────────────────────────┘
```

## 核心功能模块

| 模块 | 功能 | API 前缀 |
|------|------|---------|
| 商品管理 | CRUD + CSV 导入 + 店铺同步 | `/api/v1/products` |
| 数据采集 | Playwright 浏览器自动化拦截广告 API | `/api/v1/collect` |
| AI 分析 | 利润计算 + AI 决策 + 边界检查 | `/api/v1/analysis` |
| 执行引擎 | 自动/手动执行广告调整 | `/api/v1/execution` |
| 费率管理 | 物流费率和平台佣金 AI 解析 | `/api/v1/rates` |
| 警报中心 | 异常检测 + 邮件通知 + 全局停止 | `/api/v1/alerts` |
| Cookie 管理 | 登录状态维护 + 健康检查 | `/api/v1/login` |
| API Key | 鉴权管理 (创建/吊销) | `/api/v1/api-keys` |

## API 鉴权

所有 API（除 `/health` 和 `/system/status`）要求 `X-API-Key` Header。

首次使用时，在 `.env` 中设置 `ADMIN_API_KEY`，前端登录页输入后会自动创建正式的 `ak-xxx` Key。

## 任务与执行计划

```bash
# 规划新特性
codex exec "为 X 功能创建 EPIC 计划"

# 执行计划中的任务
codex exec "执行 TASK-001"

# 完整的 EPIC → PR 工作流见 AGENTS.md
```

### 目录结构

```
.codex-tasks/
├── active/       # 待执行的任务
├── running/      # 执行中的任务
├── pr-opened/    # 已提 PR
├── completed/    # 已完成
└── failed/       # 失败

docs/exec-plans/
├── active/       # 进行中的执行计划
└── completed/    # 已完成的计划

.codex-runs/      # 运行日志和验证证据
```

## 安全底线

- **绝不自动合并 PR** — 所有 PR 需人工审查
- **绝不提交到 `main`** — 自动化只操作 `codex/...` 分支
- **拦截敏感文件** — `.env`、密钥文件不会进入版本控制
- **数据库操作边界检查** — 所有 AI 决策通过硬/软边界验证
- **全局停止机制** — 异常情况自动暂停所有自动操作

## 环境变量参考

```bash
# 数据库
DB_HOST=localhost  DB_PORT=5432  DB_USER=ad_manager  DB_PASSWORD=xxx
DB_NAME=ad_manager

# LLM
LLM_API_KEY=sk-ant-xxx  LLM_API_BASE_URL=https://api.anthropic.com  LLM_MODEL=claude-sonnet-4-6

# 鉴权
ADMIN_API_KEY=admin-bootstrap-key-change-me  SECRET_KEY=change-me

# 邮件（Gmail SMTP + SOCKS5 代理）
SMTP_HOST=smtp.gmail.com  SMTP_PORT=587  SMTP_USER=xxx@gmail.com
SMTP_PASSWORD=xxx  SMTP_FROM=xxx@gmail.com  ALERT_EMAIL_TO=xxx@gmail.com
SMTP_PROXY_HOST=127.0.0.1  SMTP_PROXY_PORT=7890
```
