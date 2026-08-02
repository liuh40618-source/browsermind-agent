# BrowserMind

BrowserMind is an autonomous AI agent capable of planning tasks, controlling browsers, understanding web content and generating structured reports.

## What it does

- **Plans** — Decomposes natural-language tasks into actionable steps
- **Browses** — Controls a real browser via Playwright (open, click, type, scroll, screenshot)
- **Understands** — Parses web pages into clean structured content
- **Reports** — Generates structured Markdown reports from gathered information

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Configure
cp .env.example .env
# Edit .env with your LLM API key

# 3. Run
python main.py
# Open http://localhost:8000 in your browser
```

## Architecture

```
User → Task Understanding → Planner → Agent Execution Loop
                                        ├─ Browser Tool (Playwright)
                                        ├─ Parser (BeautifulSoup + Readability)
                                        └─ Search Tool (DuckDuckGo)
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
│   ├── state.py          # Shared AgentState (task, plan, logs, extracted_info)
│   ├── llm.py            # LLM client + tool schemas (8 tools)
│   ├── planner.py        # Task → Plan steps
│   ├── agent_loop.py     # Core execution loop (think → act → observe)
│   ├── analyst.py        # Extracted info → structured Markdown report
│   └── reflection.py     # Completion evaluation
├── tools/
│   ├── browser.py        # Playwright wrapper (6 capabilities)
│   ├── search.py         # DuckDuckGo search (no API key needed)
│   └── parser.py         # HTML → clean Markdown
├── frontend/
│   └── index.html        # React three-column workbench UI
├── config.py             # Settings (LLM, browser, server)
├── main.py               # FastAPI entry (REST + WebSocket + static)
├── .env                  # Environment configuration
└── requirements.txt
```

## UI Layout

Three-column AI Agent workbench:

| Column | Function |
|--------|----------|
| Left — Task Panel | Task input, quick examples, execution plan |
| Center — Timeline | Real-time execution flow (Planner / Agent / Parser / Analyst) |
| Right — Report | Structured Markdown report with download |

## Development Stages

1. **Browser Control** — FastAPI + Playwright + LLM ✅
2. **Agent Loop** — State + Planner + Tool Calling ✅
3. **Web Understanding** — Parser + Extract ✅
4. **Report Generation** — Analyst Agent ✅
5. **Product Polish** — React UI + WebSocket + Demo ✅
