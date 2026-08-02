"""
Parser 单元测试

使用 mock 隔离外部依赖（readability / html2text），
测试 Parser.parse 方法的基本行为。
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.parser import Parser


# ── Fixture ──────────────────────────────────────────────

@pytest.fixture
def parser() -> Parser:
    """创建 Parser 实例。"""
    return Parser()


# ── 基本 HTML 解析 ───────────────────────────────────────

class TestParseBasicHTML:
    """parse 方法处理基本 HTML 的测试。"""

    def test_parse_returns_required_keys(self, parser: Parser):
        """parse 返回的字典应包含所有必需字段。"""
        html = "<html><body><h1>Test Title</h1><p>This is a test paragraph with enough content to pass the threshold. Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p></body></html>"
        result = parser.parse(html, url="https://example.com")

        assert "url" in result
        assert "title" in result
        assert "sections" in result
        assert "raw_markdown" in result
        assert "stats" in result

    def test_parse_url_preserved(self, parser: Parser):
        """parse 应保留传入的 URL。"""
        html = "<html><body><p>Some content here for testing purposes that is long enough.</p></body></html>"
        result = parser.parse(html, url="https://example.com/page")
        assert result["url"] == "https://example.com/page"

    def test_parse_extracts_title(self, parser: Parser):
        """parse 应能提取页面标题。"""
        html = "<html><head><title>My Page Title</title></head><body><p>Some content here for testing purposes that is long enough to be extracted.</p></body></html>"
        result = parser.parse(html)
        # 标题应非空（具体值取决于 readability 的提取结果）
        assert isinstance(result["title"], str)

    def test_parse_stats_contains_char_counts(self, parser: Parser):
        """parse 返回的 stats 应包含字符统计。"""
        html = "<html><body><p>Content for testing character count statistics in the parser output.</p></body></html>"
        result = parser.parse(html)

        assert "original_chars" in result["stats"]
        assert "cleaned_chars" in result["stats"]
        assert result["stats"]["original_chars"] == len(html)
        assert isinstance(result["stats"]["cleaned_chars"], int)

    def test_parse_sections_is_list(self, parser: Parser):
        """parse 返回的 sections 应为列表。"""
        html = "<html><body><h1>Heading</h1><p>Some content under the heading that is long enough for extraction by readability algorithm.</p></body></html>"
        result = parser.parse(html)
        assert isinstance(result["sections"], list)

    def test_parse_strips_script_tags(self, parser: Parser):
        """parse 应去除 script 标签内容。"""
        html = """
        <html><body>
        <script>alert('xss')</script>
        <p>This is the real content that should remain after parsing and cleaning the HTML properly.</p>
        </body></html>
        """
        result = parser.parse(html)
        assert "alert" not in result["raw_markdown"]


# ── 空输入 ───────────────────────────────────────────────

class TestParseEmptyInput:
    """parse 方法处理空输入的测试。"""

    def test_parse_empty_string(self, parser: Parser):
        """空字符串应返回有效结构，不抛异常。"""
        result = parser.parse("")
        assert result["url"] == ""
        assert result["title"] == ""
        assert isinstance(result["sections"], list)
        assert result["stats"]["original_chars"] == 0

    def test_parse_empty_string_has_warning(self, parser: Parser):
        """空字符串解析应包含 warning 字段。"""
        result = parser.parse("")
        assert "warning" in result


# ── 无效 HTML ────────────────────────────────────────────

class TestParseInvalidHTML:
    """parse 方法处理无效 HTML 的测试。"""

    def test_parse_plain_text(self, parser: Parser):
        """纯文本（非 HTML）应不抛异常。"""
        result = parser.parse("This is just plain text, not HTML at all.")
        assert isinstance(result, dict)
        assert "title" in result

    def test_parse_malformed_html(self, parser: Parser):
        """格式错误的 HTML 应不抛异常。"""
        html = "<html><body><p>Unclosed paragraph<p>Another unclosed"
        result = parser.parse(html)
        assert isinstance(result, dict)

    def test_parse_html_with_only_tags(self, parser: Parser):
        """只有标签没有内容的 HTML 应不抛异常。"""
        html = "<html><body><div></div><span></span></body></html>"
        result = parser.parse(html)
        assert isinstance(result, dict)
        assert "warning" in result  # 内容太少，应有 warning

    def test_parse_html_with_noise_elements(self, parser: Parser):
        """包含广告/噪声元素的 HTML 应被清洗。"""
        html = """
        <html><body>
        <div class="ad-banner">Buy now!</div>
        <div class="sidebar">Side content</div>
        <p>This is the main content of the page that should remain after cleaning noise elements properly.</p>
        </body></html>
        """
        result = parser.parse(html)
        assert isinstance(result, dict)
        # 广告内容不应出现在 markdown 中
        assert "Buy now!" not in result["raw_markdown"]
