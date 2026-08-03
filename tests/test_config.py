"""
Settings (config.py) 单元测试

测试配置类的默认值和实例化行为，
通过 mock 隔离环境变量和文件加载。
"""

# ── Settings 默认值 ──────────────────────────────────────


class TestSettingsDefaults:
    """Settings 默认值测试。"""

    def test_default_llm_provider(self):
        """llm_provider 默认值应为 'openai'。"""
        from config import Settings

        s = Settings()
        assert s.llm_provider == "openai"

    def test_default_llm_model(self):
        """llm_model 默认值应为 'gpt-4o'。"""
        from config import Settings

        s = Settings()
        assert s.llm_model == "gpt-4o"

    def test_default_llm_api_key_is_empty(self, monkeypatch):
        """llm_api_key 默认值应为空字符串（排除 .env 干扰）。"""
        from config import Settings

        # 隔离环境变量和 .env 文件的干扰
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        s = Settings(_env_file=None)
        assert s.llm_api_key == ""

    def test_default_llm_base_url_is_empty(self):
        """llm_base_url 默认值应为空字符串。"""
        from config import Settings

        s = Settings()
        assert s.llm_base_url == ""

    def test_default_tavily_api_key_is_empty(self):
        """tavily_api_key 默认值应为空字符串。"""
        from config import Settings

        s = Settings()
        assert s.tavily_api_key == ""

    def test_default_browser_headless(self):
        """browser_headless 默认值应为 True。"""
        from config import Settings

        s = Settings()
        assert s.browser_headless is True

    def test_default_browser_timeout(self):
        """browser_timeout 默认值应为 30000。"""
        from config import Settings

        s = Settings()
        assert s.browser_timeout == 30000

    def test_default_host(self):
        """host 默认值应为 '0.0.0.0'。"""
        from config import Settings

        s = Settings()
        assert s.host == "0.0.0.0"

    def test_default_port(self):
        """port 默认值应为 8000。"""
        from config import Settings

        s = Settings()
        assert s.port == 8000


# ── Settings 实例化 ──────────────────────────────────────


class TestSettingsInstantiation:
    """Settings 实例化相关测试。"""

    def test_settings_can_be_instantiated(self):
        """Settings 应能正常实例化。"""
        from config import Settings

        s = Settings()
        assert s is not None

    def test_settings_with_custom_values(self):
        """应能通过参数覆盖默认值。"""
        from config import Settings

        s = Settings(
            llm_provider="deepseek",
            llm_model="deepseek-chat",
            llm_api_key="sk-test",
            browser_headless=False,
            port=9000,
        )
        assert s.llm_provider == "deepseek"
        assert s.llm_model == "deepseek-chat"
        assert s.llm_api_key == "sk-test"
        assert s.browser_headless is False
        assert s.port == 9000

    def test_settings_is_pydantic_model(self):
        """Settings 应是 Pydantic BaseSettings 实例。"""
        from pydantic_settings import BaseSettings

        from config import Settings

        s = Settings()
        assert isinstance(s, BaseSettings)
