"""
BrowserMind configuration.
LLM provider settings - adjust based on your choice.

优先级：代码默认值 < .env / 环境变量 < user_config.json（前端设置）
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- LLM Configuration ---
    # Provider: "openai" | "deepseek" | "qwen" | "zhipu"
    llm_provider: str = "openai"

    # API Key (set via environment variable LLM_API_KEY)
    llm_api_key: str = ""

    # Model name
    llm_model: str = "gpt-4o"

    # Base URL (for non-OpenAI providers, set the compatible endpoint)
    # DeepSeek: https://api.deepseek.com/v1
    # Qwen: https://dashscope.aliyuncs.com/compatible-mode/v1
    # Zhipu: https://open.bigmodel.cn/api/paas/v4
    llm_base_url: str = ""

    # --- Search Configuration ---
    # Tavily API Key (set via environment variable TAVILY_API_KEY)
    # If empty, falls back to DuckDuckGo (free, no key needed)
    tavily_api_key: str = ""

    # --- Browser Configuration ---
    browser_headless: bool = True
    browser_timeout: int = 30000  # milliseconds

    # --- SPA 渲染等待（解决 JS 动态渲染抓取空壳问题）---
    # 打开页面后额外等待渲染的时长（毫秒），给 SPA 的 setState 上屏留时间
    browser_render_wait_ms: int = 1500
    # 渲染完成信号：等待该选择器出现内容（React/Vue 根容器），空字符串则跳过
    browser_render_selector: str = "#root > *"

    # --- Server Configuration ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Security (optional) ---
    # 设置 AUTH_TOKEN 后，所有 API / WebSocket 请求需携带
    #   header: X-Auth-Token: <token>（REST）
    #   或首次 WS 消息中带 token 字段（WebSocket）
    # 留空 = 不启用鉴权（本地开发默认）
    auth_token: str = ""

    model_config = {"env_file": ".env", "env_prefix": ""}


def _load_user_config():
    """加载 user_config.json 并用其值覆盖 settings。"""
    try:
        from settings_store import settings_store

        user = settings_store.get_all_with_key()
        for key, value in user.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        settings.llm_api_key = resolve_api_key(settings.llm_provider)
    except Exception:
        pass


def resolve_api_key(provider: str) -> str:
    from settings_store import settings_store

    key = settings_store.get_key_for_provider(provider)
    if not key and provider == environment_settings.llm_provider:
        key = environment_settings.llm_api_key
    return key if key != "your-api-key-here" else ""


environment_settings = Settings()
settings = environment_settings.model_copy()
_load_user_config()
