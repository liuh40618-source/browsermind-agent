"""
Parser - 网页理解工具

流水线：
    原始 HTML
      ↓
    ① 清洗（BeautifulSoup 去 script/nav/footer/广告）
      ↓
    ② 正文提取（Readability 算法）
      ↓
    ③ 转 Markdown（html2text）
      ↓
    ④ 结构化输出（标题 + 分段正文）
      ↓
    交给 LLM 理解

输出契约：
    {
        "url": "...",
        "title": "...",
        "sections": [{"heading": "...", "content": "..."}],
        "raw_markdown": "...",
        "stats": {"original_chars": N, "cleaned_chars": M}
    }
"""

import re
from typing import Any
from bs4 import BeautifulSoup
from readability import Document
import html2text


# html2text 配置（线程安全：每次调用创建新实例）
def _make_h2t():
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0  # 不换行
    h.protect_links = True
    return h


# 清洗时要移除的标签
_REMOVE_TAGS = ["script", "style", "noscript", "iframe", "svg", "canvas", "template"]

# 清洗时要移除的 class 关键词（只移除明确的广告/社交噪声，不碰 header/footer/nav）
_NOISE_CLASS_PATTERNS = [
    re.compile(r"\bad\b|advert|adsense|ad-banner|ad-container", re.I),
    re.compile(r"sidebar\b", re.I),
    re.compile(r"comment|disqus", re.I),
    re.compile(r"cookie-notice|popup-banner|modal-overlay", re.I),
    re.compile(r"social-share|share-buttons", re.I),
]


class Parser:
    """网页解析器：HTML → 清洗 → 正文 → Markdown → 结构化。"""

    def parse(self, html: str, url: str = "") -> dict[str, Any]:
        """解析 HTML，返回结构化内容。

        参数:
            html: 原始 HTML 字符串
            url: 页面 URL（用于记录来源）

        返回:
            结构化解析结果
        """
        original_chars = len(html)

        # ── Step 1: BeautifulSoup 清洗 ──
        soup = BeautifulSoup(html, "lxml")

        # 收集要删除的元素（避免边遍历边删除）
        to_remove: list[Any] = []

        # 噪声标签
        for tag_name in _REMOVE_TAGS:
            to_remove.extend(soup.find_all(tag_name))

        # 噪声 class 元素 + hidden 元素
        for element in soup.find_all(True):
            attrs = element.attrs
            if not attrs:
                continue
            classes = " ".join(attrs.get("class", []))
            if classes and any(p.search(classes) for p in _NOISE_CLASS_PATTERNS):
                to_remove.append(element)
                continue
            style = str(attrs.get("style", "")).lower()
            if "display: none" in style or "display:none" in style:
                to_remove.append(element)

        for element in to_remove:
            element.decompose()

        cleaned_html = str(soup)

        # ── Step 2: Readability 正文提取 ──
        title = ""
        readable_html = ""
        try:
            doc = Document(cleaned_html)
            title = doc.short_title() or ""
            readable_html = doc.summary(html_partial=True)
        except Exception:
            pass

        # Readability 提取内容太少 → 回退到 <main>/<article>/<body>
        if len(readable_html) < 200:
            for selector in ["main", "article", "#content", ".content", ".markdown-body", "body"]:
                found = soup.find(selector)
                if found:
                    readable_html = str(found)
                    break
            if not title:
                title = self._extract_title(soup)

        if not title:
            title = self._extract_title(soup)

        # ── Step 3: 转 Markdown ──
        h2t = _make_h2t()
        markdown = h2t.handle(readable_html).strip()
        # 清理多余空行
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        cleaned_chars = len(markdown)

        # ── Step 4: 结构化为分段 ──
        sections = self._split_sections(markdown)

        # 判断是否提取到有效内容
        has_content = cleaned_chars > 50 and len(sections) > 0

        result = {
            "url": url,
            "title": title,
            "sections": sections,
            "raw_markdown": markdown[:20000],  # 截断防止过长
            "stats": {
                "original_chars": original_chars,
                "cleaned_chars": cleaned_chars,
            },
        }

        if not has_content:
            result["warning"] = "未提取到正文，可能为动态渲染页面"

        return result

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """从 soup 中提取标题。"""
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return ""

    def _split_sections(self, markdown: str) -> list[dict[str, str]]:
        """把 Markdown 按标题分割成段落。

        返回: [{"heading": "标题", "content": "内容"}, ...]
        """
        sections = []
        current_heading = ""
        current_lines: list[str] = []

        for line in markdown.split("\n"):
            # 检测 Markdown 标题 (#, ##, ###)
            heading_match = re.match(r"^(#{1,4})\s+(.+)", line)
            if heading_match:
                # 保存上一个段落
                if current_lines or current_heading:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_lines).strip(),
                    })
                current_heading = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        # 保存最后一个段落
        if current_lines or current_heading:
            content = "\n".join(current_lines).strip()
            if content or current_heading:
                sections.append({
                    "heading": current_heading,
                    "content": content,
                })

        # 过滤掉空段落
        return [s for s in sections if s["content"] or s["heading"]]

    def parse_for_llm(self, html: str, url: str = "", parsed: dict | None = None) -> str:
        """解析 HTML 并返回给 LLM 用的精简文本。

        parsed: 已解析的结果（避免重复解析同一份 HTML）。
        返回: 标题 + 各段内容的纯文本，控制在合理长度内。
        """
        if parsed is None:
            parsed = self.parse(html, url)

        parts = [f"标题: {parsed['title']}"]
        if url:
            parts.append(f"URL: {url}")

        for section in parsed["sections"]:
            if section["heading"]:
                parts.append(f"\n## {section['heading']}")
            if section["content"]:
                parts.append(section["content"][:2000])

        text = "\n".join(parts)

        # 如果解析结果太短，可能失败，加个警告
        if len(text) < 100 and parsed.get("warning"):
            text += f"\n\n[注意: {parsed['warning']}]"

        return text
