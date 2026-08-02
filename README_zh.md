# BrowserMind

[![CI](https://github.com/liuh40618-source/browsermind/actions/workflows/ci.yml/badge.svg)](https://github.com/liuh40618-source/browsermind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

BrowserMind 是一个自主 AI Agent，能够规划任务、控制浏览器、理解网页内容并生成结构化报告。

## 功能

- **规划** — 将自然语言任务自动拆解为可执行步骤
- **浏览** — 通过 Playwright 控制真实浏览器（打开、点击、输入、滚动、截图）
- **理解** — 将网页解析为干净的结构化内容
- **报告** — 基于收集的信息生成结构化 Markdown 报告

## 快速开始

### 环境要求

- Python 3.10 或更高版本
- pip

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/liuh40618-source/browsermind.git
cd browsermind

# 2. 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 配置
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key
```

### 运行

```bash
python main.py
# 在浏览器中打开 http://localhost:8000
```

## 配置

### 环境变量

将 `.env.example` 复制为 `.env` 并配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 供应商：`openai`、`deepseek`、`qwen`、`zhipu` | `openai` |
| `LLM_API_KEY` | 你的 LLM API Key | （必填） |
| `LLM_MODEL` | 模型名称 | `gpt-4o` |
| `LLM_BASE_URL` | 自定义 API 地址（非 OpenAI 供应商使用） | （空） |
| `TAVILY_API_KEY` | Tavily 搜索 API Key（未配置时回退到 DuckDuckGo） | （空） |
| `BROWSER_HEADLESS` | 是否以无头模式运行浏览器 | `true` |
| `BROWSER_TIMEOUT` | 浏览器操作超时时间（毫秒） | `30000` |
| `HOST` | 服务绑定地址 | `127.0.0.1` |
| `PORT` | 服务端口 | `8000` |
| `CORS_ORIGINS` | CORS 允许的域名（逗号分隔，`*` 仅限开发环境） | `*` |

### LLM 供应商配置

| 供应商 | API 地址 | 可用模型 |
|--------|----------|----------|
| OpenAI | （留空） | gpt-4o、gpt-4o-mini |
| DeepSeek | `https://api.deepseek.com/v1` | deepseek-chat、deepseek-reasoner |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-plus、qwen-max |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | glm-4-plus、glm-4-air |

## 架构

```
用户 → 任务理解 → Planner 任务规划 → Agent 执行循环
                                        ├─ Browser 浏览器工具 (Playwright)
                                        ├─ Parser 网页解析 (BeautifulSoup + Readability)
                                        └─ Search 搜索工具 (DuckDuckGo / Tavily)
                                    → Analyst 分析报告 → 结构化报告
                                    → Reflection 反思 → 完成度检查
```

## 技术栈

| 层级 | 技术 |
|------|------|
| Agent 编排 | 纯 Python 异步循环（思考 → 行动 → 观察） |
| 浏览器自动化 | Playwright |
| 网页解析 | BeautifulSoup + Readability + html2text |
| LLM | OpenAI 兼容接口（通义千问 / DeepSeek / GPT） |
| 后端 | FastAPI + WebSocket |
| 前端 | React (CDN) + WebSocket 实时 UI |

## 项目结构

```
browsermind/
├── agent/
│   ├── __init__.py       # 包入口
│   ├── state.py          # 共享状态 AgentState（任务、计划、日志、提取信息）
│   ├── llm.py            # LLM 客户端 + 工具定义（8 个工具）
│   ├── planner.py        # 任务 → 计划步骤
│   ├── agent_loop.py     # 核心执行循环（思考 → 行动 → 观察）
│   ├── analyst.py        # 提取信息 → 结构化 Markdown 报告
│   └── reflection.py     # 完成度评估
├── tools/
│   ├── __init__.py       # 工具常量
│   ├── browser.py        # Playwright 封装（6 个能力）
│   ├── search.py         # DuckDuckGo / Tavily 搜索
│   └── parser.py         # HTML → 干净 Markdown
├── frontend/
│   └── index.html        # React 三栏工作台 UI
├── tests/
│   ├── test_store.py     # TaskStore 单元测试
│   ├── test_settings_store.py  # SettingsStore 单元测试
│   ├── test_parser.py    # Parser 单元测试
│   ├── test_config.py    # Settings 单元测试
│   └── test_state.py     # AgentState 单元测试
├── config.py             # 配置（LLM、浏览器、服务）
├── store.py              # 任务历史（SQLite）
├── settings_store.py     # 运行时配置存储（JSON）
├── main.py               # FastAPI 入口（REST + WebSocket + 静态文件）
├── .env.example          # 环境变量模板
├── requirements.txt      # 生产依赖
├── requirements-dev.txt  # 开发依赖
├── pyproject.toml        # 项目元数据 & 工具配置
└── LICENSE
```

## 界面布局

三栏式 AI Agent 工作台：

| 栏位 | 功能 |
|------|------|
| 左栏 — 任务面板 | 任务输入、快捷示例、执行计划 |
| 中栏 — 时间线 | 实时执行流程（Planner / Agent / Parser / Analyst） |
| 右栏 — 报告 | 结构化 Markdown 报告，支持下载 |

## API 参考

### REST 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/agent/run` | 执行任务（同步） |
| `GET` | `/api/tasks` | 获取任务历史 |
| `GET` | `/api/tasks/{id}` | 获取任务详情 |
| `DELETE` | `/api/tasks` | 清空所有任务 |
| `DELETE` | `/api/tasks/{id}` | 删除单个任务 |
| `GET` | `/api/settings` | 获取当前配置 |
| `POST` | `/api/settings` | 更新配置 |
| `POST` | `/api/settings/reset` | 重置为默认值 |
| `GET` | `/api/settings/presets` | 获取 LLM 供应商预设 |

### WebSocket

| 路径 | 说明 |
|------|------|
| `/api/agent/stream` | Agent 执行实时推送，支持多轮对话 |

## 开发

### 环境搭建

```bash
pip install -r requirements-dev.txt
playwright install chromium
```

### 运行测试

```bash
pytest                    # 运行全部测试
pytest -v                 # 详细输出
pytest --cov              # 含覆盖率报告
```

### 代码检查

```bash
ruff check .              # Lint 检查
black .                   # 格式化
```

## 贡献

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## 许可证

本项目基于 MIT 许可证开源 — 详见 [LICENSE](LICENSE) 文件。

## 行为准则

请参阅 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
