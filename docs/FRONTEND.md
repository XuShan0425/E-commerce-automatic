# 前端约定

> 最后更新: 2026-05-31 | React 18 + TypeScript + Tailwind CSS + Vite

## 技术栈

| 依赖 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| React Router DOM | 6.28 | 客户端路由 |
| Recharts | 2.15 | 图表 |
| Tailwind CSS | 3.4 | 样式 |
| Vite | 6.0 | 构建工具 |
| TypeScript | 5.6 | 类型检查 |

## 目录结构

```
frontend/src/
├── api/
│   └── client.ts          # 唯一 HTTP 客户端, 导出 api.get/post/put/delete/upload
├── components/
│   ├── Layout.tsx          # 全局布局（侧栏 + 顶栏）
│   ├── ApiKeyGuard.tsx     # API Key 守卫 — 未认证时显示登录页
│   ├── StatusBadge.tsx     # 通用状态徽章 (success/warning/error)
│   ├── ProductModal.tsx    # 商品编辑弹窗
│   ├── CsvPreviewModal.tsx # CSV 导入预览
│   └── StoreProductModal.tsx # 店铺商品展示弹窗
├── contexts/
│   └── AppContext.tsx      # 全局状态 (API Key, 系统状态)
├── pages/
│   ├── Dashboard.tsx       # 仪表盘 — 核心指标概览
│   ├── Products.tsx        # 商品管理 — CRUD + CSV 导入
│   ├── Logs.tsx            # 日志中心 — 操作日志 + 筛选
│   ├── Alerts.tsx          # 警报中心 — 查看/解除/全局停止
│   ├── Settings.tsx        # 系统设置 — Cookie/代理/登录
│   └── Reports.tsx         # 报告页面
├── App.tsx                 # 路由定义
└── main.tsx                # 入口
```

## 组件模式

### 页面组件 (pages/)

- 每个页面文件对应一个路由
- 页面负责数据获取和状态管理
- 使用 `api` 对象（从 `api/client.ts`）进行 HTTP 调用

### 通用组件 (components/)

- 可复用的 UI 组件
- 通过 props 接收数据，不直接调用 API
- 使用 Tailwind 原子类，不写自定义 CSS

### 状态管理

- 无全局状态库（不用 Redux/Zustand）
- API Key 存储在 `localStorage` 中
- 页面内状态用 React `useState` / `useEffect`
- `AppContext` 提供全局的 API Key 和系统状态

## API 客户端规范

```typescript
// 所有 API 调用通过 api 对象
import { api, ApiError } from '../api/client';

// GET
const data = await api.get<ResponseType>('/products');

// POST
const result = await api.post<ResponseType>('/collect/run', { sku_ids: [...] });

// 错误处理
try {
  await api.post('/execution/run', payload);
} catch (e) {
  if (e instanceof ApiError) {
    // e.code: ErrorCode 枚举值 (如 "COOKIE_MISSING")
    // e.suggestion: 用户引导文案
    showError(e.code, e.suggestion);
  }
}
```

## 样式约定

- 只用 Tailwind 原子类，不写 `.css` 文件
- 颜色：`bg-red-50` (错误), `bg-green-50` (成功), `bg-blue-50` (信息)
- 状态徽章：`StatusBadge` 组件统一处理
- 表格：`table-auto w-full text-sm` 为基础样式
- 弹窗：固定宽度 `max-w-lg` / `max-w-2xl`，居中，半透明背景

## 路由结构

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | Dashboard | 默认首页 |
| `/products` | Products | 商品管理 |
| `/logs` | Logs | 操作日志 |
| `/alerts` | Alerts | 警报中心 |
| `/settings` | Settings | 系统设置 |
| `/reports` | Reports | 数据报告 |

## 类型约定

- API 响应类型定义在调用处（不作为独立 `.d.ts` 文件）
- 使用 `interface` 而非 `type`（除非需要 union）
- 错误类型使用 `ApiError` 类（定义在 `api/client.ts`）

## 已知模式（智能体应遵循）

1. 新页面的 API 调用写在页面文件内，不拆分为独立 service 文件
2. 弹窗组件接收 `open` + `onClose` props
3. 表格数据用 `useState` + `useEffect` 在页面内管理
4. CSV 上传使用 `api.upload()` 方法（内部用 FormData）
