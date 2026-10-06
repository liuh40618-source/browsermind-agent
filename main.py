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
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

# ── 日志框架：文件 + 控制台双输出 ──────────────────────────
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "browsermind.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("browsermind")

# Windows 上默认的 SelectorEventLoop 不支持 subprocess，
# Playwright 启动浏览器需要 subprocess，因此切换到 ProactorEventLoop。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, ValidationError

from tools.browser import BrowserTool, BrowserSession
from agent.llm import LLMClient
from agent.planner import Planner
from agent.reflection import Reflection
from agent.analyst import Analyst
from agent.agent_loop import AgentLoop
from agent.state import AgentState
from config import settings, resolve_api_key, environment_settings
from store import store
from settings_store import settings_store, PRESETS, ConfigValidationError


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
    logger.info("BrowserMind 启动 (version=%s)", app.version)
    await browser_tool.start()
    logger.info("浏览器已启动 headless=%s", settings.browser_headless)
    yield
    await browser_tool.close()
    logger.info("BrowserMind 关闭，浏览器已释放")


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

# ── 可选鉴权：设置 AUTH_TOKEN 后生效 ─────────────────────
# REST：请求需带 X-Auth-Token header；WebSocket：首次消息需带 token 字段
# 未设置 auth_token 时完全放行（本地开发零打扰）

def _auth_enabled() -> bool:
    return bool(settings.auth_token)


def _check_rest_token(request) -> bool:
    """校验 REST 请求的 X-Auth-Token header。"""
    if not _auth_enabled():
        return True
    token = request.headers.get("X-Auth-Token", "")
    return secrets.compare_digest(token.encode(), settings.auth_token.encode())


@app.middleware("http")
async def auth_middleware(request, call_next):
    if request.url.path in ("/api/health", "/") or request.url.path.startswith("/static/"):
        return await call_next(request)
    if _check_rest_token(request):
        return await call_next(request)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=401, content={"detail": "访问令牌缺失或错误"})


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
    task: str = Field(min_length=1, max_length=12000)

    @field_validator("task", mode="before")
    @classmethod
    def strip_task(cls, value):
        return value.strip() if isinstance(value, str) else value


class ToolRequest(BaseModel):
    arguments: dict[str, Any] = {}


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    tavily_api_key: str | None = None
    # 按供应商配置 Key：{"deepseek": "sk-...", "qwen": "sk-..."}
    provider_api_keys: dict[str, str] | None = None


class RegenerateRequest(BaseModel):
    task_id: int
    instruction: str | None = None


# ── API 端点 ────────────────────────────────────────────

@app.get("/api/health")
async def health():
    browser_status = "ready" if browser_tool._browser else "not_started"
    llm_ready = bool(settings.llm_api_key) and settings.llm_api_key not in ("", "your-api-key-here")
    return {
        "status": "ok",
        "version": "0.6.0",
        "browser": browser_status,
        "llm_configured": llm_ready,
        "auth_required": _auth_enabled(),
        "hint": None if llm_ready else "LLM API Key 未配置，请到设置面板填写",
    }


@app.post("/api/agent/run")
async def agent_run(req: TaskRequest):
    """接受用户任务，Agent 自主循环执行，返回完整结果。"""
    session = await browser_tool.new_session()
    try:
        loop = AgentLoop(session, llm_client, planner, reflection, analyst)
        state = await loop.run(req.task)
    finally:
        await session.close()

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


@app.post("/api/report/regenerate")
async def regenerate_report(req: RegenerateRequest):
    """轻量重生成报告：复用已抓取的信息（extracted_info），不重新浏览网页。

    用于「报告写得不好 / 想换个角度重述」等场景，成本远低于重跑整轮 Agent。
    可选 instruction 会在生成时作为特别要求注入，引导 Analyst 调整侧重点。
    """
    rec = store.get_task(req.task_id)
    if not rec:
        logger.warning("regenerate 未找到任务 id=%s", req.task_id)
        raise HTTPException(status_code=404, detail="task not found")

    task_text = rec["task"]
    if req.instruction:
        task_text = f"{task_text}\n\n[重新生成时的特别要求] {req.instruction}"

    try:
        report = await analyst.generate_report(
            task=task_text,
            extracted_info=rec["extracted_info"],
            visited_pages=rec["visited_pages"],
        )
    except Exception as e:
        logger.exception("regenerate 报告生成失败 task_id=%s", req.task_id)
        raise HTTPException(status_code=502, detail=f"report generation failed: {e}")

    store.update_report(req.task_id, report)
    logger.info("regenerate 完成 task_id=%s (报告 %d 字符)", req.task_id, len(report))
    return {"task_id": req.task_id, "final_report": report}


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
        try:
            if log is None:
                return
            msg_type, data = _classify_ws_message(log)
            await ws.send_json({"type": msg_type, "data": data})
        except Exception:
            pass
        finally:
            log_queue.task_done()


