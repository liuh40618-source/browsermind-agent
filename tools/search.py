"""
Search Tool - 搜索工具（升级版）

支持两种后端：
1. DuckDuckGo HTML API（免费）— 自动检测 bot 拦截，降级到浏览器搜索
2. Tavily（需 API key，质量更高）— 可选

搜索策略：
1. 有 Tavily Key → 用 Tavily（最稳定）
2. 无 Tavily Key → 尝试 DDG HTML API
3. DDG 被拦截（返回验证码）→ 降级到 Playwright 浏览器搜索
"""
from typing import Any
import logging
import httpx
import re
from urllib.parse import quote

logger = logging.getLogger(__name__)


class SearchTool:
    """搜索工具，支持 DDG / Tavily / 浏览器搜索三种后端。"""

    def __init__(self):
        self._tavily_api_key = ""
        try:
            from config import settings
            self._tavily_api_key = getattr(settings, "tavily_api_key", "") or ""
        except Exception:
            pass

    async def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """执行搜索，自动选择最佳后端。

        优先级：Tavily > DuckDuckGo HTML > 浏览器搜索
        """
        try:
            if self._tavily_api_key:
                results = await self._search_tavily(query, max_results)
                backend = "tavily"
            else:
                results = await self._search_duckduckgo(query, max_results)
                backend = "duckduckgo"

            # 按相关性排序
            results = self._rank_results(results, query)

            return {
                "tool": "search",
                "status": "success",
                "message": f"Found {len(results)} results for '{query}' (via {backend})",
                "data": {"query": query, "results": results, "backend": backend},
            }
        except Exception as e:
            return {
                "tool": "search",
                "status": "failed",
                "message": f"Search failed: {e}",
                "data": {"query": query, "results": []},
            }

    async def _search_duckduckgo(
        self, query: str, max_results: int
    ) -> list[dict[str, str]]:
        """通过 DuckDuckGo 搜索，DDG 被拦截时自动降级到浏览器搜索。"""
        # 尝试 DDG HTML API
        results = await self._try_ddg_html(query, max_results)

        # 如果 DDG 返回空结果（可能被 bot 拦截），降级到浏览器搜索
        if not results:
            logger.info("[Search] DDG returned no results for '%s', falling back to browser search...", query)
            browser_results = await self._search_via_browser(query, max_results)
            if browser_results:
                logger.info("[Search] Browser search returned %d results", len(browser_results))
                return browser_results

        return results

    async def _try_ddg_html(
        self, query: str, max_results: int
    ) -> list[dict[str, str]]:
        """尝试 DDG HTML API 搜索，检测 bot 拦截。"""
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        data = {"q": query}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.post(url, data=data, headers=headers)

        html = resp.text

        # 检测 bot 挑战页面（DDG 返回 202 + 验证码）
        if resp.status_code == 202 or "botnet" in html or "challenge-form" in html or "anomaly-modal" in html:
            logger.info("[Search] DDG returned challenge page (status=%d)", resp.status_code)
            return []  # 返回空列表，触发降级

        # 正常解析结果
        results = []
        result_blocks = re.findall(
            r'<div[^>]*class="result[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="result|"|<div[^>]*class="nav-link")',
            html, re.DOTALL
        )

        if not result_blocks:
            # 备用：提取所有结果链接
            result_blocks = re.findall(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
                html
            )
            for url, title in result_blocks:
                title = self._clean_text(title)
                if not title:
                    continue
                results.append({
                    "title": title,
                    "url": self._decode_ddg_url(url),
                    "snippet": "",
                    "score": 0.5,
                })
                if len(results) >= max_results:
                    break
            return results

        for block in result_blocks:
            title_match = re.search(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
                block
            )
            if not title_match:
                continue

            url = self._decode_ddg_url(title_match.group(1))
            title = self._clean_text(title_match.group(2))
            if not title:
                continue

            snippet = ""
            snippet_match = re.search(
                r'<a[^>]+class="result__snippet"[^>]*>([^<]*(?:<[^>]+>[^<]*)*)</a>',
                block, re.DOTALL
            )
            if snippet_match:
                snippet = self._clean_text(snippet_match.group(1))

            if not snippet:
                text_content = re.sub(r'<[^>]+>', ' ', block)
                text_content = self._clean_text(text_content)
                if title in text_content:
                    snippet = text_content.replace(title, '', 1).strip()
                else:
                    snippet = text_content[:200]

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet[:300],
                "score": 0.5,
            })
            if len(results) >= max_results:
                break

        return results

    async def _search_via_browser(
        self, query: str, max_results: int
    ) -> list[dict[str, str]]:
        """使用 Playwright 浏览器搜索（通过 Bing，bot 检测较宽松）。

        DuckDuckGo 和 Google 均对 headless 浏览器有严格检测，
        Bing 目前对自动化请求比较友好，能稳定返回搜索结果。
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("[Search] playwright not installed, cannot use browser search")
            return []

        search_url = f"https://www.bing.com/search?q={quote(query)}"
        results = []

        try:
            pw = await async_playwright().start()
            try:
                browser = await pw.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    )
                    try:
                        page = await context.new_page()

                        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

                        # 等待搜索结果加载
                        try:
                            await page.wait_for_selector(
                                'li.b_algo, .b_algo',
                                timeout=10000
                            )
                        except Exception:
                            pass

                        await page.wait_for_timeout(2000)

                        # 提取 Bing 搜索结果
                        extracted = await page.evaluate(
                            f"""
                            () => {{
                                const items = document.querySelectorAll('li.b_algo');
                                const results = [];
                                items.forEach(item => {{
                                    const link = item.querySelector('h2 a');
                                    const title = link?.textContent?.trim();
                                    const href = link?.getAttribute('href') || '';
                                    const snippet = item.querySelector('.b_caption p, .b_lineclamp2');
                                    if (title && href) {{
                                        results.push({{
                                            title: title,
                                            url: href,
                                            snippet: snippet?.textContent?.trim()?.slice(0, 300) || '',
                                        }});
                                    }}
                                }});
                                return results.slice(0, {max_results});
                            }}
                            """
                        )

                        results = [
                            {
                                "title": r.get("title", ""),
                                "url": self._decode_bing_url(r.get("url", "")),
                                "snippet": r.get("snippet", ""),
                                "score": 0.5,
                            }
                            for r in extracted if r.get("title") and r.get("url")
                        ]
                    finally:
                        await context.close()
                finally:
                    await browser.close()
            finally:
                await pw.stop()

        except Exception as e:
            logger.error("[Search] Browser search failed: %s", e)

        return results

    async def _search_tavily(
        self, query: str, max_results: int
    ) -> list[dict[str, str]]:
        """通过 Tavily API 搜索（高质量，需 API key）。"""
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self._tavily_api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "search_depth": "advanced",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "score": item.get("score", 0.5),
            })

        return results

    def _rank_results(
        self, results: list[dict[str, str]], query: str
    ) -> list[dict[str, str]]:
        """按相关性排序搜索结果。"""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for r in results:
            score = r.get("score", 0.5)
            title = r.get("title", "").lower()
            snippet = r.get("snippet", "").lower()
            url = r.get("url", "").lower()

            if query_lower in title:
                score += 0.3
            else:
                title_words = set(title.split())
                overlap = len(query_words & title_words)
                if overlap > 0:
                    score += 0.1 * (overlap / len(query_words))

            if query_lower in snippet:
                score += 0.2
            elif snippet:
                snippet_words = set(snippet.split())
                overlap = len(query_words & snippet_words)
                if overlap > 0:
                    score += 0.1 * (overlap / len(query_words))

            authoritative_domains = [
                "github.com", "stackoverflow.com", "docs.", "wikipedia.org",
                "medium.com", "dev.to", "reddit.com"
            ]
            if any(d in url for d in authoritative_domains):
                score += 0.1

            if 50 <= len(snippet) <= 500:
                score += 0.1

            r["score"] = min(score, 1.0)

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results

    def _clean_text(self, text: str) -> str:
        """清理文本：去掉 HTML 实体、多余空白。"""
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'&#x27;', "'", text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _decode_ddg_url(self, url: str) -> str:
        """解码 DDG 重定向 URL。"""
        match = re.search(r'uddg=([^&]+)', url)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1))
        return url

    def _decode_bing_url(self, url: str) -> str:
        """解码 Bing 重定向 URL，提取真实 URL。

        Bing 的搜索结果链接格式为：
        https://www.bing.com/ck/a?!&&p=...&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbQ==&...

        其中 u 参数是 base64 编码的真实 URL（带 a1a 前缀）。
        """
        if "bing.com/ck/" not in url:
            return url

        import base64
        match = re.search(r'[?&]u=([^&]+)', url)
        if match:
            try:
                encoded = match.group(1)
                # Bing 的 u 参数是 base64 编码，带 a1a 前缀
                if encoded.startswith("a1a"):
                    encoded = encoded[3:]
                decoded = base64.b64decode(encoded).decode("utf-8")
                return decoded
            except Exception:
                pass
        return url

    async def execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """统一调度入口。"""
        if tool == "search":
            return await self.search(**arguments)
        return {
            "tool": tool,
            "status": "failed",
            "message": f"Unknown search tool: {tool}",
            "data": {},
        }