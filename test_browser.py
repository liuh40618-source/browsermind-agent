"""快速测试浏览器工具（不依赖 LLM）。"""

import asyncio
import sys
sys.path.insert(0, ".")

from tools.browser import BrowserTool


async def main():
    browser = BrowserTool()
    await browser.start()

    print("=== 测试 open_page ===")
    r = await browser.open_page("https://github.com")
    print(f"  status: {r['status']}")
    print(f"  message: {r['message']}")
    if r["status"] == "success":
        print(f"  title: {r['data']['title']}")

    print("\n=== 测试 get_text ===")
    r = await browser.get_text()
    print(f"  status: {r['status']}")
    if r["status"] == "success":
        print(f"  title: {r['data']['title']}")
        print(f"  text length: {len(r['data']['text'])} chars")
        print(f"  first 200 chars: {r['data']['text'][:200]}")

    print("\n=== 测试 screenshot ===")
    r = await browser.screenshot()
    print(f"  status: {r['status']}")
    if r["status"] == "success":
        print(f"  screenshot base64 length: {len(r['data']['screenshot'])}")

    print("\n=== 测试 scroll ===")
    r = await browser.scroll("down", 2)
    print(f"  status: {r['status']}")
    print(f"  message: {r['message']}")

    await browser.close()
    print("\n✅ 浏览器工具测试完成")


if __name__ == "__main__":
    asyncio.run(main())
