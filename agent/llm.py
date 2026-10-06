"""
LLM 调用层
使用 OpenAI 兼容接口（通义千问 / DeepSeek / 智谱 等均兼容）。

阶段2：支持多轮对话历史，让 Agent 能"思考→行动→观察→继续思考"。
"""

import json
from typing import Any
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError
from config import settings
from tools import retry_async


# ── 浏览器工具描述 ──────────────────────────────────────

BROWSER_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": "Open a web page by URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to navigate to, e.g. https://github.com",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an element on the page by its visible text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The visible text of the element to click, e.g. 'Pricing'",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type",
            "description": "Type text into an input field.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "Placeholder text, label, or CSS selector of the input field",
                    },
                    "value": {
                        "type": "string",
                        "description": "The text to type into the field",
                    },
                },
                "required": ["selector", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the page to load lazy-loaded content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["down", "up"],
                        "description": "Scroll direction, default 'down'",
                    },
                    "times": {
                        "type": "integer",
                        "description": "Number of scroll steps, default 3",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the current page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_text",
            "description": "Get the text content of the current page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the web for information. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call this when you have gathered enough information and want to finish with a summary. Also call this if you determine the task is impossible to complete after reasonable attempts — explain why in the summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "A summary of all information gathered, or an explanation of why the task cannot be completed",
                    }
                },
                "required": ["summary"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are BrowserMind, an autonomous AI agent that controls a web browser to accomplish tasks.

You work in a loop: think → act → observe → think again.

Available tools:
- search(query): Search the web for information
- open_page(url): Open a web page
- click(text): Click an element by its visible text
- type(selector, value): Type text into an input field
- scroll(direction, times): Scroll the page
- screenshot(): Take a screenshot
- get_text(): Get page text content
- finish(summary): Call when task is complete, with a summary of findings

Rules:
1. Always think first, then call exactly ONE tool.
2. After each tool result, decide the next action based on what you observed.
3. Be efficient: don't visit the same page twice, don't repeat searches.
4. When you have enough information to answer the task, call finish() with a summary.
5. If a tool fails, try an alternative approach.
6. If after several attempts you determine the task is impossible (information doesn't exist, requires login, paywall, or the sources are unreachable), call finish() and honestly explain WHY the task cannot be completed. Do NOT keep looping indefinitely."""


class LLMClient:
    """LLM 客户端，封装对大模型的调用，支持多轮对话。"""

    def __init__(self):
        self._ready = False
        self._client = None
        self._model = None
        self._reload()

    # LLM 请求超时（秒）
    _REQUEST_TIMEOUT = 120

    def _reload(self):
        """根据当前 settings 重新创建客户端。

        关键改动：缺 Key 时不再抛异常，而是标记 _ready=False，
        让整个应用在「未配置 API Key」时也能正常启动（降级到设置页）。
        真正的报错推迟到首次真正调用大模型时（_ensure_ready）。
        """
        base_url = settings.llm_base_url or None
        # 按当前 provider 取对应的 API Key（支持多供应商各自配置 Key）
        try:
            from settings_store import settings_store
            api_key = settings_store.get_key_for_provider(settings.llm_provider) or settings.llm_api_key
        except Exception:
            api_key = settings.llm_api_key
        if not api_key or api_key in ("your-api-key-here", ""):
            self._ready = False
            self._client = None
            self._model = None
            return
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=self._REQUEST_TIMEOUT,
        )
        self._model = settings.llm_model
        self._ready = True

    def reload(self):
        """外部调用：配置变更后重新加载。"""
        self._reload()

    def _ensure_ready(self):
        """真正调用大模型前断言已就绪，否则抛出清晰错误（由 WS 通道透传）。"""
        if not self._ready or self._client is None:
            raise RuntimeError(
                "LLM API Key 尚未配置，无法运行任务。请点击右上角 ⚙ 设置填写 API Key 并保存。"
            )

    def _extract_content(self, response) -> str:
        """从 LLM 响应中提取文本内容（统一空 choices 检查）。"""
        if not response.choices:
            raise RuntimeError("LLM 返回空的 choices，请检查模型配置或 API 状态。")
        return response.choices[0].message.content or ""

    async def decide_action(
        self,
        task: str,
        conversation_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """让 LLM 根据任务和对话历史，决定下一步操作。"""
        self._ensure_ready()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}"},
        ]
        messages.extend(conversation_history)

        response = await self._chat_with_retry(messages, tools=BROWSER_TOOLS_SCHEMA)

        if not response.choices:
            raise RuntimeError("LLM 返回空的 choices，请检查模型配置或 API 状态。")
        message = response.choices[0].message

        # LLM 决定调用工具
        if message.tool_calls:
            call = message.tool_calls[0]
            tool_name = call.function.name
            arguments = json.loads(call.function.arguments)

            # finish 工具 = 任务完成
            if tool_name == "finish":
                return {
                    "done": True,
                    "answer": arguments.get("summary", ""),
                    "thought": message.content or "",
                }

            return {
                "tool": tool_name,
                "arguments": arguments,
                "thought": message.content or "",
            }

        # 没有工具调用，LLM 直接回答
        return {
            "done": True,
            "answer": message.content or "",
            "thought": message.content or "",
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> str:
        """通用 chat completion 调用（供 Planner / Reflection / Analyst / extract_info 共享）。"""
        self._ensure_ready()
        response = await self._chat_with_retry(messages, response_format=response_format)
        return self._extract_content(response)

    # LLM 网络调用重试：OpenAI SDK 的 APITimeoutError / APIConnectionError
    # 不继承内置 TimeoutError/OSError，必须显式列出
    _RETRYABLE = (TimeoutError, ConnectionError, OSError, APITimeoutError, APIConnectionError)

    @retry_async(max_attempts=3, base_delay=1.0, max_delay=8.0, retryable_exceptions=_RETRYABLE)
    async def _chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, str] | None = None,
    ) -> Any:
        """带指数退避重试的 chat.completions.create。

        只重试网络类瞬态错误（TimeoutError / ConnectionError / OSError）。
        API Key 错误（AuthenticationError）等业务错误直接抛出，不重试。
        """
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format
        return await self._client.chat.completions.create(**kwargs)

    async def extract_info(
        self, task: str, raw_text: str, fields: list[str] | None = None
    ) -> dict[str, Any]:
        """从网页文本中提取结构化信息（复用 chat() 方法）。"""
        self._ensure_ready()
        fields_hint = f"重点提取以下字段：{', '.join(fields)}" if fields else "提取与任务相关的关键信息"
        extract_prompt = f"""你是一个信息提取器。从网页文本中提取与任务相关的结构化信息。

任务：{task}
{fields_hint}

网页文本：
{raw_text[:8000]}

返回 JSON 对象，包含提取到的信息。如果没有找到相关信息，对应字段留空。"""

        content = await self.chat(
            messages=[
                {"role": "system", "content": "你是一个信息提取器，只返回JSON。"},
                {"role": "user", "content": extract_prompt},
            ],
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"raw_text": content}
