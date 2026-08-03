"""
Agent Loop - 核心执行引擎（Reflection 闭环版）

这是整个系统的心脏：思考 → 行动 → 观察 → 反思 → 继续思考

闭环工作流程：
1. Planner 拆解任务（可选，给 LLM 参考）
2. 循环：
   a. LLM 根据任务+历史，决定下一步操作
   b. 执行工具（search / browser）
   c. 如果是 get_text，自动提取结构化信息存入 State
   d. 把观察结果加入对话历史
   e. Reflection 评估完成度：
      - 完成 → 生成报告，结束
      - 未完成 → 输出 next_action，注入对话历史，驱动下一轮
   f. 重复，直到完成或达到最大轮次
3. 返回最终结果

关键变化：Reflection 从"事后日志评论员"升级为"事中决策器"，
其 next_action 会回灌到执行循环，真正形成 执行→反思→调整→再执行 的闭环。
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable

from agent.analyst import Analyst
from agent.llm import LLMClient
from agent.planner import Planner
from agent.reflection import Reflection
from agent.state import AgentState
from tools import BROWSER_TOOLS, SEARCH_TOOLS
from tools.browser import BrowserTool
from tools.search import SearchTool

# 最大循环次数（防止无限循环）—— 总执行步数硬上限
MAX_ITERATIONS = 15

# 闭环反思安全阀：连续判定"未完成"达到此次数后，强制停止反思并出报告
MAX_REFLECTION_FAILURES = 3

# 非信息更新轮次下，每隔多少轮触发一次反思（兜底，防止 Agent 一直不调用 get_text）
REFLECT_INTERVAL = 2

# 短期记忆：保留最近 N 轮的对话历史（每轮 = assistant + tool 两条消息）
SHORT_TERM_ROUNDS = 5


class AgentLoop:
    """Agent 执行循环引擎（带 Reflection 闭环）。"""

    def __init__(
        self,
        browser: BrowserTool,
        llm: LLMClient,
        planner: Planner | None = None,
        reflection: Reflection | None = None,
        analyst: Analyst | None = None,
    ):
        self.browser = browser
        self.llm = llm
        self.planner = planner
        self.reflection = reflection
        self.analyst = analyst
        self.search_tool = SearchTool()
        self.state = AgentState()
        self._log_callback: Callable[[dict], Any] | None = None
        # 用户决策队列（Human-in-the-Loop）
        self._decision_queue: asyncio.Queue[str] | None = None
        self._decision_callback: Callable[[dict], Any] | None = None
        # 用户追加指令队列（多轮对话）
        self._instruction_queue: asyncio.Queue[str] | None = None
        # 闭环反思状态
        self._reflection_failures = 0  # 连续"未完成"次数
        self._last_reflect_iteration = 0  # 上次反思的轮次
        self._reflection_count = 0  # 总反思次数

    def on_log(self, callback: Callable[[dict], Any]):
        """注册日志回调（供前端 WebSocket 实时展示）。"""
        self._log_callback = callback

    def on_decision(self, queue: asyncio.Queue[str], callback: Callable[[dict], Any]):
        """注册用户决策通道（Human-in-the-Loop）。

        - queue: 前端发回的决策（"continue" / "stop"）通过此队列传入
        - callback: 反思结果产生时调用，供前端展示决策按钮
        """
        self._decision_queue = queue
        self._decision_callback = callback

    def set_instruction_queue(self, queue: asyncio.Queue[str]):
        """设置追加指令队列（多轮对话）。

        前端通过 WebSocket 发送的追加指令通过此队列传入 Agent 循环。
        """
        self._instruction_queue = queue

    def has_pending_instructions(self) -> bool:
        """检查是否有待处理的追加指令。"""
        return (
            self._instruction_queue is not None and not self._instruction_queue.empty()
        )

    def set_previous_state(self, state: "AgentState"):
        """继承上一轮任务的状态（用于追加提问场景）。

        将前一轮的提取信息、访问页面等复制到当前 state，
        让新轮次的 Agent 能基于之前的工作继续执行。

        注意：不复制 plan_steps —— 旧计划全部 done 会污染 LLM 上下文，
        导致 LLM 误认为任务已完成。新一轮由 Planner 重新生成计划。
        """
        self.state.extracted_info = list(state.extracted_info)
        self.state.visited_pages = list(state.visited_pages)
        # plan / plan_steps 不复制：旧的已全 done，会误导 LLM
        # Planner 会在 run() 中根据新任务重新生成
        self.state.plan = []
        self.state.plan_steps = []
        self.state.task_state = dict(state.task_state) if state.task_state else {}
        # 重置状态
        self.state.status = "idle"
        self.state.final_report = ""
        self.state.duration_seconds = 0
        # 重置反思计数
        self._reflection_failures = 0
        self._last_reflect_iteration = 0
        self._reflection_count = 0

    def _emit_log(self, agent: str, action: str, detail: str = ""):
        """发送日志（含时间戳，供前端实时展示）。"""
        log = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "agent": agent,
            "action": action,
            "detail": detail,
        }
        self.state.add_log(agent, action, detail)
        if self._log_callback:
            self._log_callback(log)

    async def run(self, task: str) -> AgentState:
        """执行完整 Agent 循环（含 Reflection 闭环）。

        返回最终的 AgentState（含所有日志、提取信息、最终报告、任务状态）。
        """
        start_time = datetime.now()
        self.state.task = task
        self.state.status = "planning"
        self._emit_log("System", "任务开始", task)

        # 初始化任务状态
        self.state.task_state = {
            "goal": task,
            "completed_steps": [],
            "missing": [],
            "next_action": None,
            "score": 0,
        }

        # ── Step 0: Planner 拆解任务（状态驱动）──
        plan = []
        if self.planner:
            self._emit_log("Planner", "正在拆解任务...")
            try:
                plan = await self.planner.plan(task)
                self.state.plan = plan
                # 初始化带状态的 plan_steps
                self.state.init_plan_steps(plan)
                # 发送完整计划（前端据此实时渲染计划列表）
                self._emit_log("Planner", "plan", json.dumps(plan, ensure_ascii=False))
                # 发送带状态的 plan_steps（前端据此渲染状态指示器）
                self._emit_log(
                    "Planner",
                    "plan_steps",
                    json.dumps(self.state.plan_steps, ensure_ascii=False),
                )
                for i, step in enumerate(plan):
                    self._emit_log(
                        "Planner",
                        f"步骤 {i+1}: {step.get('type', '?')}",
                        step.get("goal", ""),
                    )
            except Exception as e:
                self._emit_log("Planner", "拆解失败，直接执行", str(e))

        # ── Step 1: 执行循环（状态驱动）──
        self.state.status = "browsing"
        conversation_history: list[dict[str, Any]] = []

        # 如果有前序状态（追加提问场景），注入之前的工作上下文
        if self.state.extracted_info or self.state.visited_pages:
            prev_context = "[前序工作上下文]\n"
            if self.state.visited_pages:
                prev_context += f"已访问页面：{', '.join(self.state.visited_pages)}\n"
            if self.state.extracted_info:
                prev_context += f"已收集 {len(self.state.extracted_info)} 条信息\n"
            prev_context += "请基于以上已有信息继续工作，避免重复操作。\n"
            conversation_history.append(
                {
                    "role": "user",
                    "content": prev_context,
                }
            )

        # 如果有计划，把计划状态摘要告诉 LLM（而非完整历史）
        if self.state.plan_steps:
            plan_summary = self.state.get_plan_summary()
            conversation_history.append(
                {
                    "role": "user",
                    "content": (
                        f"Here is the task plan with current status:\n"
                        f"{plan_summary}\n\n"
                        f"Execute the next pending step."
                        f" After completing a step, its status"
                        f" will be updated.\n"
                        f"Focus on the current running step"
                        f" or start the next pending one."
                    ),
                }
            )

        for iteration in range(1, MAX_ITERATIONS + 1):
            self._emit_log("Agent", f"第 {iteration} 轮思考...")

            # 0. 检查是否有用户追加指令（多轮对话）
            if self.has_pending_instructions():
                instructions = []
                while self.has_pending_instructions():
                    instr = self._instruction_queue.get_nowait()
                    instructions.append(instr)
                combined = "\n".join(instructions)
                self._emit_log("User", "收到追加指令", combined[:200])
                conversation_history.append(
                    {
                        "role": "user",
                        "content": (
                            f"[用户追加指令] {combined}\n"
                            "请根据以上追加指令调整你的执行计划。"
                        ),
                    }
                )

            # 1. LLM 决策（使用压缩后的上下文）
            try:
                compressed = self._compress_context(conversation_history)
                decision = await self.llm.decide_action(task, compressed)
            except Exception as e:
                self._emit_log("Agent", "LLM 决策失败", str(e))
                self.state.status = "error"
                break

            thought = decision.get("thought", "")
            if thought:
                self._emit_log("Agent", "思考", thought[:200])

            # 2. 检查是否完成（LLM 自己调用 finish）
            #    信任 LLM 的判断：它说完成了就直接出报告，不再让 Reflection 否决
            #    （Reflection 仍用于"达到最大轮次"时的兜底评估）
            if decision.get("done"):
                agent_summary = decision.get("answer", "")
                info_count = self._count_effective_info()
                self._emit_log(
                    "Agent",
                    "任务完成",
                    f"AI 认为已收集足够信息（{info_count} 条有效信息）",
                )
                # 有信息 → 正常完成；没信息 → 用 LLM 的摘要作为报告
                await self._produce_report(
                    task,
                    agent_summary,
                    status="done" if info_count > 0 else "partial",
                    wrap_partial=(info_count == 0),
                    info_count=info_count,
                )
                break

            # 3. 执行工具
            tool = decision.get("tool")
            arguments = decision.get("arguments", {})
            if not tool:
                self._emit_log("Agent", "LLM 返回无效决策", "缺少 tool 字段，跳过本轮")
                continue

            _args_str = json.dumps(arguments, ensure_ascii=False)[:200]
            self._emit_log("Agent", f"调用工具: {tool}", _args_str)

            # ─ Planner 状态驱动：匹配 plan step 并标记为 running ──
            matched_step_idx = self._match_step_to_tool(tool, arguments)
            if matched_step_idx is not None:
                step = self.state.start_step(matched_step_idx)
                if step:
                    _goal = step.get("goal", "")
                    self._emit_log(
                        "Planner",
                        f"开始: {step.get('name', '?')}",
                        f"[{matched_step_idx+1}] {_goal}",
                    )
                    self._emit_plan_steps()

            # 记录 LLM 的工具调用到对话历史
            conversation_history.append(
                {
                    "role": "assistant",
                    "content": thought,
                    "tool_calls": [
                        {
                            "id": f"call_{iteration}",
                            "type": "function",
                            "function": {
                                "name": tool,
                                "arguments": json.dumps(arguments, ensure_ascii=False),
                            },
                        }
                    ],
                }
            )

            # 执行
            if tool in BROWSER_TOOLS:
                result = await self.browser.execute(tool, arguments)
            elif tool in SEARCH_TOOLS:
                result = await self.search_tool.execute(tool, arguments)
            else:
                result = {
                    "tool": tool,
                    "status": "failed",
                    "message": f"Unknown tool: {tool}",
                    "data": {},
                }

            # 4. 处理结果
            self._emit_log(
                "Agent",
                f"工具结果: {result['status']}",
                result.get("message", "")[:200],
            )

            # ─ Planner 状态驱动：工具成功后标记 step 为 done ──
            if matched_step_idx is not None and result["status"] == "success":
                step = self.state.complete_step(matched_step_idx)
                if step:
                    self._emit_log(
                        "Planner",
                        f"完成: {step.get('name', '?')}",
                        f"[{matched_step_idx+1}] ✓",
                    )
                    self._emit_plan_steps()

            # 把结果加入对话历史（作为 tool 响应）
            observation = self._format_observation(result)
            conversation_history.append(
                {
                    "role": "tool",
                    "tool_call_id": f"call_{iteration}",
                    "content": observation,
                }
            )

            # 5. 如果是 get_text，自动提取信息存入 State
            new_info_extracted = False
            if tool == "get_text" and result["status"] == "success":
                page_data = result["data"]
                _title = page_data.get("title", "")
                self._emit_log("Parser", "提取信息", f"页面: {_title}")

                try:
                    extracted = await self.llm.extract_info(
                        task, page_data.get("text", "")
                    )
                    extracted["_source_url"] = page_data.get("url", "")
                    extracted["_source_title"] = page_data.get("title", "")
                    self.state.extracted_info.append(extracted)
                    new_info_extracted = True
                    _ext_str = json.dumps(extracted, ensure_ascii=False)[:200]
                    self._emit_log("Parser", "提取完成", _ext_str)
                except Exception as e:
                    self._emit_log("Parser", "提取失败", str(e))

            # 6. 记录访问的页面
            if tool in ("open_page", "open") and result["status"] == "success":
                url = arguments.get("url", "")
                if url and url not in self.state.visited_pages:
                    self.state.visited_pages.append(url)

            # 7. 搜索结果也存入提取信息
            if tool == "search" and result["status"] == "success":
                search_results = result["data"].get("results", [])
                self.state.extracted_info.append(
                    {
                        "_type": "search_results",
                        "_query": arguments.get("query", ""),
                        "results": search_results,
                    }
                )

            # 8. ── Reflection 闭环：执行 → 反思 → 调整 → 再执行 ──
            #    有新有效信息时立即反思；否则每隔 REFLECT_INTERVAL 轮兜底反思一次。
            if self.reflection and self._should_reflect(iteration, new_info_extracted):
                self._last_reflect_iteration = iteration
                finished = await self._reflection_step(task, conversation_history)
                if finished:
                    break

        else:
            # 循环结束但未完成 —— 有信息就当正常完成，没信息才算失败
            effective_info = self._count_effective_info()
            if effective_info == 0:
                # 完全没收集到有效信息 → failed
                self.state.status = "failed"
                self._emit_log(
                    "Agent",
                    f"达到最大轮次 ({MAX_ITERATIONS})，未收集到有效信息",
                )
                self.state.final_report = self._generate_failure_report(
                    task,
                    reason=(
                        "Agent 在多次尝试后未能获取到与任务相关的有效信息。"
                        "可能原因：搜索关键词不匹配、目标页面无法访问、"
                        "或所需信息需要登录/付费等权限。"
                    ),
                )
            else:
                # 只要有信息就正常出报告（不额外打"部分完成"标签）
                self.state.status = "done"
                self._emit_log(
                    "Agent",
                    f"达到最大轮次 ({MAX_ITERATIONS})，"
                    f"基于已有信息生成报告（{effective_info} 条有效信息）",
                )
                await self._produce_report(
                    task,
                    "Agent 达到最大轮次，以下是基于已收集信息的报告。",
                    status="done",
                    wrap_partial=False,
                    info_count=effective_info,
                )

        # ── Step 2: 最终 Reflection 评估（仅当循环内未做过闭环反思时）──
        # 闭环反思已在循环内驱动决策；这里只对"达到上限自然结束"的任务做一次最终评估，
        # 供前端展示完成度，不再影响流程。
        if (
            self.reflection
            and self.state.status not in ("error", "done")
            and self._reflection_count == 0
        ):
            self._emit_log("Reflection", "最终评估任务完成度...")
            try:
                evaluation = await self.reflection.evaluate(
                    task,
                    self.state.extracted_info,
                    self.state.visited_pages,
                    self.state.task_state or None,
                )
                self._update_task_state(evaluation)
                self._emit_reflection(evaluation)
            except Exception as e:
                self._emit_log("Reflection", "评估失败", str(e))

        # 计算任务耗时
        elapsed = (datetime.now() - start_time).total_seconds()
        self.state.duration_seconds = int(elapsed)
        _summary = (
            f"状态: {self.state.status} · "
            f"耗时: {self.state.duration_seconds}s · "
            f"反思 {self._reflection_count} 次"
        )
        self._emit_log("System", "任务结束", _summary)
        return self.state

    # ── 上下文压缩辅助方法 ────────────────────────────────

    def _compress_context(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """压缩对话历史：保留初始计划 + 最近 N 轮 + 实时计划摘要。

        策略：
        1. 保留第一条消息（计划摘要，role=user）
        2. 保留最近 SHORT_TERM_ROUNDS 轮（每轮 = assistant + tool）
        3. 在末尾追加当前 plan_steps 状态摘要（让 LLM 始终知道全局进度）
        """
        if not history:
            return history

        compressed: list[dict[str, Any]] = []

        # 1. 保留初始计划消息（第一条 user 消息）
        if history and history[0].get("role") == "user":
            compressed.append(history[0])

        # 2. 保留最近 N 轮对话（从后往前取 SHORT_TERM_ROUNDS * 2 条）
        remaining = history[1:]  # 去掉第一条计划消息
        max_messages = SHORT_TERM_ROUNDS * 2  # 每轮 = assistant + tool
        if len(remaining) > max_messages:
            remaining = remaining[-max_messages:]
        compressed.extend(remaining)

        # 3. 追加当前计划状态摘要（让 LLM 知道全局进度）
        if self.state.plan_steps:
            plan_summary = self.state.get_plan_summary()
            compressed.append(
                {
                    "role": "user",
                    "content": (
                        f"[当前计划状态]\n{plan_summary}\n"
                        f"请基于以上状态决定下一步操作。"
                    ),
                }
            )

        return compressed

    # ─ Planner 状态驱动辅助方法 ──────────────────────────

    def _match_step_to_tool(self, tool: str, arguments: dict) -> int | None:
        """把当前工具调用匹配到 plan_steps 中的 pending step。

        匹配规则：
        - search 工具 → type=search 的 pending step
        - open_page/open → type=visit 的 pending step
        - get_text → type=extract 的 pending step
        - 其他 → 第一个 pending step（兜底）
        """
        if not self.state.plan_steps:
            return None

        type_map = {
            "search": "search",
            "open_page": "visit",
            "open": "visit",
            "get_text": "extract",
        }
        expected_type = type_map.get(tool)

        # 优先匹配同类型的 pending step
        if expected_type:
            for i, s in enumerate(self.state.plan_steps):
                if s.get("status") == "pending" and s.get("type") == expected_type:
                    return i

        # 兜底：返回第一个 pending step
        for i, s in enumerate(self.state.plan_steps):
            if s.get("status") == "pending":
                return i

        return None

    def _emit_plan_steps(self) -> None:
        """推送 plan_steps 状态到前端。"""
        self._emit_log(
            "Planner",
            "plan_steps",
            json.dumps(self.state.plan_steps, ensure_ascii=False),
        )

    # ── Reflection 闭环辅助方法 ──────────────────────────

    def _should_reflect(self, iteration: int, had_new_info: bool) -> bool:
        """是否该在这一轮触发反思。

        - 提取到新有效信息 → 立即反思（最有依据）
        - 否则距上次反思已过 REFLECT_INTERVAL 轮 → 兜底反思
        """
        if had_new_info:
            return True
        return (iteration - self._last_reflect_iteration) >= REFLECT_INTERVAL

    async def _reflection_step(
        self, task: str, conversation_history: list[dict[str, Any]]
    ) -> bool:
        """执行一次反思闭环：评估 → 更新状态 → 决定完成或注入下一步指导。

        返回 True 表示任务完成（应结束循环），False 表示继续执行。
        """
        self._reflection_count += 1
        self._emit_log("Reflection", "评估任务完成度...")

        try:
            evaluation = await self.reflection.evaluate(
                task,
                self.state.extracted_info,
                self.state.visited_pages,
                self.state.task_state or None,
            )
        except Exception as e:
            self._emit_log("Reflection", "评估失败", str(e))
            return False

        # 更新任务状态 + 推送结构化日志
        self._update_task_state(evaluation)
        self._emit_reflection(evaluation)

        # ── Human-in-the-Loop：暂停，等待用户决策 ──
        user_decision = await self._wait_for_user_decision(evaluation)
        if user_decision == "stop":
            self._emit_log("User", "用户决定结束任务", "基于当前信息生成报告")
            effective = self._count_effective_info()
            await self._produce_report(
                task,
                f"用户决定结束任务。当前完成度"
                f" {evaluation.get('score', 0)}%，"
                f"以下是基于已收集信息的报告。",
                status="done" if effective > 0 else "failed",
                wrap_partial=(effective == 0),
                info_count=effective,
            )
            return True

        # 用户选择继续 → 按原逻辑执行
        if evaluation.get("success"):
            # 反思判定完成 → 生成报告，结束循环
            agent_summary = evaluation.get("reason", "反思判定信息已足够完成任务。")
            self._emit_log(
                "Reflection",
                "任务完成",
                f"完成度 {evaluation.get('score', 0)}% · {agent_summary[:100]}",
            )
            await self._produce_report(task, agent_summary, status="done")
            return True

        # 未完成 → 重置连续失败计数若有新进展，否则累计
        # （这里统一累计，由安全阀兜底）
        self._reflection_failures += 1
        next_action = evaluation.get("next_action")

        if next_action:
            guidance = self._build_guidance(evaluation)
            conversation_history.append({"role": "user", "content": guidance})
            self._emit_log(
                "Reflection",
                "调整计划",
                f"下一步：{Reflection.format_next_action(next_action)}",
            )
        else:
            self._emit_log(
                "Reflection",
                "未给出下一步动作",
                evaluation.get("reason", ""),
            )

        # 安全阀：连续未完成次数达上限 → 强制出报告，结束循环
        if self._reflection_failures >= MAX_REFLECTION_FAILURES:
            missing_desc = "、".join(evaluation.get("missing", [])) or "关键信息仍不足"
            self._emit_log(
                "Reflection",
                "停止反思",
                f"连续 {MAX_REFLECTION_FAILURES} 次未完成"
                f"（{missing_desc}），基于已有信息出报告",
            )
            effective = self._count_effective_info()
            await self._produce_report(
                task,
                f"Agent 经过 {self._reflection_count} 次反思后生成报告。",
                status="done" if effective > 0 else "failed",
                wrap_partial=(effective == 0),
                info_count=effective,
            )
            return True

        return False

    async def _wait_for_user_decision(self, evaluation: dict[str, Any]) -> str:
        """暂停执行，等待用户通过前端做出决策。

        返回 "continue" 或 "stop"。
        如果 120 秒内无响应，自动继续（超时保护）。
        """
        if self._decision_callback:
            self._decision_callback(evaluation)

        if not self._decision_queue:
            # 没有决策通道 → 默认继续（向后兼容）
            return "continue"

        self._emit_log("System", "等待用户决策...", "请选择：继续执行 或 结束任务")

        try:
            decision = await asyncio.wait_for(self._decision_queue.get(), timeout=120)
            return decision
        except asyncio.TimeoutError:
            self._emit_log("System", "用户决策超时", "120秒无响应，自动继续执行")
            return "continue"

    def _emit_reflection(self, evaluation: dict[str, Any]) -> None:
        """推送结构化反思日志（前端据此展示完成度/发现问题/调整计划）。"""
        score = evaluation.get("score", 0)
        reason = evaluation.get("reason", "")
        missing = evaluation.get("missing", [])
        next_action = evaluation.get("next_action")

        # 结构化 payload，前端据此渲染独立的紫色反思节点
        payload = {
            "score": score,
            "reason": reason,
            "missing": missing,
            "next_action": (
                Reflection.format_next_action(next_action) if next_action else None
            ),
            "success": evaluation.get("success", False),
        }
        self._emit_log(
            "Reflection",
            "反思结果",
            json.dumps(payload, ensure_ascii=False),
        )

    def _build_guidance(self, evaluation: dict[str, Any]) -> str:
        """把反思结果转成给 LLM 的下一步指令（注入对话历史，驱动再执行）。"""
        reason = evaluation.get("reason", "")
        missing = evaluation.get("missing", [])
        next_action = evaluation.get("next_action") or {}
        t = next_action.get("type", "")

        lines = ["[Reflection 反馈] 当前信息仍不足以完成任务。"]
        if reason:
            lines.append(f"原因：{reason}")
        if missing:
            lines.append("仍缺少：" + "、".join(missing))

        # 把 next_action 翻译成明确指令
        if t == "search":
            lines.append(f'请立即执行搜索：query="{next_action.get("query", "")}"')
        elif t == "open_page":
            lines.append(f"请立即打开页面：{next_action.get('url', '')}")
        elif t == "get_text":
            lines.append("请立即获取当前页面的文本内容。")
        elif t == "click":
            lines.append(f'请立即点击文字为 "{next_action.get("text", "")}" 的元素。')
        elif t == "scroll":
            lines.append(f"请立即向 {next_action.get('direction', 'down')} 滚动页面。")
        elif t == "type":
            _sel = next_action.get("selector", "")
            _val = next_action.get("value", "")
            lines.append(f'请在 "{_sel}" 输入 "{_val}"。')
        elif t == "finish":
            lines.append(f"请结束任务：{next_action.get('summary', '')}")

        lines.append("请基于以上指导决定下一步工具调用，不要重复已做过的操作。")
        return "\n".join(lines)

    def _update_task_state(self, evaluation: dict[str, Any]) -> None:
        """根据反思结果更新任务状态（goal/completed_steps/missing/next_action/score）。"""
        ts = self.state.task_state or {}
        if not ts:
            ts = {
                "goal": self.state.task,
                "completed_steps": [],
                "missing": [],
                "next_action": None,
                "score": 0,
            }

        completed: list[str] = []
        if self.state.visited_pages:
            completed.append(f"已访问 {len(self.state.visited_pages)} 个页面")
        effective = self._count_effective_info()
        if effective:
            completed.append(f"已提取 {effective} 条有效信息")

        ts["completed_steps"] = completed
        ts["missing"] = evaluation.get("missing", [])
        ts["next_action"] = evaluation.get("next_action")
        ts["score"] = evaluation.get("score", 0)
        if evaluation.get("success"):
            ts["next_action"] = None
        self.state.task_state = ts

    async def _produce_report(
        self,
        task: str,
        agent_summary: str,
        status: str,
        wrap_partial: bool = False,
        info_count: int = 0,
    ) -> None:
        """生成最终报告并写入 state（Analyst 失败则回退到摘要）。"""
        self.state.status = status
        if self.analyst:
            self._emit_log("Analyst", "正在生成结构化报告...")
            try:
                report = await self.analyst.generate_report(
                    task=task,
                    extracted_info=self.state.extracted_info,
                    visited_pages=self.state.visited_pages,
                    agent_summary=agent_summary,
                )
                if wrap_partial:
                    report = self._wrap_partial_report(report, info_count)
                self.state.final_report = report
                self._emit_log("Analyst", "报告生成完成", f"{len(report)} 字符")
            except Exception as e:
                self._emit_log("Analyst", "报告生成失败，使用摘要", str(e))
                self.state.final_report = agent_summary
        else:
            self.state.final_report = agent_summary

    # ── 原有辅助方法 ─────────────────────────────────────

    def _format_observation(self, result: dict[str, Any]) -> str:
        """把工具返回结果格式化为 LLM 能理解的观察文本。"""
        if result["status"] == "success":
            data = result.get("data", {})
            # get_text 返回页面内容
            if "text" in data:
                text = data["text"][:3000]  # 截断，防止对话历史过长
                _t = data.get("title", "")
                _u = data.get("url", "")
                return f"页面标题: {_t}\nURL: {_u}\n页面内容:\n{text}"
            # search 返回搜索结果
            if "results" in data:
                results = data["results"]
                lines = [f"找到 {len(results)} 条结果:"]
                for r in results:
                    snippet = r.get("snippet", "")
                    snippet_part = f" — {snippet[:150]}" if snippet else ""
                    lines.append(f"- {r['title']}: {r['url']}{snippet_part}")
                return "\n".join(lines)
            # 其他成功结果
            return result.get("message", "Success")
        elif result["status"] == "ambiguous":
            return f"找到多个匹配元素: {result.get('data', {}).get('candidates', [])}"
        else:
            return f"失败: {result.get('message', 'Unknown error')}"

    def _count_effective_info(self) -> int:
        """统计有效信息条数（搜索结果、提取信息都算有效）。"""
        count = 0
        for info in self.state.extracted_info:
            # 搜索结果：有结果条目就算有效
            if info.get("_type") == "search_results":
                results = info.get("results", [])
                if results:
                    count += 1
                continue
            # 提取信息：有非元数据字段就算有效
            keys = [k for k in info.keys() if not k.startswith("_")]
            if keys:
                count += 1
        return count

    def _generate_failure_report(self, task: str, reason: str) -> str:
        """生成「任务未能完成」的报告。"""
        lines = [
            "# ❌ 任务未能完成",
            "",
            f"**任务**：{task}",
            "",
            "## 原因",
            reason,
            "",
            "## 建议",
            "- 尝试用更具体的关键词描述任务",
            "- 确认所需信息是否公开可获取",
            "- 如果涉及特定网站，检查该网站是否需要登录",
            "",
        ]
        if self.state.visited_pages:
            lines.append("## 已尝试访问的页面")
            for url in self.state.visited_pages:
                lines.append(f"- {url}")
            lines.append("")
        return "\n".join(lines)

    def _wrap_partial_report(self, report: str, info_count: int) -> str:
        """在报告顶部加上「信息有限」提示（仅当完全没收集到信息时触发）。"""
        if info_count == 0:
            banner = (
                "> ℹ️ **本次任务未能获取到有效信息。**\n"
                "> 建议：尝试用更具体的关键词，或确认目标信息是否公开可获取。\n"
            )
        else:
            banner = (
                f"> ℹ️ **报告基于 {info_count} 条信息生成**\n"
                "> 部分内容可能不完整，建议用更具体的描述重新执行。\n"
            )
        return f"{banner}\n{report}"
