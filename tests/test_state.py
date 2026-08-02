"""
AgentState 单元测试

测试状态模型的初始值、方法行为以及 to_store_dict 导出，
不依赖任何外部服务。
"""

import pytest
from agent.state import AgentState


# ── 初始状态 ─────────────────────────────────────────────

class TestAgentStateDefaults:
    """AgentState 默认初始值测试。"""

    def test_default_task_is_empty(self):
        """task 默认值应为空字符串。"""
        state = AgentState()
        assert state.task == ""

    def test_default_plan_is_empty(self):
        """plan 默认值应为空列表。"""
        state = AgentState()
        assert state.plan == []

    def test_default_plan_steps_is_empty(self):
        """plan_steps 默认值应为空列表。"""
        state = AgentState()
        assert state.plan_steps == []

    def test_default_current_step_index(self):
        """current_step_index 默认值应为 -1。"""
        state = AgentState()
        assert state.current_step_index == -1

    def test_default_current_step_is_empty(self):
        """current_step 默认值应为空字符串。"""
        state = AgentState()
        assert state.current_step == ""

    def test_default_visited_pages_is_empty(self):
        """visited_pages 默认值应为空列表。"""
        state = AgentState()
        assert state.visited_pages == []

    def test_default_extracted_info_is_empty(self):
        """extracted_info 默认值应为空列表。"""
        state = AgentState()
        assert state.extracted_info == []

    def test_default_final_report_is_empty(self):
        """final_report 默认值应为空字符串。"""
        state = AgentState()
        assert state.final_report == ""

    def test_default_logs_is_empty(self):
        """logs 默认值应为空列表。"""
        state = AgentState()
        assert state.logs == []

    def test_default_status_is_idle(self):
        """status 默认值应为 'idle'。"""
        state = AgentState()
        assert state.status == "idle"

    def test_default_duration_seconds(self):
        """duration_seconds 默认值应为 0。"""
        state = AgentState()
        assert state.duration_seconds == 0

    def test_default_task_state_is_empty(self):
        """task_state 默认值应为空字典。"""
        state = AgentState()
        assert state.task_state == {}


# ── to_store_dict ────────────────────────────────────────

class TestToStoreDict:
    """to_store_dict 方法测试。"""

    def test_to_store_dict_returns_all_required_keys(self):
        """to_store_dict 应返回 save_task 所需的所有 key。"""
        state = AgentState()
        d = state.to_store_dict()
        expected_keys = {
            "task", "status", "plan", "visited_pages",
            "extracted_info", "final_report", "logs", "duration_seconds",
        }
        assert set(d.keys()) == expected_keys

    def test_to_store_dict_values_match_state(self):
        """to_store_dict 的值应与 state 属性一致。"""
        state = AgentState(
            task="搜索AI新闻",
            status="done",
            plan=[{"name": "step1"}],
            visited_pages=["https://example.com"],
            extracted_info=[{"key": "val"}],
            final_report="报告内容",
            logs=[{"time": "12:00"}],
            duration_seconds=60,
        )
        d = state.to_store_dict()
        assert d["task"] == "搜索AI新闻"
        assert d["status"] == "done"
        assert d["plan"] == [{"name": "step1"}]
        assert d["visited_pages"] == ["https://example.com"]
        assert d["extracted_info"] == [{"key": "val"}]
        assert d["final_report"] == "报告内容"
        assert d["logs"] == [{"time": "12:00"}]
        assert d["duration_seconds"] == 60

    def test_to_store_dict_with_defaults(self):
        """默认 state 的 to_store_dict 应返回正确的默认值。"""
        state = AgentState()
        d = state.to_store_dict()
        assert d["task"] == ""
        assert d["status"] == "idle"
        assert d["plan"] == []
        assert d["visited_pages"] == []
        assert d["extracted_info"] == []
        assert d["final_report"] == ""
        assert d["logs"] == []
        assert d["duration_seconds"] == 0


# ── add_log ──────────────────────────────────────────────

