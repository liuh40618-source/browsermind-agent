"""browser.open_page SPA 渲染等待逻辑测试（Fake Page，不启动真浏览器）。

验证 _goto_with_render_wait 的调用顺序与降级行为：
- L1: networkidle 优先
- 降级: networkidle 超时 → domcontentloaded
- L2: 显式等 #root > * 渲染信号
- 固定等待收尾
"""

import asyncio

import pytest

from tools.browser import BrowserSession
from config import settings


class FakePage:
    """模拟 Playwright Page，记录 goto / wait_for_selector / wait_for_timeout 调用。"""

    def __init__(self, networkidle_fails=False):
        self.calls = []
        self.networkidle_fails = networkidle_fails

    async def goto(self, url, wait_until="domcontentloaded"):
        self.calls.append(("goto", url, wait_until))
        if wait_until == "networkidle" and self.networkidle_fails:
            raise TimeoutError("networkidle timed out")

    async def wait_for_selector(self, selector, timeout=None):
        self.calls.append(("wait_for_selector", selector, timeout))

    async def wait_for_timeout(self, ms):
        self.calls.append(("wait_for_timeout", ms))


@pytest.fixture(autouse=True)
def restore_settings():
    """每个测试后恢复 settings，避免互相污染。"""
    yield
    settings.browser_render_selector = "#root > *"
    settings.browser_render_wait_ms = 1500


class TestGotoWithRenderWait:
    def test_uses_networkidle_first(self):
        """正常路径：先 networkidle，再等渲染信号，最后固定等待。"""
        page = FakePage()
        session = BrowserSession(browser=None)

        asyncio.run(session._goto_with_render_wait(page, "https://example.com"))

        gotos = [c for c in page.calls if c[0] == "goto"]
        assert gotos == [("goto", "https://example.com", "networkidle")]

        selectors = [c for c in page.calls if c[0] == "wait_for_selector"]
        assert selectors[0][1] == "#root > *"

        waits = [c for c in page.calls if c[0] == "wait_for_timeout"]
        assert waits[0][1] == 1500

    def test_falls_back_to_domcontentloaded(self):
        """networkidle 超时（长轮询页面）→ 降级 domcontentloaded。"""
        page = FakePage(networkidle_fails=True)
        session = BrowserSession(browser=None)

        asyncio.run(session._goto_with_render_wait(page, "https://spa.example.com"))

        gotos = [c for c in page.calls if c[0] == "goto"]
        assert gotos == [
            ("goto", "https://spa.example.com", "networkidle"),
            ("goto", "https://spa.example.com", "domcontentloaded"),
        ]

    def test_empty_selector_skips_wait(self, monkeypatch):
        """browser_render_selector 为空 → 跳过显式选择器等待。"""
        monkeypatch.setattr(settings, "browser_render_selector", "")
        page = FakePage()
        session = BrowserSession(browser=None)

        asyncio.run(session._goto_with_render_wait(page, "https://example.com"))

        selectors = [c for c in page.calls if c[0] == "wait_for_selector"]
        assert selectors == []

    def test_selector_timeout_does_not_fail(self, monkeypatch):
        """选择器等待超时（非 SPA 页面）→ 忽略，不抛异常。"""
        original = FakePage.wait_for_selector

        async def raising_selector(self, selector, timeout=None):
            self.calls.append(("wait_for_selector", selector, timeout))
            raise TimeoutError("selector not found")

        FakePage.wait_for_selector = raising_selector
        try:
            page = FakePage()
            session = BrowserSession(browser=None)
            # 不应抛异常
            asyncio.run(session._goto_with_render_wait(page, "https://example.com"))
        finally:
            FakePage.wait_for_selector = original

    def test_open_page_success_contract(self, monkeypatch):
        """open_page 对外契约：成功时返回 tool/status/message/data。"""

        async def fake_goto(self, url, wait_until="domcontentloaded"):
            self.calls.append(("goto", url, wait_until))

        async def fake_title(self):
            return "测试页"

        FakePage.goto = fake_goto
        FakePage.title = fake_title
        try:
            session = BrowserSession(browser=None)
            session._page = FakePage()  # 绕过 _ensure_page 的 None 检查
            result = asyncio.run(session.open_page("https://example.com"))
            assert result["status"] == "success"
            assert result["data"]["title"] == "测试页"
            assert result["tool"] == "open_page"
        finally:
            del FakePage.goto
            del FakePage.title
