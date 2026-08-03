"""
SettingsStore 单元测试

使用 tmp_path 创建临时 JSON 配置文件，测试所有读写操作，
不依赖任何外部服务或真实配置。
"""

import json
from pathlib import Path

import pytest

from settings_store import SettingsStore

# ── Fixture ──────────────────────────────────────────────


@pytest.fixture
def settings(tmp_path: Path) -> SettingsStore:
    """创建一个使用临时配置文件的 SettingsStore 实例。"""
    config_path = tmp_path / "test_config.json"
    return SettingsStore(path=config_path)


@pytest.fixture
def settings_with_data(tmp_path: Path) -> SettingsStore:
    """创建一个已包含数据的 SettingsStore 实例。"""
    config_path = tmp_path / "test_config.json"
    data = {
        "llm_provider": "deepseek",
        "llm_model": "deepseek-chat",
        "llm_api_key": "sk-secret-123",
        "tavily_api_key": "tvly-secret-456",
        "browser_headless": False,
    }
    config_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return SettingsStore(path=config_path)


# ── get / 基本操作 ───────────────────────────────────────


class TestGet:
    """get 方法相关测试。"""

    def test_get_existing_key(self, settings_with_data: SettingsStore):
        """get 应返回已存在的 key 对应的值。"""
        assert settings_with_data.get("llm_provider") == "deepseek"
        assert settings_with_data.get("llm_model") == "deepseek-chat"

    def test_get_nonexistent_key_returns_none(self, settings: SettingsStore):
        """get 不存在的 key 应返回 None。"""
        assert settings.get("nonexistent") is None

    def test_get_nonexistent_key_returns_default(self, settings: SettingsStore):
        """get 不存在的 key 应返回指定的默认值。"""
        assert settings.get("nonexistent", "fallback") == "fallback"

    def test_get_empty_store(self, settings: SettingsStore):
        """空 store 的 get 应返回默认值。"""
        assert settings.get("anything") is None


# ── get_all（过滤敏感 key）───────────────────────────────


class TestGetAll:
    """get_all 方法相关测试。"""

    def test_get_all_excludes_sensitive_keys(self, settings_with_data: SettingsStore):
        """get_all 不应包含 llm_api_key 和 tavily_api_key。"""
        result = settings_with_data.get_all()
        assert "llm_api_key" not in result
        assert "tavily_api_key" not in result

    def test_get_all_includes_non_sensitive_keys(
        self,
        settings_with_data: SettingsStore,
    ):
        """get_all 应包含非敏感 key。"""
        result = settings_with_data.get_all()
        assert result["llm_provider"] == "deepseek"
        assert result["llm_model"] == "deepseek-chat"
        assert result["browser_headless"] is False

    def test_get_all_on_empty_store(self, settings: SettingsStore):
        """空 store 的 get_all 应返回空字典。"""
        assert settings.get_all() == {}


# ── get_all_with_key（包含所有 key）──────────────────────


class TestGetAllWithKey:
    """get_all_with_key 方法相关测试。"""

    def test_get_all_with_key_includes_sensitive_keys(
        self,
        settings_with_data: SettingsStore,
    ):
        """get_all_with_key 应包含敏感 key。"""
        result = settings_with_data.get_all_with_key()
        assert "llm_api_key" in result
        assert "tavily_api_key" in result
        assert result["llm_api_key"] == "sk-secret-123"
        assert result["tavily_api_key"] == "tvly-secret-456"

    def test_get_all_with_key_returns_copy(self, settings_with_data: SettingsStore):
        """get_all_with_key 应返回字典副本，修改不影响内部数据。"""
        result = settings_with_data.get_all_with_key()
        result["llm_provider"] = "modified"
        assert settings_with_data.get("llm_provider") == "deepseek"


# ── update ───────────────────────────────────────────────


class TestUpdate:
    """update 方法相关测试。"""

    def test_update_saves_data(self, settings: SettingsStore):
        """update 后 get 应返回新值。"""
        settings.update({"llm_provider": "qwen", "llm_model": "qwen-plus"})
        assert settings.get("llm_provider") == "qwen"
        assert settings.get("llm_model") == "qwen-plus"

    def test_update_persists_to_file(self, tmp_path: Path):
        """update 后数据应持久化到文件，重新加载后仍可读取。"""
        config_path = tmp_path / "test_config.json"
        store1 = SettingsStore(path=config_path)
        store1.update({"llm_provider": "zhipu"})

        # 重新创建实例，验证文件持久化
        store2 = SettingsStore(path=config_path)
        assert store2.get("llm_provider") == "zhipu"

    def test_update_returns_non_sensitive_data(self, settings: SettingsStore):
        """update 应返回不含敏感 key 的字典。"""
        settings.update(
            {
                "llm_provider": "openai",
                "llm_api_key": "sk-new-key",
            }
        )
        result = settings.update({"llm_model": "gpt-4o"})
        assert "llm_api_key" not in result
        assert "llm_model" in result

    def test_update_overwrites_existing(self, settings_with_data: SettingsStore):
        """update 应覆盖已有 key 的值。"""
        settings_with_data.update({"llm_provider": "openai"})
        assert settings_with_data.get("llm_provider") == "openai"


# ── reset ────────────────────────────────────────────────


class TestReset:
    """reset 方法相关测试。"""

    def test_reset_clears_all_data(self, settings_with_data: SettingsStore):
        """reset 后所有数据应被清空。"""
        result = settings_with_data.reset()
        assert result == {}
        assert settings_with_data.get("llm_provider") is None

    def test_reset_removes_file(self, settings_with_data: SettingsStore):
        """reset 后配置文件应被删除。"""
        config_path = settings_with_data.path
        assert config_path.exists()
        settings_with_data.reset()
        assert not config_path.exists()

    def test_reset_on_empty_store(self, settings: SettingsStore):
        """空 store 调用 reset 不应报错。"""
        result = settings.reset()
        assert result == {}


# ── 文件不存在时的行为 ───────────────────────────────────


class TestFileNotExists:
    """配置文件不存在时的行为测试。"""

    def test_init_with_nonexistent_file(self, tmp_path: Path):
        """指定不存在的文件路径时，SettingsStore 应正常初始化。"""
        config_path = tmp_path / "subdir" / "nonexistent.json"
        store = SettingsStore(path=config_path)
        assert store.get("anything") is None

    def test_init_creates_parent_directory(self, tmp_path: Path):
        """初始化时应自动创建父目录。"""
        config_path = tmp_path / "new_dir" / "config.json"
        SettingsStore(path=config_path)
        assert (tmp_path / "new_dir").is_dir()


# ── 损坏的 JSON 文件 ────────────────────────────────────


class TestCorruptedFile:
    """JSON 文件损坏时的容错测试。"""

    def test_corrupted_json_loads_empty(self, tmp_path: Path):
        """损坏的 JSON 文件应被容错处理，加载为空配置。"""
        config_path = tmp_path / "bad_config.json"
        config_path.write_text("{invalid json content!!!", encoding="utf-8")
        store = SettingsStore(path=config_path)
        assert store.get_all() == {}
