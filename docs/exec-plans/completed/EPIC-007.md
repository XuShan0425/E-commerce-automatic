# EPIC-007 — 前端控制台

## 目标

构建 React + Tailwind 管理界面，提供 Dashboard / 商品管理 / 日志中心 / 警报中心 / 报告查看 / 系统设置 6 个页面。

## 技术栈

Vite 5 + React 18 + TypeScript + Tailwind CSS 3 + React Router v6 + Recharts

## 架构

```
frontend/
├── index.html                     # Vite 入口
├── package.json                   # 依赖管理
├── vite.config.ts                 # 代理 /api → localhost:8000
├── tailwind.config.js / postcss   # 样式
├── tsconfig.json
└── src/
    ├── main.tsx                   # React 根节点
    ├── App.tsx                    # 路由定义
    ├── index.css                  # Tailwind 指令
    ├── api/client.ts              # fetch 封装 (X-API-Key 注入)
    ├── contexts/AppContext.tsx     # API Key + Toast 全局状态
    ├── components/
    │   ├── Layout.tsx              # 侧边栏 + 顶栏
    │   ├── ApiKeyGuard.tsx         # 未配置 Key 时显示登录页
    │   └── StatusBadge.tsx         # 通用状态徽标
    └── pages/
        ├── Dashboard.tsx           # 仪表盘 (汇总卡 + ROI 趋势图 + SKU 网格)
        ├── Products.tsx            # 商品管理 (CRUD + CSV 导入 + 物流/佣金 + AI 解析)
        ├── Logs.tsx                # 日志中心 (操作日志表格 + 筛选 + AI reasoning 展开)
        ├── Alerts.tsx              # 警报中心 (警报列表 + 待确认操作管理)
        ├── Settings.tsx            # 系统设置 (状态面板 + 快捷操作 + API Key 管理)
        └── Reports.tsx             # 报告查看 (SKU 分析历史 + ROI 趋势图)
```

## 页面功能覆盖

### Dashboard `/`
- 4 汇总卡片 (SKU 数 / 平均 ROI / 平均毛利率 / 未处理警报)
- 近 7 天 ROI 趋势图 (Recharts LineChart)
- SKU 卡片网格 (ROI / 毛利率 / 真实成本 / 盈亏平衡)
- 点击「查看详情」跳转 Reports 页

### Products `/products`
- 3 个标签页: 商品列表 / 物流费率 / 平台佣金
- 商品: CRUD 表格 + CSV 导入 + 添加商品
- 物流费率: 表格 + AI 解析按钮 (parse → 预览 confirm)
- 平台佣金: 表格 + AI 解析按钮

### Logs `/logs`
- 操作日志表格 (时间 / SKU / 操作 / 值变化 / 置信度 / 状态)
- 筛选: SKU ID + 状态
- 点击行展开 AI reasoning
- 状态徽标可视化

### Alerts `/alerts`
- 2 个标签页: 警报列表 / 待确认操作
- 警报: 表格 + 标记已处理 + 清除全局停止
- 待确认: confirm / reject 按钮 (调用 EPIC-006 API)

### Settings `/settings`
- 系统状态面板 (Cookie / 调度器 / 全局停止 / API Keys 数)
- 快捷操作: 启动登录 / 手动采集 / AI 分析 / 执行决策 / 邮件测试
- 调度器启停按钮
- API Key 管理: 列表 + 创建 (返回 raw key) + 吊销

### Reports `/reports`
- SKU ID 输入 + 查询
- 当前指标卡片 (ROI / 毛利率 / 真实成本 / 物流 / 盈亏平衡)
- ROI 历史趋势图 (ROI + 毛利率双线)
- 历史分析记录表格

## 验收标准

1. `npm install && npm run dev` 正常启动，localhost:5173 可访问
2. API Key 引导页 → 输入 Key → 进入控制台
3. 6 个页面均可通过侧边栏导航
4. 所有页面正确调用后端 API 并渲染数据
5. Dashboard 图表正常渲染
6. Product CRUD / CSV 导入 / AI 解析费率 链路完整
7. 警报解决 / 软边界 confirm/reject 流程正确
8. 操作日志筛选 + AI reasoning 展开

## 注意事项

- 前端通过 Vite proxy 转发 `/api` 到 `localhost:8000`，无需跨域
- API Key 存储在 localStorage，页面刷新不丢失
- 所有页面都通过 `api.get/post/put/delete` 调用后端，错误统一由 Toast 展示
- 前端不依赖后端运行即可启动（数据为空时显示引导文案）
