"""
Browser Tool - 浏览器控制封装层

设计原则：
- LLM 不直接调用 Playwright，中间隔一层封装
- LLM 输出 {"tool": "click", "arguments": {"text": "Pricing"}}
- 系统执行 Playwright 操作，返回统一契约

6 个能力：open / click / type / scroll / screenshot / get_text
"""

from typing import Any
from playwright.async_api import async_playwright, Browser, Page
from config import settings


class BrowserTool:
    """浏览器工具封装，对 Agent 暴露语义化接口。"""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    # ── 生命周期 ──────────────────────────────────────────

    async def start(self) -> None:
        """启动 Playwright 和浏览器。"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.browser_headless
        )
        self._page = await self._browser.new_page()
        self._page.set_default_timeout(settings.browser_timeout)

    async def close(self) -> None:
        """关闭浏览器，释放资源。"""
        try:
            if self._page:
                await self._page.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._browser = None
        self._playwright = None

    def _ensure_page(self) -> Page:
        """确保页面已初始化。"""
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    # ── 6 个核心能力 ──────────────────────────────────────

    async def open_page(self, url: str) -> dict[str, Any]:
        """打开网页。"""
        page = self._ensure_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            return {
                "tool": "open_page",
                "status": "success",
                "message": f"Opened {url}",
                "data": {"url": url, "title": await page.title()},
            }
        except Exception as e:
            return {
                "tool": "open_page",
                "status": "failed",
                "message": f"Failed to open {url}: {e}",
                "data": {"url": url},
            }

    async def click(self, text: str) -> dict[str, Any]:
        """按文字点击元素（不直接用 CSS 选择器）。

        定位优先级：精确文字 → 模糊匹配 → aria-label → 按钮内文字
        找到多个时返回候选，不猜测。
        """
        page = self._ensure_page()
        try:
            # 策略1：精确文字匹配
            locator = page.get_by_text(text, exact=True)
            count = await locator.count()
            if count == 0:
                # 策略2：模糊匹配
                locator = page.get_by_text(text, exact=False)
                count = await locator.count()
            if count == 0:
                # 策略3：aria-label
                locator = page.get_by_label(text, exact=False)
                count = await locator.count()
            if count == 0:
                # 策略4：按钮/链接内文字（转义单引号防止注入）
                safe_text = text.replace("'", "\\'")
                locator = page.locator(
                    f"button:has-text('{safe_text}'), a:has-text('{safe_text}')"
                )
                count = await locator.count()

            if count == 0:
                return {
                    "tool": "click",
                    "status": "failed",
                    "message": f"Element with text '{text}' not found",
                    "data": {"text": text},
                }
            if count > 1:
                # 找到多个，返回候选让 LLM 决定
                texts = []
                for i in range(min(count, 5)):
                    t = await locator.nth(i).inner_text()
                    texts.append(t.strip()[:80])
                return {
                    "tool": "click",
                    "status": "ambiguous",
                    "message": f"Found {count} elements matching '{text}', please specify",
                    "data": {"text": text, "candidates": texts},
                }

            await locator.first.click()
            return {
                "tool": "click",
                "status": "success",
                "message": f"Clicked '{text}'",
                "data": {"text": text},
            }
        except Exception as e:
            return {
                "tool": "click",
                "status": "failed",
                "message": f"Click failed: {e}",
                "data": {"text": text},
            }

    async def type_text(self, selector: str, value: str) -> dict[str, Any]:
        """在输入框中输入文本。

        selector 支持语义定位：placeholder 文字、aria-label 或 CSS。
        """
        page = self._ensure_page()
        try:
            # 策略1：placeholder
            locator = page.get_by_placeholder(selector, exact=False)
            count = await locator.count()
            if count == 0:
                # 策略2：aria-label
                locator = page.get_by_label(selector, exact=False)
                count = await locator.count()
            if count == 0:
                # 策略3：直接当 CSS 选择器
                locator = page.locator(selector)
                count = await locator.count()

            if count == 0:
                return {
                    "tool": "type",
                    "status": "failed",
                    "message": f"Input field '{selector}' not found",
                    "data": {"selector": selector, "value": value},
                }

            await locator.first.click()
            await locator.first.fill(value)
            return {
                "tool": "type",
                "status": "success",
                "message": f"Typed '{value}' into '{selector}'",
                "data": {"selector": selector, "value": value},
            }
        except Exception as e:
            return {
                "tool": "type",
                "status": "failed",
                "message": f"Type failed: {e}",
                "data": {"selector": selector, "value": value},
            }

    async def scroll(self, direction: str = "down", times: int = 3) -> dict[str, Any]:
        """滚动页面，加载懒加载内容。

        direction: "down" | "up"
        times: 滚动次数
        """
        page = self._ensure_page()
        try:
            delta = 800 if direction == "down" else -800
            for _ in range(times):
                await page.mouse.wheel(0, delta)
                await page.wait_for_timeout(500)
            return {
                "tool": "scroll",
                "status": "success",
                "message": f"Scrolled {direction} {times} times",
                "data": {"direction": direction, "times": times},
            }
        except Exception as e:
            return {
                "tool": "scroll",
                "status": "failed",
                "message": f"Scroll failed: {e}",
                "data": {"direction": direction, "times": times},
            }

    async def screenshot(self) -> dict[str, Any]:
        """截图，返回 base64 编码的图片。"""
        page = self._ensure_page()
        try:
            screenshot_bytes = await page.screenshot(full_page=False)
            import base64
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return {
                "tool": "screenshot",
                "status": "success",
                "message": "Screenshot captured",
                "data": {"screenshot": screenshot_b64},
            }
        except Exception as e:
            return {
                "tool": "screenshot",
                "status": "failed",
                "message": f"Screenshot failed: {e}",
                "data": {},
            }

    async def get_text(self) -> dict[str, Any]:
        """获取页面文本内容（阶段3起：返回 Parser 解析后的结构化内容）。"""
        page = self._ensure_page()
        try:
            title = await page.title()
            html = await page.content()
            url = page.url

            # 用 Parser 解析，返回结构化内容（一次解析，两处复用）
            from tools.parser import Parser
            parser = Parser()
            parsed = parser.parse(html, url)

            # 给 LLM 的精简文本（复用已解析结果，避免二次解析）
            clean_text = parser.parse_for_llm(html, url, parsed=parsed)
            max_chars = 30000
            truncated = len(clean_text) > max_chars
            clean_text = clean_text[:max_chars]

            return {
                "tool": "get_text",
                "status": "success",
                "message": f"Retrieved page text ({len(clean_text)} chars, cleaned from {parsed['stats']['original_chars']} chars)",
                "data": {
                    "title": parsed["title"] or title,
                    "text": clean_text,
                    "truncated": truncated,
                    "url": url,
                    "sections": parsed["sections"],
                    "stats": parsed["stats"],
                },
            }
        except Exception as e:
            return {
                "tool": "get_text",
                "status": "failed",
                "message": f"Get text failed: {e}",
                "data": {},
            }

    # ── 统一调度入口 ─────────────────────────────────────

    async def execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """统一调度：根据 LLM 输出的 tool 名称，调用对应方法。

        LLM 输出示例：
            {"tool": "click", "arguments": {"text": "Pricing"}}

        系统执行后返回统一契约。
        """
        dispatch = {
            "open_page": lambda: self.open_page(**arguments),
            "open": lambda: self.open_page(**arguments),
            "click": lambda: self.click(**arguments),
            "type": lambda: self.type_text(**arguments),
            "scroll": lambda: self.scroll(**arguments),
            "screenshot": lambda: self.screenshot(),
            "get_text": lambda: self.get_text(),
        }

        handler = dispatch.get(tool)
        if handler is None:
            return {
                "tool": tool,
                "status": "failed",
                "message": f"Unknown tool: '{tool}'. Available: {list(dispatch.keys())}",
                "data": {},
            }

        return await handler()
