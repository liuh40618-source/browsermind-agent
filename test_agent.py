"""测试 LLM + 浏览器完整闭环：用户输入任务 → AI 决定浏览器操作 → 执行。"""

import asyncio
import sys
sys.path.insert(0, ".")

from tools.browser import BrowserTool
from agent.llm import LLMClient


async def main():
    browser = BrowserTool()
    llm = LLMClient()

    await browser.start()

    task = "打开 GitHub 首页，获取页面标题和前 500 个字符的文本内容"
    print(f"📋 任务: {task}\n")

    # 第1轮：LLM 决策
    print("🧠 LLM 正在思考...")
    history = []
    decision = await llm.decide_action(task, history)

    if decision.get("done"):
        print(f"  LLM 直接回答: {decision.get('answer')}")
        await browser.close()
        return

    print(f"  思考: {decision.get('thought', '(无)')}")
    print(f"  调用工具: {decision['tool']}")
    print(f"  参数: {decision['arguments']}")

    # 记录工具调用到历史
    history.append({
        "role": "assistant",
        "content": decision.get("thought", ""),
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": decision["tool"], "arguments": str(decision["arguments"])},
        }],
    })

    # 执行浏览器操作
    print("\n🌐 执行浏览器操作...")
    result = await browser.execute(decision["tool"], decision["arguments"])
    print(f"  状态: {result['status']}")
    print(f"  消息: {result['message']}")

    if result["status"] == "success" and result["data"]:
        # 把结果喂回给 LLM，让它继续
        observation = f"工具返回: {result['data']}"
        if "text" in result["data"]:
            observation = f"页面标题: {result['data'].get('title','')}\n页面文本(前500字): {result['data']['text'][:500]}"
        elif "title" in result["data"]:
            observation = f"页面标题: {result['data']['title']}"

        # 记录工具结果到历史
        history.append({
            "role": "tool",
            "tool_call_id": "call_1",
            "content": observation,
        })

        print(f"\n📤 观察结果:\n  {observation[:300]}")

        print("\n🧠 LLM 第二轮思考...")
        decision2 = await llm.decide_action(task, history)
        if decision2.get("done"):
            print(f"  ✅ 任务完成")
            print(f"  回答: {decision2.get('answer')}")
        else:
            print(f"  LLM 想继续: {decision2['tool']}({decision2.get('arguments')})")
            print("  （阶段1单轮测试，到此为止）")

    await browser.close()
    print("\n✅ LLM + 浏览器闭环测试完成")


if __name__ == "__main__":
    asyncio.run(main())
