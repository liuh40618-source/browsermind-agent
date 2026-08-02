"""
BrowserMind configuration.
LLM provider settings - adjust based on your choice.

优先级：代码默认值 < .env / 环境变量 < user_config.json（前端设置）
"""

import logging

from pydantic_settings import BaseSettings

__version__ = "0.6.0"

logger = logging.getLogger(__name__)


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

    # --- Server Configuration ---
    host: str = "127.0.0.1"
    port: int = 8000

    # CORS allowed origins (comma-separated, e.g. "http://localhost:3000,https://example.com")
    # Set to "*" to allow all origins (not recommended for production)
    cors_origins: str = "*"

    model_config = {"env_file": ".env", "env_prefix": ""}


def _load_user_config():
    """加载 user_config.json 并用其值覆盖 settings。"""
    try:
        from settings_store import settings_store

        user = settings_store.get_all_with_key()
        for key, value in user.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
    except Exception:
        logger.debug("Failed to load user config, using defaults", exc_info=True)


settings = Settings()
_load_user_config()
