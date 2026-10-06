"""Local UI fixture: python -m uvicorn tests.workspace_preview:app --port 8001.

Serves the real frontend with deterministic, in-memory data and no model calls.
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from settings_store import PRESETS

app = FastAPI()
frontend = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=frontend), name="static")
REPORT = """# Research verification

| Product | Deployment | Source |
| --- | --- | --- |
| Alpha | Self-hosted | [Documentation](https://example.com/docs) |
| Beta | Cloud | [Documentation](https://example.org/docs) |

## Findings

Evidence is available for the deployment comparison. Pricing needs another source.

<script>alert('unsafe')</script><img src="https://example.com/tracker.png">
"""
records = [
    dict(id=i, task=f"Research sample {i}", status="done", final_report=REPORT,
         report_excerpt="Deployment comparison", created_at="2026-09-21T12:00:00",
         duration_seconds=42, parent_id=None)
    for i in range(1, 24)
]


@app.get("/")
async def index():
    return FileResponse(frontend / "index.html")


@app.get("/api/health")
async def health():
    return dict(status="ok", browser="ready", auth_required=False)


@app.get("/api/settings")
async def settings():
    return dict(llm_provider="openai", llm_model="UI test fixture", llm_base_url="",
                has_api_key=True, providers_with_keys=["openai"])


@app.get("/api/settings/presets")
async def presets():
    return PRESETS


@app.get("/api/tasks")
async def tasks(limit: int = 20, offset: int = 0, q: str = "", status: str = ""):
    matched = [r for r in records if q.lower() in r["task"].lower()
               and (not status or r["status"] == status)]
    return dict(tasks=matched[offset:offset + limit], total=len(matched))


@app.get("/api/tasks/{task_id}")
async def detail(task_id: int):
    return next(r for r in records if r["id"] == task_id)


@app.post("/api/report/regenerate")
async def regenerate():
    return dict(final_report=REPORT + "\n## Regenerated\n\nUpdated report.\n")


@app.websocket("/api/agent/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    try:
        initial = await ws.receive_json()
        if initial.get("task") == "error":
            await ws.send_json(dict(type="error", message="Simulated connection error"))
            return
        round_id = 100
        while True:
            steps = [dict(goal="Compare deployment", status="done"),
                     dict(goal="Verify pricing", status="pending")]
            await ws.send_json(dict(type="plan_steps", data=steps))
            await ws.send_json(dict(type="log", data=dict(agent="Browser", action="Inspect sources",
                                                          detail="Source details. " * 40)))
            await ws.send_json(dict(type="reflection", data=dict(score=65, reason="More evidence needed")))
            await ws.send_json(dict(type="log", data=dict(agent="System", action="等待用户决策",
                detail=json.dumps(dict(score=65, reason="Verify pricing before continuing.")))))
            cancelled = False
            while True:
                message = await ws.receive_json()
                if message.get("type") == "instruction":
                    await ws.send_json(dict(type="log", data=dict(agent="System", action="Adjustment received",
                                                                  detail=message["text"])))
                elif message.get("type") in ("decision", "cancel"):
                    cancelled = message["type"] == "cancel"
                    break
            await asyncio.sleep(0.2)
            await ws.send_json(dict(type="done", data=dict(id=round_id,
                status="cancelled" if cancelled else "partial", plan_steps=steps,
                visited_pages=["https://example.com/docs", "javascript:alert(1)"],
                final_report=REPORT, duration_seconds=42)))
            if cancelled:
                break
            message = await ws.receive_json()
            if message.get("type") != "instruction":
                break
            round_id += 1
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()
