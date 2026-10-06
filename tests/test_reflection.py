"""Reflection 单元测试：验证输出规范化（不依赖真实 LLM）。"""

import pytest

from agent.reflection import Reflection


def make_reflection():
    """构造不依赖 LLM 的 Reflection 实例（_normalize 是纯逻辑）。"""
    return Reflection(llm_client=None)


class TestReflectionNormalize:
    def test_normalizes_success(self):
        """success=true 时 next_action 应强制为 None。"""
        r = make_reflection()
        result = r._normalize({
            "success": True,
            "score": "85",          # 字符串应转为 int
            "reason": "信息已足够",
            "missing": [],
            "next_action": {"type": "search", "query": "x"},  # 应被清掉
        })
        assert result["success"] is True
        assert result["score"] == 85
        assert result["next_action"] is None

    def test_normalizes_score_clamping(self):
        """score 应被夹在 0-100。"""
        r = make_reflection()
        assert r._normalize({"score": 150})["score"] == 100
        assert r._normalize({"score": -10})["score"] == 0
        assert r._normalize({"score": "abc"})["score"] == 0

    def test_normalizes_missing_to_list(self):
        """missing 非列表时应转为列表。"""
        r = make_reflection()
        result = r._normalize({"missing": "缺来源"})
        assert result["missing"] == ["缺来源"]

    def test_normalizes_invalid_next_action(self):
        """next_action 缺 type 时应置 None。"""
        r = make_reflection()
        result = r._normalize({
            "success": False,
            "next_action": {"query": "没有type字段"},
        })
        assert result["next_action"] is None

    def test_keeps_valid_next_action(self):
        """未完成时合法的 next_action 应保留。"""
        r = make_reflection()
        result = r._normalize({
            "success": False,
            "next_action": {"type": "search", "query": "Python 3.14"},
        })
        assert result["next_action"]["type"] == "search"
        assert result["next_action"]["query"] == "Python 3.14"


class TestFormatNextAction:
    def test_none_returns_empty(self):
        assert Reflection.format_next_action(None) == "无"

    def test_search(self):
        s = Reflection.format_next_action({"type": "search", "query": "AI 就业"})
        assert "AI 就业" in s

    def test_open_page(self):
        s = Reflection.format_next_action({"type": "open_page", "url": "https://a.b"})
        assert "https://a.b" in s

    def test_finish(self):
        s = Reflection.format_next_action({"type": "finish", "summary": "任务完成"})
        assert "任务完成" in s

    def test_unknown_type_falls_back_to_json(self):
        s = Reflection.format_next_action({"type": "weird", "x": 1})
        assert "weird" in s
