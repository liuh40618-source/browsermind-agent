<p align="center">
  <h1 align="center">BrowserMind</h1>
  <p align="center">
    <b>一个能自主规划、操控浏览器、理解网页并生成结构化报告的 AI Agent。</b><br/>
    An autonomous AI agent that plans tasks, controls a real browser, understands web content, and produces structured reports.
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"/>
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python"/>
    <img src="https://img.shields.io/badge/FastAPI-0.100+-teal.svg" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/Playwright-1.30+-brightgreen.svg" alt="Playwright"/>
  </p>
</p>

---

## ✨ 特性（Features）

- **任务规划（Planner）** — 把自然语言任务自动拆解为可执行步骤。
- **真实浏览器操控（BrowserTool）** — 基于 Playwright 打开页面、点击、输入、滚动、截图，不是“假装”上网。
- **网页理解（Parser）** — 用 BeautifulSoup + Readability + html2text 把杂乱 HTML 提炼成干净 Markdown。
- **结构化报告（Analyst）** — 把收集到的信息整理成可下载的 Markdown 报告。
- **反思与自检（Reflection）** — 评估任务完成度，判断是否需要继续或补充。
- **人在回路（Human-in-the-loop）** — Reflection 阶段可暂停，等待你「继续 / 调整」，并支持追加指令的**多轮对话**；追问轮带「防短路」守卫，避免 LLM 直接换皮旧报告收尾。
- **轻量报告重生成** — `POST /api/report/regenerate` 复用已抓取信息直接重出报告，无需重开浏览器、不重爬页面。
- **实时可视化工作台** — React 三栏界面，通过 WebSocket 实时展示 Planner / Agent / Parser / Analyst 的执行过程。
- **多模型兼容** — 对接 OpenAI 兼容 API，可运行时切换 Qwen / DeepSeek / GPT / 智谱 等。

## 🖥️ 界面预览

> 深色三栏工作台：左=任务与计划，中=实时时间线，右=报告。启动服务后访问 `http://localhost:8000` 即可看到实时执行过程（认知星图五阶段随执行连线亮起）。
>
> 想要动态 demo？启动服务后用录屏工具 capture 一段操作，保存为 `docs/demo.gif` 并在此引用即可。

## 🏗️ 架构

> 架构图见下方文字版（ASCII）。

```
User → Task Understanding → Planner → Agent Execution Loop
                                        ├─ BrowserTool (Playwright)
                                        ├─ Parser (BeautifulSoup + Readability)
                                        └─ Search (Tavily → DuckDuckGo → Bing 三级降级)
                                    → Reflection → Completion Check
                                    → Analyst → Markdown Report
```

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY

# 3. 启动
python main.py
# 浏览器打开 http://localhost:8000
```

> 需要 Python 3.11+。Windows 用户首次运行会自动切换为 `ProactorEventLoop` 以支持 Playwright 子进程。

## ⚙️ 配置

编辑 `.env`（或运行时在前端「设置」面板中修改，立即生效）：

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_PROVIDER` | 模型供应商 | `openai` / `deepseek` / `qwen` / `zhipu` |
| `LLM_API_KEY` | API 密钥 | `sk-...` |
| `LLM_MODEL` | 模型名 | `gpt-4o` / `deepseek-chat` |
| `LLM_BASE_URL` | 兼容端点（非 OpenAI 时必填） | `https://api.deepseek.com/v1` |
| `TAVILY_API_KEY` | 可选，留空则回退 DuckDuckGo（免密钥） | — |
| `BROWSER_HEADLESS` | 是否无头模式 | `true` / `false` |
| `PORT` | 服务端口 | `8000` |

常用端点：
- **DeepSeek**：`https://api.deepseek.com/v1`
- **Qwen**：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- **Zhipu**：`https://open.bigmodel.cn/api/paas/v4`

## 🧭 使用方式

- **Web 工作台**：打开 `http://localhost:8000`，在左栏输入任务 → 「运行」，中栏实时看执行，右栏看报告并下载。
- **WebSocket 多轮**：前端通过 `/api/agent/stream` 实时接收过程；可在 Reflection 暂停时发送决策或追加指令。
- **REST 一次性**：`POST /api/agent/run` 提交任务，返回完整结果（适合脚本调用）。

```bash
curl -X POST http://localhost:8000/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task":"对比 GPT-4o 与 Claude 在 Agent 任务上的能力，给出结论"}'
```

## 📁 项目结构

