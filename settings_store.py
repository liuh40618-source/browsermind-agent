"""
Settings Store - 运行时配置存储

用 JSON 文件保存用户通过前端界面修改的 AI 模型配置，
优先级高于 .env / 环境变量，低于代码直接修改。
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


CONFIG_PATH = Path(__file__).resolve().parent / "data" / "user_config.json"

# 预设供应商配置模板
# 只放真实存在的模型名，不编造倍率/标签等元数据
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

# 可配置字段白名单（防止写入任意键）
ALLOWED_KEYS = {
    "llm_provider", "llm_model", "llm_api_key", "llm_base_url", "tavily_api_key",
    "provider_api_keys",
}

# 敏感键：后端使用，前端不展示
_SENSITIVE_KEYS = {"llm_api_key", "tavily_api_key", "provider_api_keys"}




class ConfigValidationError(ValueError):
    """配置校验失败，message 为对用户友好的中文提示。"""


def validate_settings(data: dict[str, Any]) -> list[str]:
    """校验用户提交的配置，返回错误列表（空列表 = 全部合法）。

    校验规则：
    - llm_provider: 必须在 PRESETS 中
    - llm_model: 非空字符串
    - llm_base_url: 必须是 http(s):// 开头（若提供）
    - llm_api_key / tavily_api_key: 非空且不含空白
    """
    errors: list[str] = []

    provider = data.get("llm_provider")
    if provider is not None:
        if not isinstance(provider, str) or provider not in PRESETS:
            errors.append(f"供应商不受支持：{provider}（可选：{', '.join(PRESETS.keys())}）")

    model = data.get("llm_model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        errors.append("模型名称不能为空")

    base_url = data.get("llm_base_url")
    if base_url:
        try:
            parsed = urlsplit(base_url)
            valid = parsed.scheme in ("http", "https") and bool(parsed.hostname)
            valid = valid and not any(ch.isspace() for ch in base_url)
            valid = valid and not parsed.username and not parsed.password and not parsed.fragment
            _ = parsed.port
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            errors.append("Base URL 必须是有效的 http(s):// 地址")

    for key in ("llm_api_key", "tavily_api_key"):
        value = data.get(key)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{key} 不能为空")
            elif any(ch.isspace() for ch in value):
                errors.append(f"{key} 不应包含空格")

    return errors


def _validate_provider_keys(keys: Any) -> None:
    if not isinstance(keys, dict):
        raise ConfigValidationError("供应商密钥必须是对象")
    for provider, key in keys.items():
        errors = validate_settings({"llm_provider": provider})
        if key != "":
            errors.extend(validate_settings({"llm_api_key": key}))
        if key is None:
            errors.append("密钥必须是字符串")
        if errors:
            raise ConfigValidationError("；".join(errors))


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

    def _save(self, data: dict[str, Any]):
        """原子替换文件，写入成功后才更新内存。"""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as f:
                temp_path = Path(f.name)
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def get_all(self) -> dict[str, Any]:
        """返回完整配置（不含敏感密钥，前端展示用）。"""
        return {k: v for k, v in self._data.items() if k not in _SENSITIVE_KEYS}

    def get_all_with_key(self) -> dict[str, Any]:
        """返回完整配置（含 api_key，后端使用）。"""
        return dict(self._data)

    # ── 按供应商的 API Key 管理 ──────────────────────────

    def _provider_keys(self) -> dict[str, str]:
        """内部取 provider_api_keys 字典（自动迁移旧格式）。"""
        keys = self._data.get("provider_api_keys")
        keys = dict(keys) if isinstance(keys, dict) else {}
        # 迁移：旧的单一 llm_api_key 归入当前 provider 名下
        legacy = self._data.get("llm_api_key")
        provider = self._data.get("llm_provider")
        if legacy and provider and provider not in keys:
            keys[provider] = legacy
        return keys

    def get_key_for_provider(self, provider: str | None) -> str:
        """供应商之间不共享密钥；仅兼容未标注供应商的旧配置。"""
        if not provider:
            return self._data.get("llm_api_key", "")
        keys = self._provider_keys()
        if provider in keys:
            return keys[provider]
        if not self._data.get("llm_provider"):
            return self._data.get("llm_api_key", "")
        return ""

    def set_key_for_provider(self, provider: str, api_key: str) -> None:
        """为指定供应商保存 API Key（写 provider_api_keys，并同步 llm_api_key）。"""
        if not provider or provider not in PRESETS:
            return
        self.update({"provider_api_keys": {provider: api_key}})

    def providers_with_keys(self) -> set[str]:
        """已配置 API Key 的供应商集合。"""
        keys = self._provider_keys()
        return {p for p, k in keys.items() if k}

    def update(self, data: dict[str, Any]) -> dict[str, Any]:
        """更新配置并保存（自动过滤白名单外的键，非法值抛 ConfigValidationError）。"""
        # 只保留白名单字段
        filtered = {k: v for k, v in data.items() if k in ALLOWED_KEYS}
        errors = validate_settings(filtered)
        if errors:
            raise ConfigValidationError("；".join(errors))
        provider_keys = filtered.pop("provider_api_keys", {})
        _validate_provider_keys(provider_keys)
        keys = self._provider_keys()
        updated = {**self._data, **filtered}
        provider = updated.get("llm_provider")
        if "llm_api_key" in filtered and provider in PRESETS:
            keys[provider] = filtered["llm_api_key"]
        for name, key in provider_keys.items():
            if key:
                keys[name] = key
            else:
                keys.pop(name, None)
        updated["provider_api_keys"] = keys
        if provider:
            updated["llm_api_key"] = keys.get(provider, "")
        self._save(updated)
        return self.get_all()

    def reset(self) -> dict[str, Any]:
        """清空用户配置，回退到 .env / 默认值。"""
        self._data = {}
        if self.path.exists():
            self.path.unlink()
        return {}


# 全局单例
settings_store = SettingsStore()