class TestAddLog:
    """add_log 方法测试。"""

    def test_add_log_appends_to_logs(self):
        """add_log 应向 logs 列表追加一条记录。"""
        state = AgentState()
        state.add_log("browser", "open_page", "https://example.com")
        assert len(state.logs) == 1
        log = state.logs[0]
        assert log["agent"] == "browser"
        assert log["action"] == "open_page"
        assert log["detail"] == "https://example.com"
        assert "time" in log

    def test_add_multiple_logs(self):
        """多次调用 add_log 应追加多条记录。"""
        state = AgentState()
        state.add_log("planner", "plan")
        state.add_log("browser", "browse")
        state.add_log("analyst", "analyze")
        assert len(state.logs) == 3


# ── plan_steps 状态管理 ──────────────────────────────────

class TestPlanSteps:
    """plan_steps 相关方法测试。"""

    def test_init_plan_steps(self):
        """init_plan_steps 应正确初始化步骤列表。"""
        state = AgentState()
        steps = [
            {"name": "step1", "type": "search", "status": "pending"},
            {"name": "step2", "type": "browse", "status": "pending"},
        ]
        state.init_plan_steps(steps)
        assert len(state.plan_steps) == 2
        assert state.current_step_index == -1

    def test_init_plan_steps_deep_copy(self):
        """init_plan_steps 应深拷贝，修改原始列表不影响 state。"""
        state = AgentState()
        steps = [{"name": "step1", "status": "pending"}]
        state.init_plan_steps(steps)
        steps[0]["name"] = "modified"
        assert state.plan_steps[0]["name"] == "step1"

    def test_start_step(self):
        """start_step 应将指定步骤标记为 running。"""
        state = AgentState()
        state.init_plan_steps([
            {"name": "step1", "status": "pending"},
            {"name": "step2", "status": "pending"},
        ])
        result = state.start_step(0)
        assert result is not None
        assert result["status"] == "running"
        assert state.current_step_index == 0

    def test_start_step_invalid_index(self):
        """start_step 传入越界索引应返回 None。"""
        state = AgentState()
        state.init_plan_steps([{"name": "step1", "status": "pending"}])
        assert state.start_step(5) is None
        assert state.start_step(-1) is None

    def test_complete_step(self):
        """complete_step 应将指定步骤标记为 done。"""
        state = AgentState()
        state.init_plan_steps([{"name": "step1", "status": "running"}])
        result = state.complete_step(0)
        assert result["status"] == "done"

    def test_skip_step(self):
        """skip_step 应将指定步骤标记为 skipped。"""
        state = AgentState()
        state.init_plan_steps([{"name": "step1", "status": "pending"}])
        result = state.skip_step(0)
        assert result["status"] == "skipped"

    def test_get_next_pending_step(self):
        """get_next_pending_step 应返回下一个 pending 步骤。"""
        state = AgentState()
        state.init_plan_steps([
            {"name": "step1", "status": "done"},
            {"name": "step2", "status": "pending"},
            {"name": "step3", "status": "pending"},
        ])
        result = state.get_next_pending_step()
        assert result is not None
        idx, step = result
        assert idx == 1
        assert step["name"] == "step2"

    def test_get_next_pending_step_none(self):
        """没有 pending 步骤时应返回 None。"""
        state = AgentState()
        state.init_plan_steps([
            {"name": "step1", "status": "done"},
            {"name": "step2", "status": "done"},
        ])
        assert state.get_next_pending_step() is None


# ── get_plan_summary ─────────────────────────────────────

class TestGetPlanSummary:
    """get_plan_summary 方法测试。"""

    def test_no_plan_returns_message(self):
        """无计划时应返回 '无计划'。"""
        state = AgentState()
        assert state.get_plan_summary() == "无计划"

    def test_plan_summary_contains_step_names(self):
        """计划摘要应包含步骤名称。"""
        state = AgentState()
        state.init_plan_steps([
            {"name": "搜索信息", "status": "done"},
            {"name": "分析数据", "status": "pending"},
        ])
        summary = state.get_plan_summary()
        assert "搜索信息" in summary
        assert "分析数据" in summary
        assert "1/2" in summary  # 进度