async def _message_listener(
    ws: WebSocket,
    decision_queue: asyncio.Queue[str],
    instruction_queue: asyncio.Queue[str],
    disconnected: asyncio.Event,
    cancel_event: asyncio.Event | None = None,
):
    """监听前端消息：决策（decision）、追加指令（instruction）和取消（cancel）。"""
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
            elif msg_type == "cancel":
                if cancel_event is not None:
                    cancel_event.set()
                instruction_queue.put_nowait("")
    finally:
        disconnected.set()
        if cancel_event is not None:
            cancel_event.set()
        instruction_queue.put_nowait("")
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
            "plan_steps": state_obj.plan_steps,
            "extracted_info": state_obj.extracted_info,
            "final_report": state_obj.final_report,
            "visited_pages": state_obj.visited_pages,
            "duration_seconds": state_obj.duration_seconds,
        },
    })


async def _run_agent_round(
    ws: WebSocket,
    session: BrowserSession,
    task: str,
    log_queue: asyncio.Queue,
    decision_queue: asyncio.Queue[str],
    instruction_queue: asyncio.Queue[str],
    prev_state=None,
    parent_id: int | None = None,
    cancel_event: asyncio.Event | None = None,
) -> tuple["AgentState", int]:
    """执行一轮 Agent 任务并保存结果。返回 (state, task_id)。"""
    loop = AgentLoop(session, llm_client, planner, reflection, analyst)
    loop.on_log(lambda log: log_queue.put_nowait(log))
    if cancel_event is not None:
        loop.set_cancel_event(cancel_event)

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
    task_dict = state.to_store_dict()
    if parent_id is not None:
        task_dict["parent_id"] = parent_id
    task_id = store.save_task(**task_dict)
    await log_queue.join()
    await _send_done(ws, state, task_id)
    return state, task_id


@app.websocket("/api/agent/stream")
async def agent_stream(ws: WebSocket):
    """WebSocket 端点：实时推送 Agent 执行过程（支持多轮对话）。"""
    await ws.accept()

    sender_task: asyncio.Task | None = None
    listener_task: asyncio.Task | None = None
    log_queue: asyncio.Queue | None = None
    session: BrowserSession | None = None

    try:
        try:
            data = await asyncio.wait_for(ws.receive_json(), timeout=30)
        except asyncio.TimeoutError:
            await ws.send_json({"type": "error", "message": "Connection timeout: no task received"})
            return

        # 可选鉴权：首次消息需带 token（若已配置 AUTH_TOKEN）
        if not isinstance(data, dict):
            await ws.send_json({"type": "error", "message": "任务消息必须是对象"})
            return
        if _auth_enabled() and data.get("token", "") != settings.auth_token:
            await ws.send_json({"type": "error", "message": "未授权：token 缺失或错误"})
            await ws.close(code=4401)
            return

        try:
            task = TaskRequest.model_validate(data).task
        except ValidationError:
            await ws.send_json({"type": "error", "message": "任务须为 1 至 12000 字符"})
            return

        log_queue = asyncio.Queue()
        decision_queue: asyncio.Queue[str] = asyncio.Queue()
        instruction_queue: asyncio.Queue[str] = asyncio.Queue()
        disconnected = asyncio.Event()
        cancel_event = asyncio.Event()

        sender_task = asyncio.create_task(_log_sender(ws, log_queue))
        listener_task = asyncio.create_task(
            _message_listener(ws, decision_queue, instruction_queue, disconnected, cancel_event)
        )

        # 每条 WS 连接独占一个浏览器会话（独立 context + page），并发任务互不串台
        session = await browser_tool.new_session()

        # 第一轮：执行初始任务
        state, prev_id = await _run_agent_round(
            ws, session, task, log_queue, decision_queue, instruction_queue,
            cancel_event=cancel_event,
        )

        # 后续轮次：等待追加指令（多轮对话，10 分钟超时）
        prev_state = state
        while not disconnected.is_set():
            if cancel_event.is_set():
                break
            try:
                instruction = await asyncio.wait_for(instruction_queue.get(), timeout=600)
            except asyncio.TimeoutError:
                break
            if disconnected.is_set() or cancel_event.is_set():
                break

            follow_up_task = (
                f"原始任务：{task}\n\n"
                f"[已有成果参考] 上一轮已收集 {len(prev_state.extracted_info)} 条信息、"
                f"访问了 {len(prev_state.visited_pages)} 个页面，并产出过一份报告（见下，仅供参考，不可直接当作最终答案）：\n"
                f"{prev_state.final_report[:500] if prev_state.final_report else '无'}\n\n"
                f"[追加要求] {instruction}\n\n"
                f"重要：你必须执行新的工具调用（search / open_page / get_text / click 等）来完成上述追加要求，"
                f"然后基于全部信息（含上一轮已收集的）生成新的完整报告。不要仅改写旧报告就结束。"
            )
            state, prev_id = await _run_agent_round(
                ws, session, follow_up_task,
                log_queue, decision_queue, instruction_queue,
                prev_state, parent_id=prev_id, cancel_event=cancel_event,
            )
            prev_state = state

    except WebSocketDisconnect:
        logger.info("WebSocket 断开（客户端主动）")
        pass
    except Exception as e:
        logger.exception("WebSocket 执行异常: %s", e)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if session is not None:
            try:
                await session.close()
            except Exception:
                pass
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
        try:
            await ws.close()
        except (RuntimeError, WebSocketDisconnect):
            pass


