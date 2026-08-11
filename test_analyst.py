"""测试阶段4：Analyst 报告生成。

完整流程：Planner → Agent循环(搜索+浏览+提取) → Reflection → Analyst报告
"""

import asyncio
import sys
sys.path.insert(0, ".")

from tools.browser import BrowserTool
from agent.llm import LLMClient
from agent.planner import Planner
from agent.reflection import Reflection
from agent.analyst import Analyst
from agent.agent_loop import AgentLoop


async def main():
    browser = BrowserTool()
    llm = LLMClient()
    planner = Planner()
    reflection = Reflection()
    analyst = Analyst()

    await browser.start()

    loop = AgentLoop(browser, llm, planner, reflection, analyst)

    def on_log(log: dict):
        print(f"  [{log['agent']}] {log['action']}"
              + (f" — {log['detail']}" if log.get('detail') else ""))

    loop.on_log(on_log)

    # 测试任务
    task = "搜索 Python 最流行的 Web 框架，找到排名前 3 的项目，获取它们的 GitHub Star 数和简介"
    print(f"📋 任务: {task}\n")
    print("─" * 60)

    state = await loop.run(task)

    print("\n" + "=" * 60)
    print("📊 执行结果")
    print("=" * 60)
    print(f"状态: {state.status}")
    print(f"访问页面数: {len(state.visited_pages)}")
    for url in state.visited_pages:
        print(f"  - {url}")
    print(f"提取信息数: {len(state.extracted_info)}")

    print("\n" + "=" * 60)
    print("📄 最终报告（Analyst 生成）")
    print("=" * 60)
    print(state.final_report if state.final_report else "(无报告)")

    # 保存报告到文件
    report_path = "report_output.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(state.final_report or "")
    print(f"\n📁 报告已保存到: {report_path}")

    await browser.close()
    print("\n✅ 阶段4 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
