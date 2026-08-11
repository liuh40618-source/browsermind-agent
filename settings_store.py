"""
Settings Store - 运行时配置存储

用 JSON 文件保存用户通过前端界面修改的 AI 模型配置，
优先级高于 .env / 环境变量，低于代码直接修改。
"""

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parent / "data" / "user_config.json"

# 预设供应商配置模板
PRESETS = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "qwen": {
        "label": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-coder-plus"],
    },
    "zhipu": {
        "label": "智谱 AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4-9b"],
    },
}


class SettingsStore:
    """用户配置存储（JSON 文件）。"""

    def __init__(self, path: Path | None = None):
        self.path = path or CONFIG_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self):
        """从 JSON 文件加载配置。"""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        """保存配置到 JSON 文件。"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    _SENSITIVE_KEYS = {"llm_api_key", "tavily_api_key"}

    def get_all(self) -> dict[str, Any]:
        """返回完整配置（不含敏感密钥，前端展示用）。"""
        return {k: v for k, v in self._data.items() if k not in self._SENSITIVE_KEYS}

    def get_all_with_key(self) -> dict[str, Any]:
        """返回完整配置（含 api_key，后端使用）。"""
        return dict(self._data)

    def update(self, data: dict[str, Any]) -> dict[str, Any]:
        """更新配置并保存。"""
        self._data.update(data)
        self._save()
        return self.get_all()

    def reset(self) -> dict[str, Any]:
        """清空用户配置，回退到 .env / 默认值。"""
        self._data = {}
        if self.path.exists():
            self.path.unlink()
        return {}


# 全局单例
settings_store = SettingsStore()
