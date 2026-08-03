"""
Planner Agent - 把用户需求变成计划。

输入：用户自然语言任务
输出：结构化步骤列表

例如：
    输入："找5个AI视频生成工具，比较价格和功能"
    输出：
    {
      "steps": [
        {"type": "search", "query": "AI video generator", "goal": "找到候选工具"},
        {"type": "visit", "target": "official website", "goal": "了解产品"},
        {"type": "extract", "fields": ["price", "features"], "goal": "收集价格和功能"},
        {"type": "analyze", "goal": "比较并生成报告"}
      ]
    }
"""

import json
from typing import Any

PLANNER_PROMPT = """You are a task planner for BrowserMind, an autonomous AI agent.

Given a user's task, break it down into a sequence of executable steps.

Each step must have:
- "name": a short label for this step (in Chinese, 4-10 chars, e.g. "搜索候选工具")
- "type": one of "search" | "visit" | "extract" | "analyze"
- "goal": what this step aims to achieve (in Chinese)
- "status": always "pending" (will be updated during execution)

For "search" steps, include "query" (the search keyword).
For "visit" steps, include "target" (what kind of page to visit).
For "extract" steps, include "fields" (list of info to extract).
For "analyze" steps, no extra fields needed (it's the final analysis).

Return ONLY a JSON object with a "steps" array. No explanation."""


class Planner:
    """任务规划器：把用户任务拆解为步骤序列。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def plan(self, task: str) -> list[dict[str, Any]]:
        """把用户任务拆解为步骤列表。"""
        content = await self._llm.chat(
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": f"任务：{task}"},
            ],
            response_format={"type": "json_object"},
        )

        result = json.loads(content)
        steps = result.get("steps", [])

        # 确保每个 step 都有 name 和 status 字段
        for i, step in enumerate(steps):
            if not step.get("name"):
                step["name"] = f"步骤{i+1}"
            step.setdefault("status", "pending")

        return steps
