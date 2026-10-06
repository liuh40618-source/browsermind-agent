"""settings_store 按供应商存储 API Key 的单元测试。"""

import pytest

from settings_store import SettingsStore


@pytest.fixture()
def store(tmp_path):
    return SettingsStore(path=tmp_path / "cfg.json")


class TestProviderKeys:
    def test_set_and_get_key_for_provider(self, store):
        """set_key_for_provider 后 get_key_for_provider 能取回。"""
        store.set_key_for_provider("deepseek", "sk-ds-123")
        store.set_key_for_provider("qwen", "sk-qw-456")
        assert store.get_key_for_provider("deepseek") == "sk-ds-123"
        assert store.get_key_for_provider("qwen") == "sk-qw-456"

    def test_providers_with_keys(self, store):
        """providers_with_keys 只返回已配置的供应商。"""
        store.set_key_for_provider("deepseek", "sk-ds-123")
        assert store.providers_with_keys() == {"deepseek"}

    def test_clear_key_removes_provider(self, store):
        """置空 Key 应移除该供应商的配置。"""
        store.set_key_for_provider("deepseek", "sk-ds-123")
        store.set_key_for_provider("deepseek", "")
        assert store.providers_with_keys() == set()
        assert store.get_key_for_provider("deepseek") == ""

    def test_unknown_provider_ignored(self, store):
        """未知供应商不写入。"""
        store.set_key_for_provider("not-a-provider", "sk-x")
        assert store.providers_with_keys() == set()

    def test_legacy_api_key_migrates_to_current_provider(self, store):
        """旧格式：llm_api_key + llm_provider 应迁移到 provider_api_keys。"""
        store.update({"llm_provider": "qwen", "llm_model": "qwen-plus", "llm_api_key": "sk-legacy"})
        assert store.get_key_for_provider("qwen") == "sk-legacy"
        assert "qwen" in store.providers_with_keys()

    def test_update_with_api_key_archives_to_provider(self, store):
        """update 提交 llm_api_key 时按当前 provider 归档。"""
        store.update({"llm_provider": "deepseek", "llm_model": "deepseek-chat"})
        store.update({"llm_api_key": "sk-archived"})
        assert store.get_key_for_provider("deepseek") == "sk-archived"

    def test_provider_keys_not_exposed_in_get_all(self, store):
        """get_all（前端展示用）不应含 provider_api_keys 明文。"""
        store.set_key_for_provider("deepseek", "sk-ds-123")
        exposed = store.get_all()
        assert "provider_api_keys" not in exposed
        assert "llm_api_key" not in exposed

    def test_get_key_falls_back_to_llm_api_key(self, store):
        """未按供应商配置时回退 llm_api_key。"""
        store.update({"llm_api_key": "sk-fallback"})
        assert store.get_key_for_provider("openai") == "sk-fallback"
