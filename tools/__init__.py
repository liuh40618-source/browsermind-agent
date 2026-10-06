"""
BrowserMind Tools - 工具注册表

所有工具通过 @tool 装饰器注册到 TOOL_REGISTRY，agent_loop 按注册表统一分发。
新增工具只需在对应工具模块内注册，无需修改 agent_loop 主循环。

用法：
    from tools import tool
    @tool("my_tool", backend="browser")
    async def my_tool(self, ...):
        ...

backend 决定由哪个执行器（BrowserSession / SearchTool）调用。
"""

from typing import Any, Callable

import asyncio
import functools
import logging

logger = logging.getLogger(__name__)

# 后端类型常量
BACKEND_BROWSER = "browser"
BACKEND_SEARCH = "search"


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    ),
):
    """轻量级指数退避重试装饰器（用于 async 函数）。

    用法:
        @retry_async(max_attempts=3)
        async def fetch(): ...

    触发重试的默认异常：TimeoutError / ConnectionError / OSError
    （网络类瞬态错误）。业务错误（如 401 鉴权失败）不重试。
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                attempt += 1
                try:
                    return await fn(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt >= max_attempts:
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        "[retry] %s 第 %d/%d 次失败: %s，%.1fs 后重试",
                        fn.__name__, attempt, max_attempts, e, delay,
                    )
                    await asyncio.sleep(delay)

        return wrapper

    return decorator


class ToolSpec:
    """工具规格：名称 → 执行后端 + 绑定的方法名。"""

    __slots__ = ("name", "backend", "method")

    def __init__(self, name: str, backend: str, method: str):
        self.name = name
        self.backend = backend
        self.method = method

    def __repr__(self) -> str:
        return f"<ToolSpec {self.name} -> {self.backend}.{self.method}>"


# 注册表：工具名 -> ToolSpec
TOOL_REGISTRY: dict[str, ToolSpec] = {}


def tool(name: str, backend: str, method: str | None = None):
    """装饰器：把方法注册为可用工具。

    Args:
        name: 工具名（LLM 调用时使用的名字）
        backend: BACKEND_BROWSER 或 BACKEND_SEARCH，决定由哪个执行器调用
        method: 绑定的执行方法名；缺省用被装饰函数名

    用法（在 BrowserSession 内）:
        @tool("open_page", backend=BACKEND_BROWSER)
        async def open_page(self, url): ...

    别名（同一方法多个名字）:
        @tool("open", backend=BACKEND_BROWSER, method="open_page")
    """

    def decorator(fn: Callable) -> Callable:
        TOOL_REGISTRY[name] = ToolSpec(name, backend, method or fn.__name__)
        return fn

    return decorator


def register_tool(name: str, backend: str, method: str) -> None:
    """函数式注册（供不适用装饰器的方法使用）。"""
    TOOL_REGISTRY[name] = ToolSpec(name, backend, method)


# ── 向后兼容的集合（由注册表派生）─────────────────────────

def _tools_of_backend(backend: str) -> set[str]:
    return {n for n, spec in TOOL_REGISTRY.items() if spec.backend == backend}


def get_browser_tools() -> set[str]:
    """当前注册的浏览器类工具名集合。"""
    return _tools_of_backend(BACKEND_BROWSER)


def get_search_tools() -> set[str]:
    """当前注册的搜索类工具名集合。"""
    return _tools_of_backend(BACKEND_SEARCH)


def get_all_tools() -> set[str]:
    """所有已注册工具名（不含 finish）。"""
    return set(TOOL_REGISTRY.keys())


# 兼容旧引用：保持 BROWSER_TOOLS / SEARCH_TOOLS / ALL_TOOLS 为模块级常量
# （由于注册发生在 browser.py / search.py 被 import 时，这里提供惰性获取；
#   agent_loop 已改为调用 get_* 函数，旧常量仅作兼容保留。）
BROWSER_TOOLS: set[str] = set()
SEARCH_TOOLS: set[str] = set()
ALL_TOOLS: set[str] = set()


def _sync_compat_sets():
    """把注册表同步进兼容常量（在工具模块完成注册后调用）。"""
    global BROWSER_TOOLS, SEARCH_TOOLS, ALL_TOOLS
    BROWSER_TOOLS = get_browser_tools()
    SEARCH_TOOLS = get_search_tools()
    ALL_TOOLS = get_all_tools()


def init_registry() -> int:
    """导入工具模块并完成注册，返回工具总数。

    在应用启动时调用一次，确保所有 @tool 注册生效。
    """
    from tools import browser, search  # noqa: F401
    _sync_compat_sets()
    return len(TOOL_REGISTRY)
