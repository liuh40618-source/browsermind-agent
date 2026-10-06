"""settings_store 配置校验单元测试。"""

import pytest

from settings_store import (
    ConfigValidationError,
    validate_settings,
    ALLOWED_KEYS,
)


class TestValidateSettings:
    def test_valid_config_no_errors(self):
        errors = validate_settings({
            "llm_provider": "openai",
            "llm_model": "gpt-4o",
            "llm_base_url": "https://api.openai.com/v1",
            "llm_api_key": "sk-abc123",
        })
        assert errors == []

    def test_invalid_provider(self):
        errors = validate_settings({"llm_provider": "not-a-provider"})
        assert any("供应商" in e for e in errors)

    def test_empty_model(self):
        errors = validate_settings({"llm_model": "  "})
        assert any("模型" in e for e in errors)

    def test_bad_base_url(self):
        errors = validate_settings({"llm_base_url": "api.openai.com/v1"})
        assert any("http(s)://" in e for e in errors)

    def test_api_key_with_spaces(self):
        errors = validate_settings({"llm_api_key": "sk- abc"})
        assert any("空格" in e for e in errors)

    def test_unknown_key_filtered_not_validated(self):
        """白名单外的键不应引起校验错误（由 update 过滤）。"""
        errors = validate_settings({"evil_key": "x"})
        assert errors == []

    def test_whitelist_contains_expected(self):
        assert ALLOWED_KEYS == {
            "llm_provider", "llm_model", "llm_api_key", "llm_base_url", "tavily_api_key",
            "provider_api_keys",
        }


class TestUpdateValidation:
    def test_update_rejects_invalid(self, tmp_path):
        from settings_store import SettingsStore
        store = SettingsStore(path=tmp_path / "cfg.json")
        with pytest.raises(ConfigValidationError):
            store.update({"llm_provider": "bad"})

    def test_update_filters_unknown_keys(self, tmp_path):
        from settings_store import SettingsStore
        store = SettingsStore(path=tmp_path / "cfg.json")
        result = store.update({"llm_model": "gpt-4o", "evil": "x"})
        assert "evil" not in result
        assert result["llm_model"] == "gpt-4o"
