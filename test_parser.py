"""测试阶段3：Parser 网页理解效果。

对比：原始 HTML 字符数 vs 清洗后 Markdown 字符数 vs 结构化分段数
"""

import asyncio
import sys
sys.path.insert(0, ".")

from tools.browser import BrowserTool
from tools.parser import Parser


async def main():
    browser = BrowserTool()
    await browser.start()

    # 测试1：GitHub 项目页（复杂页面，大量噪声）
    print("=" * 60)
    print("测试1: GitHub 项目页 (langchain)")
    print("=" * 60)
    await browser.open_page("https://github.com/langchain-ai/langchain")

    page = browser._page
    html = await page.content()
    raw_chars = len(html)

    parser = Parser()
    result = parser.parse(html, "https://github.com/langchain-ai/langchain")

    print(f"  原始 HTML: {raw_chars:,} 字符")
    print(f"  清洗后 Markdown: {result['stats']['cleaned_chars']:,} 字符")
    print(f"  压缩比: {result['stats']['cleaned_chars']/raw_chars*100:.1f}%")
    print(f"  标题: {result['title']}")
    print(f"  分段数: {len(result['sections'])}")

    print(f"\n  分段预览（前5段）:")
    for i, s in enumerate(result["sections"][:5]):
        heading = s["heading"] or "(无标题)"
        content_preview = s["content"][:120].replace("\n", " ")
        print(f"    [{i+1}] {heading}")
        print(f"        {content_preview}...")

    if result.get("warning"):
        print(f"\n  ⚠️ {result['warning']}")

    # 测试2：普通网页
    print("\n" + "=" * 60)
    print("测试2: 普通 Web 页面 (example.com)")
    print("=" * 60)
    await browser.open_page("https://example.com")
    html2 = await page.content()
    result2 = parser.parse(html2, "https://example.com")

    print(f"  原始 HTML: {len(html2):,} 字符")
    print(f"  清洗后: {result2['stats']['cleaned_chars']:,} 字符")
    print(f"  标题: {result2['title']}")
    print(f"  分段数: {len(result2['sections'])}")
    print(f"\n  Markdown 内容:")
    print(f"  {result2['raw_markdown'][:500]}")

    # 测试3：通过 get_text 工具（验证集成）
    print("\n" + "=" * 60)
    print("测试3: get_text 工具集成 Parser")
    print("=" * 60)
    await browser.open_page("https://github.com/langchain-ai/langchain")
    r = await browser.get_text()
    print(f"  状态: {r['status']}")
    print(f"  消息: {r['message']}")
    if r["status"] == "success":
        print(f"  标题: {r['data']['title']}")
        print(f"  清洗后文本长度: {len(r['data']['text']):,} 字符")
        print(f"  分段数: {len(r['data'].get('sections', []))}")
        print(f"  统计: {r['data'].get('stats', {})}")
        print(f"  前300字:\n  {r['data']['text'][:300]}")

    await browser.close()
    print("\n✅ 阶段3 Parser 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