# ── 任务历史 API ────────────────────────────────────────

@app.get("/api/tasks")
async def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=200),
    status: str = Query("", max_length=30),
    summary: bool = False,
):
    """获取任务历史列表。"""
    tasks = store.list_tasks(limit=limit, offset=offset, q=q, status=status, summary=summary)
    total = store.count_tasks(q=q, status=status)
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
        raise HTTPException(status_code=404, detail="Task not found")
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
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/api/browser/{tool_name}")
async def call_browser_tool(tool_name: str, req: ToolRequest):
    """直接调用浏览器工具（用于测试）。"""
    session = await browser_tool.new_session()
    try:
        result = await session.execute(tool_name, req.arguments)
    finally:
        await session.close()
    return result


# ── 设置 API ────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    """获取当前配置（不含 API Key 明文，但返回各供应商是否已配置 Key）。"""
    user_cfg = settings_store.get_all()
    provider = user_cfg.get("llm_provider", settings.llm_provider)
    configured = settings_store.providers_with_keys()
    if resolve_api_key(environment_settings.llm_provider):
        configured.add(environment_settings.llm_provider)
    return {
        "llm_provider": provider,
        "llm_model": user_cfg.get("llm_model", settings.llm_model),
        "llm_base_url": user_cfg.get("llm_base_url", settings.llm_base_url),
        "has_api_key": bool(resolve_api_key(provider)),
        "has_tavily_key": bool(settings_store.get("tavily_api_key", settings.tavily_api_key)),
        # 每个供应商是否已配置 Key（前端据此把模型分成"可用/需配置"两组）
        "providers_with_keys": sorted(configured),
    }


@app.get("/api/settings/presets")
async def get_presets():
    """获取供应商预设模板。"""
    return PRESETS


@app.post("/api/settings")
async def update_settings(req: SettingsUpdate):
    """保存用户配置，立即生效。非法配置返回 422 + 具体原因。"""
    data = req.model_dump(exclude_none=True)
    if not data:
        return {"error": "No settings provided"}

    # 空白输入保留现有密钥；所有字段验证通过后统一保存。
    data = {key: value for key, value in data.items()
            if key not in ("llm_api_key", "tavily_api_key") or value != ""}
    data.setdefault("llm_provider", settings.llm_provider)

    # 1. 校验并保存到 JSON 文件（非法值抛 ConfigValidationError）
    try:
        settings_store.update(data)
    except ConfigValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 2. 更新内存中的 settings（含 provider 切换后同步对应 Key）
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    # provider 切换后，用新 provider 的 Key 覆盖内存中的 llm_api_key
    settings.llm_api_key = resolve_api_key(settings.llm_provider)

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
