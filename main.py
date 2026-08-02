"""
BrowserMind - FastAPI 主入口

阶段5：产品包装
- /api/agent/run：接受任务，Agent 自主循环执行
- /api/agent/stream：WebSocket 实时推送执行过程
- /api/tasks：任务历史查询
- / ：托管前端工作台（React 三栏 UI）
- /admin：后台管理页面
- /static：前端静态资源
"""

import os
import json
import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

# Windows 上默认的 SelectorEventLoop 不支持 subprocess，
# Playwright 启动浏览器需要 subprocess，因此切换到 ProactorEventLoop。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools.browser import BrowserTool
from agent.llm import LLMClient
from agent.planner import Planner
from agent.reflection import Reflection
from agent.analyst import Analyst
from agent.agent_loop import AgentLoop
from config import settings
from store import store
from settings_store import settings_store, PRESETS


# ── 路径 ────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"


# ── 全局实例 ────────────────────────────────────────────

browser_tool = BrowserTool()
llm_client = LLMClient()
planner = Planner(llm_client)
reflection = Reflection(llm_client)
analyst = Analyst(llm_client)


# ── 生命周期 ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await browser_tool.start()
    yield
    await browser_tool.close()


app = FastAPI(
    title="BrowserMind",
    description="Autonomous AI agent for browsing, understanding, and reporting.",
    version="0.6.0",
    lifespan=lifespan,
)

# CORS（开发时前端可能独立运行在不同端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 前端静态文件托管 ────────────────────────────────────

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_frontend():
    """托管前端工作台首页。"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(
            str(index_path),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {"error": "Frontend not found", "path": str(index_path)}


# ── API 端点 ────────────────────────────────────────────

# ── 请求模型 ──

class TaskRequest(BaseModel):
    task: str


class ToolRequest(BaseModel):
    arguments: dict[str, Any] = {}


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    tavily_api_key: str | None = None


# ── API 端点 ────────────────────────────────────────────

@app.get("/api/health")
async def health():
    browser_status = "ready" if browser_tool._page else "not_started"
    return {"status": "ok", "version": "0.6.0", "browser": browser_status}


@app.post("/api/agent/run")
async def agent_run(req: TaskRequest):
    """接受用户任务，Agent 自主循环执行，返回完整结果。"""
    loop = AgentLoop(browser_tool, llm_client, planner, reflection, analyst)
    state = await loop.run(req.task)

    task_id = store.save_task(**state.to_store_dict())

    return {
        "id": task_id,
        "task": state.task,
        "status": state.status,
        "plan": state.plan,
        "visited_pages": state.visited_pages,
        "extracted_info": state.extracted_info,
        "final_report": state.final_report,
        "logs": state.logs,
        "duration_seconds": state.duration_seconds,
    }


# ── WebSocket 辅助函数 ──────────────────────────────────

def _classify_ws_message(log: dict) -> tuple[str, Any]:
    """将日志分类为 WebSocket 消息类型，返回 (type, data)。"""
    action = log.get("action", "")
    agent = log.get("agent", "")
    detail = log.get("detail", "")

    if action == "plan":
        try:
            return "plan", json.loads(detail)
        except (json.JSONDecodeError, Exception):
            return "log", log
    elif action == "plan_steps":
        try:
            return "plan_steps", json.loads(detail)
        except (json.JSONDecodeError, Exception):
            return "log", log
    elif agent == "Reflection" and action == "反思结果":
        try:
            return "reflection", json.loads(detail)
        except (json.JSONDecodeError, Exception):
            return "log", log
    return "log", log


async def _log_sender(ws: WebSocket, log_queue: asyncio.Queue):
    """从队列消费日志，按顺序通过 WebSocket 发送。"""
    while True:
        try:
            log = await log_queue.get()
        except Exception:
            break
        if log is None:
            break
        try:
            msg_type, data = _classify_ws_message(log)
            await ws.send_json({"type": msg_type, "data": data})
        except Exception:
            break


async def _message_listener(
    ws: WebSocket,
    decision_queue: asyncio.Queue[str],
    instruction_queue: asyncio.Queue[str],
    disconnected: asyncio.Event,
):
    """监听前端消息：决策（decision）和追加指令（instruction）。"""
    try:
        while True:
            try:
                msg = await ws.receive_json()
            except (WebSocketDisconnect, Exception):
                break
            msg_type = msg.get("type", "")
            if msg_type == "decision":
                await decision_queue.put(msg.get("decision", "continue"))
            elif msg_type == "instruction":
                text = msg.get("text", "")
                if text:
                    await instruction_queue.put(text)
    finally:
        disconnected.set()
        try:
            decision_queue.put_nowait("continue")
        except Exception:
            pass


async def _send_done(ws: WebSocket, state_obj, task_id: int):
    """推送 done 消息到前端。"""
    await ws.send_json({
        "type": "done",
        "data": {
            "id": task_id,
            "task": state_obj.task,
            "status": state_obj.status,
            "plan": state_obj.plan,
            "extracted_info": state_obj.extracted_info,
            "final_report": state_obj.final_report,
            "visited_pages": state_obj.visited_pages,
            "duration_seconds": state_obj.duration_seconds,
        },
    })


async def _run_agent_round(
    ws: WebSocket,
    task: str,
    log_queue: asyncio.Queue,
    decision_queue: asyncio.Queue[str],
    instruction_queue: asyncio.Queue[str],
    prev_state=None,
) -> "AgentState":
    """执行一轮 Agent 任务并保存结果。"""
    loop = AgentLoop(browser_tool, llm_client, planner, reflection, analyst)
    loop.on_log(lambda log: log_queue.put_nowait(log))

    def on_decision(evaluation: dict):
        log_queue.put_nowait({
            "time": datetime.now().strftime("%H:%M:%S"),
            "agent": "System",
            "action": "等待用户决策",
            "detail": json.dumps({
                "score": evaluation.get("score", 0),
                "reason": evaluation.get("reason", ""),
                "missing": evaluation.get("missing", []),
                "next_action": evaluation.get("next_action"),
                "success": evaluation.get("success", False),
            }, ensure_ascii=False),
        })

    loop.on_decision(decision_queue, on_decision)
    loop.set_instruction_queue(instruction_queue)
    if prev_state:
        loop.set_previous_state(prev_state)

    state = await loop.run(task)
    task_id = store.save_task(**state.to_store_dict())
    await _send_done(ws, state, task_id)
    return state


@app.websocket("/api/agent/stream")
async def agent_stream(ws: WebSocket):
    """WebSocket 端点：实时推送 Agent 执行过程（支持多轮对话）。"""
    await ws.accept()

    sender_task: asyncio.Task | None = None
    listener_task: asyncio.Task | None = None
    log_queue: asyncio.Queue | None = None

    try:
        try:
            data = await asyncio.wait_for(ws.receive_json(), timeout=30)
        except asyncio.TimeoutError:
            await ws.send_json({"type": "error", "message": "Connection timeout: no task received"})
            return
        task = data.get("task", "")
        if not task:
            await ws.send_json({"type": "error", "message": "No task provided"})
            return

        log_queue = asyncio.Queue()
        decision_queue: asyncio.Queue[str] = asyncio.Queue()
        instruction_queue: asyncio.Queue[str] = asyncio.Queue()
        disconnected = asyncio.Event()

        sender_task = asyncio.create_task(_log_sender(ws, log_queue))
        listener_task = asyncio.create_task(
            _message_listener(ws, decision_queue, instruction_queue, disconnected)
        )

        # 第一轮：执行初始任务
        state = await _run_agent_round(ws, task, log_queue, decision_queue, instruction_queue)

        # 后续轮次：等待追加指令（多轮对话，10 分钟超时）
        prev_state = state
        while not disconnected.is_set():
            try:
                instruction = await asyncio.wait_for(instruction_queue.get(), timeout=600)
            except asyncio.TimeoutError:
                break
            if disconnected.is_set():
                break

            follow_up_task = (
                f"原始任务：{task}\n\n"
                f"前序报告摘要：{prev_state.final_report[:500] if prev_state.final_report else '无'}\n\n"
                f"追加要求：{instruction}"
            )
            state = await _run_agent_round(ws, follow_up_task, log_queue, decision_queue, instruction_queue, prev_state)
            prev_state = state

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if listener_task and not listener_task.done():
            listener_task.cancel()
            try:
                await listener_task
            except (asyncio.CancelledError, Exception):
                pass
        if sender_task and not sender_task.done() and log_queue is not None:
            await log_queue.put(None)
            try:
                await asyncio.wait_for(sender_task, timeout=5)
            except (asyncio.TimeoutError, Exception):
                sender_task.cancel()
                try:
                    await sender_task
                except (asyncio.CancelledError, Exception):
                    pass


# ── 任务历史 API ────────────────────────────────────────

@app.get("/api/tasks")
async def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取任务历史列表。"""
    tasks = store.list_tasks(limit=limit, offset=offset)
    total = store.count_tasks()
    return {
        "tasks": tasks,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int):
    """获取单个任务详情。"""
    task = store.get_task(task_id)
    if not task:
        return {"error": "Task not found", "id": task_id}
    return task


