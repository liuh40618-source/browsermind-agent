"""
Reflection Agent - 任务完成度评估 + 下一步决策器（闭环版）

这是 Agent 闭环的核心决策器，不再只是"日志评论员"：
- 评估当前信息是否足以完成任务
- 若不足，输出机器可执行的下一次动作（next_action）
- next_action 会被回灌到执行循环，驱动 Agent 继续行动

输出契约：
{
    "success": true/false,          # 信息是否足够完成任务
    "score": 0-100,                 # 完成度评分
    "reason": "为什么完成/未完成",    # 中文说明
    "missing": ["缺少的信息1", ...], # 仍缺失的关键信息
    "next_action": {                # 机器可执行的下一次动作（success=true 时为 null）
        "type": "search|open_page|get_text|click|scroll|type|finish",
        ...参数
    } | null
}
"""

import json
from typing import Any

REFLECTION_PROMPT = """\
You are the Reflection module of BrowserMind, an autonomous AI agent.

Your job is to evaluate whether the agent has gathered enough information
to complete the user's task, and if NOT, decide the NEXT CONCRETE ACTION.

Given:
- The user's original task
- All information gathered so far (extracted_info)
- Pages visited
- Current task state (completed steps, missing info, next action)

Decide:
1. success: Has enough information been collected to genuinely answer
   the task? Be strict - only true if the gathered info truly answers
   the task.
2. score: Completion score 0-100.
3. reason: Why complete or incomplete, what's missing (in Chinese).
4. missing: A list of specific missing pieces of information (in
   Chinese). Empty list if success.
5. next_action: The NEXT machine-executable tool call. MUST be one of:
   - {"type": "search", "query": "..."}
   - {"type": "open_page", "url": "..."}
   - {"type": "get_text"}
   - {"type": "click", "text": "..."}
   - {"type": "scroll", "direction": "down"}
   - {"type": "type", "selector": "...", "value": "..."}
   - {"type": "finish", "summary": "..."}
     # when you determine the task is impossible or already complete
   Set next_action to null if success=true.

Return ONLY a JSON object:
{
    "success": true/false,
    "score": 0-100,
    "reason": "...",
    "missing": ["...", "..."],
    "next_action": {"type": "...", ...} or null
}

Be strict and honest: do not return success=true if key information
is still missing."""


class Reflection:
    """反思决策器：评估完成度 + 输出下一步可执行动作。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def evaluate(
        self,
        task: str,
        extracted_info: list[dict[str, Any]],
        visited_pages: list[str],
        task_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """评估当前信息是否足够完成任务；若不足，给出下一步可执行动作。

        参数:
            task: 用户原始任务
            extracted_info: Agent 已收集的所有信息
            visited_pages: 已访问的页面 URL
            task_state: 当前任务状态（goal/completed_steps/missing/next_action）

        返回:
            标准化的评估结果 dict（见模块头注释契约）
        """
        state_desc = "（尚无状态）"
        if task_state:
            state_desc = json.dumps(task_state, ensure_ascii=False, indent=2)

        context = f"""任务：{task}

已访问页面：{visited_pages}

当前任务状态：
{state_desc}

已收集信息：
{json.dumps(extracted_info, ensure_ascii=False, indent=2)}
"""
        content = await self._llm.chat(
            messages=[
                {"role": "system", "content": REFLECTION_PROMPT},
                {"role": "user", "content": context},
            ],
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "success": False,
                "score": 0,
                "reason": "反思结果解析失败",
                "missing": [],
                "next_action": None,
            }

        return self._normalize(result)

    def _normalize(self, result: dict[str, Any]) -> dict[str, Any]:
        """标准化反思输出，保证字段完整、类型正确。"""
        success = bool(result.get("success", False))
        score = result.get("score", 0)
        try:
            score = int(score)
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(100, score))

        reason = str(result.get("reason", "")).strip()
        missing = result.get("missing", [])
        if not isinstance(missing, list):
            missing = [str(missing)] if missing else []
        else:
            missing = [str(m) for m in missing]

        next_action = result.get("next_action")
        if success:
            next_action = None
        elif not isinstance(next_action, dict) or "type" not in next_action:
            next_action = None

        return {
            "success": success,
            "score": score,
            "reason": reason,
            "missing": missing,
            "next_action": next_action,
        }

    @staticmethod
    def format_next_action(next_action: dict[str, Any] | None) -> str:
        """把 next_action 转成人类可读描述（供日志/前端展示）。"""
        if not next_action or not isinstance(next_action, dict):
            return "无"
        t = next_action.get("type", "?")
        if t == "search":
            return f"搜索：{next_action.get('query', '')}"
        if t == "open_page":
            return f"打开页面：{next_action.get('url', '')}"
        if t == "get_text":
            return "获取当前页面文本"
        if t == "click":
            return f"点击：{next_action.get('text', '')}"
        if t == "scroll":
            return f"滚动 {next_action.get('direction', 'down')}"
        if t == "type":
            return f"输入：{next_action.get('value', '')}"
        if t == "finish":
            return f"结束：{next_action.get('summary', '')[:60]}"
        return json.dumps(next_action, ensure_ascii=False)
