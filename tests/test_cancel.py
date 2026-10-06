"""AgentLoop 取消行为测试：验证 cancel_event 置位后循环优雅退出。"""

import asyncio

import pytest

from agent.agent_loop import AgentLoop
from agent.state import AgentState


class FakeLLM:
    """假的 LLM：第一次返回一个 search 调用，之后挂起（模拟慢任务）。"""

    def __init__(self):
        self.calls = 0

    async def decide_action(self, task, history):
        self.calls += 1
        if self.calls == 1:
            return {"tool": "search", "arguments": {"query": "test"}, "thought": "先搜一下"}
        # 之后永远不返回 done（模拟 LLM 卡住）
        await asyncio.sleep(60)
        return {"done": True, "answer": ""}


class FakeBrowser:
    """假的浏览器：search 不需要真浏览器，用 search_tool 即可。"""

    async def execute(self, tool, arguments):
        return {"tool": tool, "status": "success", "message": "ok", "data": {}}


class FakeSearch:
    async def search(self, query, max_results=5):
        return {
            "tool": "search",
            "status": "success",
            "message": "ok",
            "data": {"results": [{"title": "t", "url": "u", "snippet": "s"}]},
        }


def make_loop():
    loop = AgentLoop(FakeBrowser(), FakeLLM(), planner=None, reflection=None, analyst=None)
    loop.search_tool = FakeSearch()
    return loop


class TestCancel:
    def test_cancel_event_stops_loop(self):
        """取消事件置位后，循环应在下一轮开始前退出并标记 cancelled。"""
        loop = make_loop()
        cancel_event = asyncio.Event()
        loop.set_cancel_event(cancel_event)

        async def scenario():
            # 启动循环任务，但立刻安排取消
            async def run_and_cancel():
                cancel_event.set()  # 第一轮开始前就取消
                state = await loop.run("测试任务")
                return state

            state = await asyncio.wait_for(run_and_cancel(), timeout=5)
            return state

        state = asyncio.run(scenario())
        assert state.status == "cancelled"
        # _generate_failure_report 使用"停止"措辞
        assert "停止" in state.final_report

    def test_cancel_after_first_tool_call(self):
        """执行过一次工具调用后取消，应保留已收集信息并标记 cancelled。"""
        loop = make_loop()
        cancel_event = asyncio.Event()
        loop.set_cancel_event(cancel_event)

        async def scenario():
            # 第一次 decide_action 返回 search → 执行 → 第二轮开始前取消
            state = await asyncio.wait_for(loop.run("测试任务"), timeout=10)
            return state

        # 安排：第一次调用 decide 期间置位 cancel（此时 calls==0，尚未执行 original）
        original_decide = loop.llm.decide_action

        async def decide_with_cancel(task, history):
            if loop.llm.calls == 0:
                cancel_event.set()
            return await original_decide(task, history)

        loop.llm.decide_action = decide_with_cancel
        state = asyncio.run(scenario())
        assert state.status == "cancelled"
        # 第一次 search 已执行，extracted_info 应有内容
        assert len(state.extracted_info) >= 1

    def test_no_cancel_runs_normally(self):
        """未置位取消事件时，循环行为不变（由 LLM 的 finish 收尾）。

        零信息 + done → 按真实逻辑标记 partial（_produce_report 设计行为）。
        """

        class DoneLLM(FakeLLM):
            async def decide_action(self, task, history):
                self.calls += 1
                return {"done": True, "answer": "完成"}

        loop = AgentLoop(FakeBrowser(), DoneLLM(), planner=None, reflection=None, analyst=None)
        state = asyncio.run(loop.run("简单任务"))
        assert state.status in ("done", "partial")
        assert "完成" in state.final_report