@app.delete("/api/tasks")
async def clear_all_tasks():
    """清空所有任务记录。"""
    count = store.clear_all_tasks()
    return {"ok": True, "deleted": count}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务记录。"""
    deleted = store.delete_task(task_id)
    if deleted:
        return {"ok": True, "id": task_id}
    return {"error": "Task not found", "id": task_id}


@app.post("/api/browser/{tool_name}")
async def call_browser_tool(tool_name: str, req: ToolRequest):
    """直接调用浏览器工具（用于测试）。"""
    result = await browser_tool.execute(tool_name, req.arguments)
    return result


# ── 设置 API ────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    """获取当前配置（不含 API Key）。"""
    user_cfg = settings_store.get_all()
    return {
        "llm_provider": user_cfg.get("llm_provider", settings.llm_provider),
        "llm_model": user_cfg.get("llm_model", settings.llm_model),
        "llm_base_url": user_cfg.get("llm_base_url", settings.llm_base_url),
        "has_api_key": bool(settings_store.get("llm_api_key", settings.llm_api_key)),
        "has_tavily_key": bool(settings_store.get("tavily_api_key", settings.tavily_api_key)),
    }


@app.get("/api/settings/presets")
async def get_presets():
    """获取供应商预设模板。"""
    return PRESETS


@app.post("/api/settings")
async def update_settings(req: SettingsUpdate):
    """保存用户配置，立即生效。"""
    data = req.model_dump(exclude_none=True)
    if not data:
        return {"error": "No settings provided"}

    # 1. 保存到 JSON 文件
    settings_store.update(data)

    # 2. 更新内存中的 settings
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    # 3. 重新加载 LLM 客户端
    llm_client.reload()

    return {"ok": True, "settings": settings_store.get_all()}


@app.post("/api/settings/reset")
async def reset_settings():
    """重置为用户配置，回退到 .env / 默认值。"""
    settings_store.reset()

    # 重新从 .env 加载 defaults
    from config import Settings
    defaults = Settings()
    for field in ["llm_provider", "llm_model", "llm_api_key", "llm_base_url", "tavily_api_key"]:
        setattr(settings, field, getattr(defaults, field))

    llm_client.reload()
    return {"ok": True}


# ── 启动 ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
