"""
Agent State - 状态中心
所有 Agent 共用一个状态，保存完整上下文。

Agent 不是简单的"输入→输出"，而是：
    思考 → 行动 → 观察 → 继续思考
必须保存上下文。
"""

from typing import Any
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """共享状态，在 LangGraph 各 Node 之间流转。"""

    # 用户原始任务
    task: str = ""

    # Planner 拆解出的步骤列表（原始，不含 status）
    plan: list[dict[str, Any]] = Field(default_factory=list)

    # 带状态的计划步骤（Planner 状态驱动用）
    # 每个 step: {"name": str, "type": str, "goal": str, "status": "pending"|"running"|"done"|"skipped", ...}
    plan_steps: list[dict[str, Any]] = Field(default_factory=list)

    # 当前执行的步骤索引（-1 表示未开始）
    current_step_index: int = -1

    # 当前执行的步骤
    current_step: str = ""

    # 已访问的页面 URL
    visited_pages: list[str] = Field(default_factory=list)

    # 提取出的结构化信息
    extracted_info: list[dict[str, Any]] = Field(default_factory=list)

    # 最终报告
    final_report: str = ""

    # 执行日志（供前端 WebSocket 实时展示）
    logs: list[dict[str, str]] = Field(default_factory=list)

    # 当前状态: idle / planning / browsing / parsing / analyzing / done / error
    status: str = "idle"

    # 任务执行耗时（秒）
    duration_seconds: int = 0

    # 任务状态（Reflection 闭环用）：goal / completed_steps / missing / next_action / score
    task_state: dict[str, Any] = Field(default_factory=dict)

    def add_log(self, agent: str, action: str, detail: str = "") -> None:
        """添加一条执行日志。"""
        from datetime import datetime  # noqa: deferred to avoid circular import at module level
        self.logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "agent": agent,
            "action": action,
            "detail": detail,
        })

    # ── Planner 状态驱动方法 ──

    def init_plan_steps(self, steps: list[dict[str, Any]]) -> None:
        """用 Planner 输出的步骤初始化 plan_steps（深拷贝，避免引用污染）。"""
        import copy
        self.plan_steps = [copy.deepcopy(s) for s in steps]
        self.current_step_index = -1

    def start_step(self, index: int) -> dict[str, Any] | None:
        """将第 index 个 step 标记为 running，返回该 step（或 None）。"""
        if 0 <= index < len(self.plan_steps):
            # 把之前的 running 步骤标记为 done（安全兜底）
            for s in self.plan_steps:
                if s.get("status") == "running":
                    s["status"] = "done"
            self.plan_steps[index]["status"] = "running"
            self.current_step_index = index
            return self.plan_steps[index]
        return None

    def complete_step(self, index: int) -> dict[str, Any] | None:
        """将第 index 个 step 标记为 done。"""
        if 0 <= index < len(self.plan_steps):
            self.plan_steps[index]["status"] = "done"
            return self.plan_steps[index]
        return None

    def skip_step(self, index: int) -> dict[str, Any] | None:
        """将第 index 个 step 标记为 skipped。"""
        if 0 <= index < len(self.plan_steps):
            self.plan_steps[index]["status"] = "skipped"
            return self.plan_steps[index]
        return None

    def get_next_pending_step(self) -> tuple[int, dict[str, Any]] | None:
        """找到下一个 pending 状态的 step，返回 (index, step)。"""
        for i, s in enumerate(self.plan_steps):
            if s.get("status") == "pending":
                return i, s
        return None

    def to_store_dict(self) -> dict[str, Any]:
        """导出 store.save_task() 所需的参数字典（消除 main.py 中的重复展开）。"""
        return {
            "task": self.task,
            "status": self.status,
            "plan": self.plan,
            "visited_pages": self.visited_pages,
            "extracted_info": self.extracted_info,
            "final_report": self.final_report,
            "logs": self.logs,
            "duration_seconds": self.duration_seconds,
        }

    def get_plan_summary(self) -> str:
        """生成计划摘要（供 LLM 上下文压缩用）。"""
        if not self.plan_steps:
            return "无计划"
        lines = []
        for i, s in enumerate(self.plan_steps):
            icon = {"done": "✓", "running": "▶", "pending": "○", "skipped": "✗"}.get(s.get("status", ""), "?")
            lines.append(f"{icon} [{i+1}] {s.get('name', '?')}: {s.get('status', '?')}")
        done = sum(1 for s in self.plan_steps if s.get("status") == "done")
        total = len(self.plan_steps)
        lines.append(f"进度: {done}/{total}")
        return "\n".join(lines)
