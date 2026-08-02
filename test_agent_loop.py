"""测试阶段2：Agent 完整循环。

测试场景：让 Agent 自主搜索、浏览、提取信息。
"""

import asyncio
import sys
sys.path.insert(0, ".")

from tools.browser import BrowserTool
from agent.llm import LLMClient
from agent.planner import Planner
from agent.reflection import Reflection
from agent.agent_loop import AgentLoop


async def main():
    browser = BrowserTool()
    llm = LLMClient()
    planner = Planner()
    reflection = Reflection()

    await browser.start()

    loop = AgentLoop(browser, llm, planner, reflection)

    # 注册日志回调：实时打印
    def on_log(log: dict):
        time_str = ""
        print(f"  [{log['agent']}] {log['action']}"
              + (f" — {log['detail']}" if log.get('detail') else ""))

    loop.on_log(on_log)

    # 测试任务（简单一点，验证循环能跑通）
    task = "打开 GitHub，搜索 'langchain'，找到 Star 数最多的项目，获取项目介绍"
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
    print(f"\n提取信息数: {len(state.extracted_info)}")
    print(f"\n最终报告:\n{state.final_report[:1000] if state.final_report else '(无)'}")
    print(f"\n日志数: {len(state.logs)}")

    await browser.close()
    print("\n✅ 阶段2 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
