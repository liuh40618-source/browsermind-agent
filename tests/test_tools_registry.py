"""工具注册表单元测试：验证 @tool 装饰器与注册表契约。"""

import pytest

from tools import TOOL_REGISTRY, init_registry, get_browser_tools, get_search_tools, get_all_tools


class TestToolRegistry:
    def test_registry_populated(self):
        """init_registry 后注册表非空。"""
        n = init_registry()
        assert n >= 8  # 7 浏览器 + 1 搜索（+open 别名 = 8 条）

    def test_browser_tools_known_names(self):
        """核心浏览器工具应注册到 browser 后端。"""
        init_registry()
        browser_tools = get_browser_tools()
        for name in ("open_page", "click", "type", "scroll", "screenshot", "get_text"):
            assert name in browser_tools

    def test_open_is_alias_of_open_page(self):
        """open 别名应指向 open_page 方法。"""
        init_registry()
        spec = TOOL_REGISTRY["open"]
        assert spec.backend == "browser"
        assert spec.method == "open_page"

    def test_search_tool_registered(self):
        """search 应注册到 search 后端。"""
        init_registry()
        assert "search" in get_search_tools()
        assert TOOL_REGISTRY["search"].backend == "search"

    def test_all_tools_includes_finish_excluded(self):
        """get_all_tools 不应包含 finish（finish 由 LLM 层处理）。"""
        init_registry()
        assert "finish" not in get_all_tools()

    def test_spec_has_expected_fields(self):
        """ToolSpec 应包含 name/backend/method。"""
        init_registry()
        spec = TOOL_REGISTRY["click"]
        assert spec.name == "click"
        assert spec.method == "click"
        assert spec.backend == "browser"
