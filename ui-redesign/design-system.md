# BrowserMind · 界面设计系统（UI Design System）

> 设计目标：在「美」与「易用」之间取平衡，遵循用户在 AI 智能体工具（Cursor / ChatGPT / Manus 类）中已形成习惯的**三栏工作台范式**，同时以设计令牌统一视觉语言、以双主题覆盖更广人群、以 WCAG AA 保证无障碍。

---

## 🎨 设计基座（Design Foundations）

### 1. 配色系统（Color）
全量走 CSS 变量，浅色为默认，深色调通过 `[data-theme="dark"]` 覆盖。阶段色在明/暗下保持同一语义映射，确保用户跨主题不丢失认知。

| 角色 | 浅色 Token | 深色 Token | 用途 |
|------|-----------|-----------|------|
| 应用背景 | `--bg-app #f5f6f9` | `#0b0e16` | 整体画布 |
| 表面 | `--bg-surface #fff` | `#131826` | 卡片/栏 |
| 次级表面 | `--bg-surface-2` | `#171d2e` | 输入框/表格头 |
| 悬停 | `--bg-hover` | `#1f2740` | hover 态 |
| 边框 | `--border` | `rgba(255,255,255,.09)` | 分隔线 |
| 主文本 | `--text-strong #14161c` | `#eef1f8` | 标题/重点 |
| 正文 | `--text #2b2f3a` | `#cdd3e0` | 段落 |
| 次文本 | `--text-secondary` | `#97a0b3` | 说明 |
| 弱文本 | `--text-muted` | `#646d81` | 辅助标签 |
| 品牌主色 | `--brand #5b5bf0` | `#8b7bfc` | 主操作/强调 |
| 成功 | `--success` | `#2bd19a` | 完成 |
| 警告 | `--warning` | `#f0a93a` | 缺失/注意 |
| 危险 | `--danger` | `#ff6b66` | 错误/停止 |

**智能体阶段语义色（跨浅/深共用）**

| 阶段 | 变量 | 色值 | 含义 |
|------|------|------|------|
| 规划/思考 | `--stage-think` | `#6d5efc` | Planner |
| 浏览/搜索 | `--stage-browse` | `#2f6bff` | Browser Tool |
| 解析/抽取 | `--stage-parse` | `#11a36e` | Parser |
| 分析 | `--stage-analyze` | `#d98300` | Analyst |
| 反思 | `--stage-reflect` | `#d6409f` | Reflection |

> 无障碍：正文 `--text` 在 `--bg-surface` 上对比度 ≥ 4.5:1（WCAG AA）；弱文本仅用于非必要标签。

### 2. 字体系统（Typography）
- **主字体**：`Inter`（回退 system-ui / PingFang SC / 微软雅黑），标题与 UI 通用。
- **等宽**：`JetBrains Mono`，用于日志、URL、代码、时间。
- **字号阶梯**：12 → 13 → 14 → 15 → 18 → 22 → 28px（4px 节奏的衍生）。
- **字重**：400 / 500 / 600 / 700 / 800。
- 行高：正文 1.5–1.6，标题 1.3 收紧。

### 3. 间距系统（Spacing）
基准 **4px**，完整阶梯：`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48px`。
栅格采用 12 列弹性栅格；本工作台用 `264px | 1fr | 340px` 三栏定宽 + 自适应。

### 4. 圆角与阴影 / 动效
- 圆角：`sm 6 / md 10 / lg 14 / xl 20 / full 999px`。
- 阴影：三层（sm/md/lg），浅色更轻、深色更沉，用于建立层级而不喧宾夺主。
- 动效：统一缓动 `cubic-bezier(.4,0,.2,1)`；所有动画在 `prefers-reduced-motion` 下自动降级为瞬时。

---

## 🧱 组件库（Component Library）

### 基础组件
| 组件 | 变体 / 状态 | 说明 |
|------|-----------|------|
| 按钮 Button | primary / ghost / line；hover·active·disabled | 主操作用品牌色填充 |
| 图标按钮 IconBtn | 默认 / toggle | 顶栏主题、面板开关 |
| 输入框 Textarea | default / focus / disabled | 任务描述，⌘/Ctrl+Enter 运行 |
| 卡片 Card | surface / hover | 时间线节点、统计卡 |
| 徽章 Badge | thinking/browsing/parsing/analyzing/reflecting/system | 阶段标识，颜色与阶段色一致 |
| 进度条 Progress | 0–100% 渐变填充 | 任务整体进度 |
| 胶囊 Pill | default / live（带脉冲点） | 状态、元信息 |
| 统计块 Stat | 2×2 网格 | 概览数字 |
| 计划树 Tree | done / run / pending | 执行步骤状态 |
| 对话框/抽屉 | 移动端侧栏·情报面板 | 响应式承载 |

### 交互状态规范
- **默认 / hover / active / focus / disabled** 五态齐全；焦点统一 `--focus-ring`（品牌色外环，不依赖 outline 色）。
- **加载**：时间线节点以 `slideIn` 依次入场，进度条平滑增长。
- **空态**：报告区、历史区有清晰引导文案与图标。
- **错误**：危险色仅用于停止/失败，且配合文案而非仅靠颜色（满足色彩无障碍）。

---

## 📱 响应式策略（Responsive）

| 断点 | 布局 | 交互 |
|------|------|------|
| ≥1100px | 三栏常驻（264 / 1fr / 340） | 全功能 |
| 720–1100px | 两栏，情报面板转为右侧抽屉 | 顶栏「📊」开合面板 |
| ≤720px | 单栏，侧栏转为左侧抽屉 | 顶栏「☰」开合导航，遮罩关闭 |

---

## ♿ 无障碍标准（Accessibility · WCAG AA）

- **对比度**：正文 ≥ 4.5:1，大文本 ≥ 3:1。
- **键盘可达**：跳转链接（skip-link）、全部按钮/输入可 Tab 聚焦，焦点环清晰。
- **屏幕阅读器**：语义标签（`aside/main/section/nav`）+ `aria-label`；时间线 `aria-live="polite"` 播报新增节点。
- **触控目标**：图标按钮 ≥ 38px，列表项 padding 充足，满足 44px 建议。
- **动效敏感**：`prefers-reduced-motion` 下关闭所有动画。
- **主题持久化**：选择存入 `localStorage`，首次访问跟随系统 `prefers-color-scheme`。

---

## 🔁 与现有 `frontend/index.html` 的关系
- 现有实现为**深色单主题、CDN React**；本方案保留其已被用户验证的**三栏范式与阶段可视化**，并补齐：① 浅/暗双主题；② 统一令牌与组件文档；③ 响应式抽屉与无障碍；④ 欢迎态/空态/加载态的完整状态机。
- 可直接作为 `index.html` 的视觉与交互改版基准；组件类名已语义化，便于映射回 React 组件。

---
**UI Designer** · BrowserMind 界面设计方案
**日期**：2026-08-07
**状态**：设计系统 + 可交互原型已就绪，可进入开发对接（Developer Handoff）