```
browsermind/
├── agent/
│   ├── state.py          # 共享状态（task / plan / logs / extracted_info）
│   ├── llm.py            # LLM 客户端 + 工具 schema + 自动重试
│   ├── planner.py        # 任务 → 计划步骤
│   ├── agent_loop.py     # 核心执行循环（think → act → observe）+ 取消支持
│   ├── analyst.py        # 抽取信息 → 结构化 Markdown 报告
│   └── reflection.py     # 完成度评估
├── tools/
│   ├── __init__.py       # 工具注册表（@tool 装饰器）+ retry_async 重试工具
│   ├── browser.py        # Playwright 封装（6 项能力，@tool 注册）
│   ├── search.py         # Tavily → DDG → Bing 三级降级搜索
│   └── parser.py         # HTML → 干净 Markdown
├── tests/                # pytest 单元测试（97 个用例 / 12 个文件）
├── frontend/
│   └── index.html        # React 三栏工作台（CDN 引入）+ 重新生成/停止按钮
├── docs/                 # 项目讲解文档（毕设答辩 / 简历面试 / 路演三场景）
├── config.py             # 配置（LLM / 浏览器 / 服务 / 可选鉴权）
├── main.py               # FastAPI 入口（REST + WebSocket + 静态托管 + 日志）
├── store.py              # SQLite 任务存储（含 parent_id 父子关联 + update_report）
├── settings_store.py     # 用户配置（JSON，带校验）
├── pyproject.toml        # ruff / pytest / mypy 配置
├── Dockerfile            # 容器化部署
├── docker-compose.yml    # 一键启动（数据卷持久化）
└── requirements.txt
```

## 🔌 API 速览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/agent/run` | 一次性执行任务，返回完整结果 |
| `WS` | `/api/agent/stream` | 实时流式执行 + 多轮对话 |
| `POST` | `/api/report/regenerate` | 轻量重生成报告（复用已抓取信息，不重爬） |
| `GET` | `/api/tasks` | 任务历史列表 |
| `GET` | `/api/tasks/{id}` | 单个任务详情 |
| `DELETE` | `/api/tasks` | 清空全部任务历史 |
| `DELETE` | `/api/tasks/{id}` | 删除单个任务 |
| `GET/POST/RESET` | `/api/settings` | 读取 / 更新 / 重置配置 |

> 任务表含 `parent_id` 字段：多轮追问的每一轮会以父任务 ID 串联，可在历史中追溯「这是第几轮追问」。

### 🔐 可选鉴权（部署到公网时）

设置环境变量 `AUTH_TOKEN` 后，所有请求需携带凭证，未设置时本地开发零打扰：

- **REST**：请求头加 `X-Auth-Token: <token>`
- **WebSocket**：首次消息带 `"token": "<token>"` 字段
- `/api/health` 与首页 `/` 始终放行（健康探测用）

## 🧰 技术栈

| 层 | 技术 |
|----|------|
| Agent 编排 | 纯 Python 异步循环（think → act → observe） |
| 浏览器自动化 | Playwright |
| 网页解析 | BeautifulSoup + Readability + html2text |
| LLM | OpenAI 兼容 API（Qwen / DeepSeek / GPT） |
| 后端 | FastAPI + WebSocket |
| 前端 | React（CDN）+ WebSocket 实时 UI |
| 工程质量 | pytest（97 用例）+ ruff + mypy + 工具注册表 |

## ✅ 开发规范

```bash
pip install -r requirements.txt pytest ruff mypy
pytest tests/          # 跑单元测试
ruff check .           # 静态检查（F 规则）
mypy main.py           # 类型检查
```

## 🐳 Docker 部署

```bash
cp .env.example .env   # 填入 LLM_API_KEY（可选 AUTH_TOKEN）
docker compose up -d --build
# 打开 http://localhost:8000
```

`data/`（任务数据库 + 用户配置）与 `logs/` 通过卷挂载持久化。

## 🗺️ Roadmap

- [x] ~可插拔工具注册表~（已落地，见 `tools/__init__.py` 的 `@tool` 装饰器）
- [ ] 自动评测数据集（验证 Agent 在不同任务上的稳定性）
- [x] ~浅色/深色双主题 + 响应式抽屉~（已落地，见前端主题切换）
- [x] ~Docker 化部署~（已落地，见 `Dockerfile` / `docker-compose.yml`）
- [x] ~多轮追问防短路 + 轻量报告重生成~（已落地，见 `/api/report/regenerate`）
- [ ] 任务结果对比 / 版本管理（parent_id 已具备追溯基础）

## 🤝 贡献

欢迎参与！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 📄 许可证

[MIT](LICENSE) © 2026 BrowserMind Contributors
