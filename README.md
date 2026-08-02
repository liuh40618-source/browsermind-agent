# BrowserMind

[![CI](https://github.com/liuh40618-source/browsermind/actions/workflows/ci.yml/badge.svg)](https://github.com/liuh40618-source/browsermind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

BrowserMind is an autonomous AI agent capable of planning tasks, controlling browsers, understanding web content and generating structured reports.

## What it does

- **Plans** — Decomposes natural-language tasks into actionable steps
- **Browses** — Controls a real browser via Playwright (open, click, type, scroll, screenshot)
- **Understands** — Parses web pages into clean structured content
- **Reports** — Generates structured Markdown reports from gathered information

## Quick Start

### Prerequisites

- Python 3.10 or higher
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/liuh40618-source/browsermind.git
cd browsermind

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Configure
cp .env.example .env
# Edit .env with your LLM API key
```

### Running

```bash
python main.py
# Open http://localhost:8000 in your browser
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider: `openai`, `deepseek`, `qwen`, `zhipu` | `openai` |
| `LLM_API_KEY` | Your LLM API key | (required) |
| `LLM_MODEL` | Model name | `gpt-4o` |
| `LLM_BASE_URL` | Custom API base URL (for non-OpenAI providers) | (empty) |
| `TAVILY_API_KEY` | Tavily search API key (falls back to DuckDuckGo if empty) | (empty) |
| `BROWSER_HEADLESS` | Run browser in headless mode | `true` |
| `BROWSER_TIMEOUT` | Browser action timeout (ms) | `30000` |
| `HOST` | Server bind address | `127.0.0.1` |
| `PORT` | Server port | `8000` |
| `CORS_ORIGINS` | Comma-separated CORS origins (`*` for dev only) | `*` |

### LLM Provider Setup

| Provider | Base URL | Example Models |
|----------|----------|----------------|
| OpenAI | (leave empty) | gpt-4o, gpt-4o-mini |
| DeepSeek | `https://api.deepseek.com/v1` | deepseek-chat, deepseek-reasoner |
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-plus, qwen-max |
| Zhipu | `https://open.bigmodel.cn/api/paas/v4` | glm-4-plus, glm-4-air |

## Architecture

```
User → Task Understanding → Planner → Agent Execution Loop
                                        ├─ Browser Tool (Playwright)
                                        ├─ Parser (BeautifulSoup + Readability)
                                        └─ Search Tool (DuckDuckGo / Tavily)
                                    → Analyst → Report
                                    → Reflection → Completion Check
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Orchestration | Pure Python async loop (think → act → observe) |
| Browser Automation | Playwright |
| Web Parsing | BeautifulSoup + Readability + html2text |
| LLM | OpenAI-compatible API (Qwen / DeepSeek / GPT) |
| Backend | FastAPI + WebSocket |
| Frontend | React (CDN) + WebSocket real-time UI |

## Project Structure

```
browsermind/
├── agent/
│   ├── __init__.py       # Package exports
│   ├── state.py          # Shared AgentState (task, plan, logs, extracted_info)
│   ├── llm.py            # LLM client + tool schemas (8 tools)
│   ├── planner.py        # Task → Plan steps
│   ├── agent_loop.py     # Core execution loop (think → act → observe)
│   ├── analyst.py        # Extracted info → structured Markdown report
│   └── reflection.py     # Completion evaluation
├── tools/
│   ├── __init__.py       # Tool name constants
│   ├── browser.py        # Playwright wrapper (6 capabilities)
│   ├── search.py         # DuckDuckGo / Tavily search
│   └── parser.py         # HTML → clean Markdown
├── frontend/
│   └── index.html        # React three-column workbench UI
├── tests/
│   ├── test_store.py     # TaskStore unit tests
│   ├── test_settings_store.py  # SettingsStore unit tests
│   ├── test_parser.py    # Parser unit tests
│   ├── test_config.py    # Settings unit tests
│   └── test_state.py     # AgentState unit tests
├── config.py             # Settings (LLM, browser, server)
├── store.py              # Task history (SQLite)
├── settings_store.py     # Runtime config storage (JSON)
├── main.py               # FastAPI entry (REST + WebSocket + static)
├── .env.example          # Environment template
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── pyproject.toml        # Project metadata & tool config
└── LICENSE
```

## UI Layout

Three-column AI Agent workbench:

| Column | Function |
|--------|----------|
| Left — Task Panel | Task input, quick examples, execution plan |
| Center — Timeline | Real-time execution flow (Planner / Agent / Parser / Analyst) |
| Right — Report | Structured Markdown report with download |

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/agent/run` | Run a task (synchronous) |
| `GET` | `/api/tasks` | List task history |
| `GET` | `/api/tasks/{id}` | Get task detail |
| `DELETE` | `/api/tasks` | Clear all tasks |
| `DELETE` | `/api/tasks/{id}` | Delete a task |
| `GET` | `/api/settings` | Get current settings |
| `POST` | `/api/settings` | Update settings |
| `POST` | `/api/settings/reset` | Reset to defaults |
| `GET` | `/api/settings/presets` | Get LLM provider presets |

### WebSocket

| Path | Description |
|------|-------------|
| `/api/agent/stream` | Real-time agent execution streaming with multi-turn support |

## Development

### Setup

```bash
pip install -r requirements-dev.txt
playwright install chromium
```

### Running Tests

```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest --cov              # With coverage report
```

### Linting

```bash
ruff check .              # Lint
black .                   # Format
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
