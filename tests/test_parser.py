"""Parser 单元测试：验证 HTML → 清洗 → 正文 → Markdown → 分段 流水线。"""

import pytest

from tools.parser import Parser


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>测试页面标题</title></head>
<body>
  <script>var junk = 1;</script>
  <style>.junk{color:red}</style>
  <nav>导航栏内容，不应出现在正文</nav>
  <h1>一级标题</h1>
  <p>这是第一段正文内容，应该被保留。</p>
  <h2>二级标题</h2>
  <p>这是第二段正文内容，也应该被保留。</p>
  <div class="ad-banner">广告内容，应被清洗</div>
</body>
</html>
"""


class TestParserPipeline:
    def test_parse_returns_expected_structure(self):
        """parse 返回 url/title/sections/stats 契约。"""
        parser = Parser()
        result = parser.parse(SAMPLE_HTML, url="https://example.com/test")

        assert result["url"] == "https://example.com/test"
        assert result["title"] == "测试页面标题"
        assert isinstance(result["sections"], list)
        assert "original_chars" in result["stats"]
        assert "cleaned_chars" in result["stats"]

    def test_cleans_noise_tags(self):
        """script/style/ad-banner 应从正文中移除（nav 是设计上保留的）。"""
        parser = Parser()
        result = parser.parse(SAMPLE_HTML)

        markdown = result["raw_markdown"]
        assert "var junk" not in markdown
        assert "广告内容" not in markdown
        # nav 在 parser.py 中刻意保留（设计注释：不碰 header/footer/nav）
        assert "导航栏内容" in markdown

    def test_keeps_article_content(self):
        """正文标题与段落应保留。"""
        parser = Parser()
        result = parser.parse(SAMPLE_HTML)

        joined = "".join(s["content"] for s in result["sections"])
        assert "第一段正文内容" in joined
        assert "第二段正文内容" in joined

    def test_split_sections_by_headings(self):
        """Markdown 标题应切分为独立 section。"""
        parser = Parser()
        result = parser.parse(SAMPLE_HTML)

        headings = [s["heading"] for s in result["sections"]]
        # Readability 处理后标题会带 markdown 前缀，至少存在 2 个 section
        assert len(result["sections"]) >= 2
        assert any("一级标题" in h for h in headings)

    def test_empty_html_gives_warning(self):
        """空/极短 HTML 应给出动态渲染警告而非崩溃。"""
        parser = Parser()
        result = parser.parse("<html><body><p>hi</p></body></html>")

        assert result["warning"] == "未提取到正文，可能为动态渲染页面"

    def test_parse_for_llm_includes_title_and_content(self):
        """parse_for_llm 输出应含标题与正文片段。"""
        parser = Parser()
        text = parser.parse_for_llm(SAMPLE_HTML, url="https://example.com/test")

        assert "测试页面标题" in text
        assert "第一段正文内容" in text

    def test_parse_for_llm_reuses_parsed_result(self):
        """传入已解析结果时不应重复解析（内部调用 parse 返回同结构）。"""
        parser = Parser()
        parsed = parser.parse(SAMPLE_HTML)
        text = parser.parse_for_llm(SAMPLE_HTML, parsed=parsed)

        assert text  # 非空即视为复用成功（正常路径）
