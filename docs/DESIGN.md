# 设计系统参考

> 最后更新: 2026-05-31 | 用于指导前端 UI 实现

## 设计原则

1. **信息层次清晰** — 关键指标突出，详细数据折叠/分页
2. **操作可发现** — 主要操作按钮可见，危险操作有确认步骤
3. **状态可感知** — 加载/成功/失败/警告状态始终显示
4. **响应式但不优先移动端** — 核心用户场景在桌面端（1920×1080 / 1440×900）

## 配色

| 用途 | Tailwind Class | 说明 |
|------|---------------|------|
| 主色调 | `blue-600` / `blue-700` | 按钮、链接 |
| 成功 | `green-500` / `green-50` (bg) | ROI 正值、操作成功 |
| 警告 | `amber-500` / `amber-50` (bg) | 边界警告、待确认 |
| 危险 | `red-500` / `red-50` (bg) | ROI 负值、操作失败、全局停止 |
| 信息 | `blue-400` / `blue-50` (bg) | 中性信息 |
| 背景 | `gray-50` (page) / `white` (card) | 页面/卡片层次 |
| 文字 | `gray-900` (主) / `gray-600` (次) / `gray-400` (禁用) | 文字层次 |

## 组件规格

### StatusBadge

```tsx
<StatusBadge status="success" />  // 绿色圆点 + 文字
<StatusBadge status="warning" />  // 琥珀色
<StatusBadge status="error" />    // 红色
<StatusBadge status="info" />     // 蓝色
```

### 表格

- 基础样式: `table-auto w-full text-sm`
- 表头: `bg-gray-50 text-gray-600 font-medium`
- 行: `border-b border-gray-100 hover:bg-gray-50`
- 空状态: 居中文字 "暂无数据"

### 弹窗 (Modal)

- 背景: 半透明黑色 `bg-black/50`
- 内容: `bg-white rounded-lg shadow-xl max-w-lg mx-auto`
- 标题: `text-lg font-semibold`
- 关闭: 右上角 X 按钮 + 点击背景关闭

### 按钮

- 主要: `bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700`
- 次要: `border border-gray-300 text-gray-700 px-4 py-2 rounded hover:bg-gray-50`
- 危险: `bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600`
- 禁用: `opacity-50 cursor-not-allowed`

## 布局

- 全局: 侧栏 (240px 宽) + 主内容区
- 侧栏: 深色背景 (`gray-900`), 导航链接, 底部系统状态
- 顶栏: 页面标题 + 面包屑 (可选)
- 最大内容宽度: 无限制 (fluid)，padding `p-6`

## 图表 (Recharts)

- 使用 Recharts 作为唯一图表库
- 颜色方案: `['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']`
- Tooltip: 自定义 `content` prop，白色背景 + 阴影
- 折线图: `strokeWidth={2}` + `dot={false}` (数据点太多时)
