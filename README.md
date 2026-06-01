# 速卖通广告智能管理系统 (AliExpress Ad Manager)

> AI 帮你自动分析速卖通广告效果、算利润、调价格，不用天天盯后台。

---

## 这是什么系统？

一个**自动运营工具**，连接你的速卖通卖家后台，帮你做三件事：

1. **看数据** — 自动采集每个商品的广告曝光、点击、花费、成交额
2. **算利润** — 结合进价、物流费、平台佣金，算你到底赚多少
3. **AI 出主意** — 分析哪些商品该加广告、哪些该降价、哪些该停投，自动执行或等你确认

---

## 快速启动（第一次使用）

### 1. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
# 必须改的：
ADMIN_API_KEY=设置一个登录密码
LLM_API_KEY=你的AI接口key

# 数据库（一般不用改）
DB_HOST=localhost
DB_USER=ad_manager
DB_PASSWORD=数据库密码

# 邮件通知（可选，不填也能用）
SMTP_USER=你的@gmail.com
SMTP_PASSWORD=Gmail应用密码
ALERT_EMAIL_TO=接收警报的邮箱
```

### 2. 用 Docker 一键启动（推荐）

```bash
docker compose up -d
```

等 30 秒，访问 http://localhost:8000 就能看到网页了。

### 3. 或者不用 Docker 手动启动

```bash
# 1. 装 Python 依赖
pip install -r requirements.txt

# 2. 装浏览器（用于自动采集）
playwright install chromium

# 3. 初始化数据库
alembic upgrade head

# 4. 启动（带防双开 + 日志 + 热重启）
python scripts/start.py

# 5. 新开一个窗口，启动前端
cd frontend && npm install && npm run dev
```

然后浏览器打开 http://localhost:5173

---

## 每天怎么用？

### 启动系统

**方式一（推荐）：装成开机自启**
```bash
# 右键点击 → 以管理员身份运行
scripts\install-service.bat
```
装一次以后，每次电脑开机自动在后台启动。

**方式二：手动启动**
```bash
python scripts/start.py
```

**方式三：在网页上重启**
打开「系统设置」→ 点击「🔄 热重启」，服务会自动重启（断 3-5 秒）。

### 日常操作流程

```
1. 打开网页 → 输入 API Key 登录
2. 系统设置 → 点击「启动登录」→ 在弹出的浏览器登录速卖通
3. 系统设置 → 点击「手动采集」→ 系统开始抓取广告数据
4. 系统设置 → 点击「AI 分析」→ 系统计算利润并出建议
5. 如果有待确认的操作 → 去「警报中心」确认或拒绝
```

### 防双开

系统自带**防重复启动**机制。如果你不小心开了两次，第二次会提示：

```
[错误] 应用已在运行 (PID: 12345)
       如需重启，请先停止现有进程
```

强行停止已运行的应用：
```bash
python scripts/start.py --stop
```

---

## 日志在哪里看？

### 方式一：网页上看

打开「系统设置」→ 点击「📋 查看日志」，直接看到最近 200 行日志。

### 方式二：直接打开文件

日志文件在项目目录下的 `logs/app.log`，用记事本就能打开。

### 方式三：Docker 查看（如果用 Docker 启动）

```bash
docker logs ad-manager-app
```

### 日志里有什么？

每条日志是一行 JSON，大概长这样：
```json
{"timestamp": "2026-06-01T10:00:00.000Z", "level": "INFO", "logger": "data_collector", "event": "采集完成", "ad_count": 15}
```

- `level` = 级别：`INFO` 正常 / `WARNING` 要注意 / `ERROR` 出问题了
- `logger` = 哪个模块：`data_collector` 采集 / `decision_engine` AI 分析 / `scheduler` 定时任务
- `event` = 做了什么

---

## 系统架构（简单版）

```
你的浏览器 ──→ [网页控制台] ──→ [后端程序] ──→ [数据库]
                                        │
                                        └── [AI 接口] + [浏览器自动操作]
```

- **网页控制台**：你看得见的页面
- **后端程序**：干活的，采集数据、算利润、调价格
- **数据库**：存数据的地方
- **AI 接口**：帮你分析决策
- **浏览器自动操作**：系统自己开浏览器去速卖通后台操作

---

## 常见问题

**Q: 网页打不开？**
A: 先确认系统在运行。运行 `python scripts/start.py` 或打开 Docker Desktop 看容器是否在跑。

**Q: 采集不到数据？**
A: 去「系统设置」点「启动登录」重新登录速卖通。Cookie 过期了。

**Q: AI 分析失败？**
A: 检查 `.env` 里的 `LLM_API_KEY` 是否正确配置，以及 API 额度是否用完。

**Q: 如何彻底关闭？**
```bash
python scripts/start.py --stop
```

**Q: 如何卸载开机自启？**
```bash
schtasks /delete /tn "AdManager" /f
```

---

## 技术栈（给开发者看）

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.13) |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 前端 | React 18 + TypeScript + Tailwind |
| 浏览器自动化 | Playwright |
| AI | Claude API |
| 容器 | Docker Compose |
