"""store 单元测试：验证 parent_id 串联与 update_report 回写（临时 DB）。"""

import os
import tempfile
from pathlib import Path

import pytest

from store import TaskStore


@pytest.fixture()
def store(tmp_path):
    """每个测试独立临时数据库。"""
    return TaskStore(db_path=tmp_path / "test_tasks.db")


def save(store, task="任务", **kw):
    """便捷保存。"""
    return store.save_task(
        task=task,
        status=kw.get("status", "done"),
        plan=kw.get("plan", []),
        visited_pages=kw.get("visited_pages", []),
        extracted_info=kw.get("extracted_info", []),
        final_report=kw.get("final_report", "报告"),
        logs=kw.get("logs", []),
        duration_seconds=kw.get("duration_seconds", 0),
        parent_id=kw.get("parent_id"),
    )


class TestTaskStore:
    def test_save_and_get_roundtrip(self, store):
        """保存后能按 id 取回完整记录。"""
        tid = save(store, task="对比 GPT 与 Claude", final_report="结论：各有优势")
        rec = store.get_task(tid)
        assert rec["task"] == "对比 GPT 与 Claude"
        assert rec["final_report"] == "结论：各有优势"

    def test_save_returns_incrementing_ids(self, store):
        """每次保存返回递增 id。"""
        id1 = save(store)
        id2 = save(store)
        assert id2 == id1 + 1

    def test_parent_id_links_followup(self, store):
        """追问轮应通过 parent_id 关联父任务。"""
        parent = save(store, task="原始任务")
        child = save(store, task="追问", parent_id=parent)
        assert store.get_task(child)["parent_id"] == parent

    def test_default_parent_id_is_none(self, store):
        """首轮任务 parent_id 应为 None。"""
        tid = save(store)
        assert store.get_task(tid)["parent_id"] is None

    def test_update_report_overwrites(self, store):
        """update_report 应回写 final_report。"""
        tid = save(store, final_report="旧报告")
        ok = store.update_report(tid, "重生成的报告")
        assert ok is True
        assert store.get_task(tid)["final_report"] == "重生成的报告"

    def test_update_report_missing_task_returns_false(self, store):
        """不存在的任务 update_report 应返回 False 而非崩溃。"""
        assert store.update_report(99999, "x") is False

    def test_list_tasks_sorted_desc(self, store):
        """list_tasks 应按创建时间倒序。"""
        save(store, task="A")
        save(store, task="B")
        tasks = store.list_tasks()
        assert tasks[0]["task"] == "B"
        assert tasks[1]["task"] == "A"

    def test_count_tasks(self, store):
        """count_tasks 返回总数。"""
        save(store)
        save(store)
        assert store.count_tasks() == 2

    def test_extracted_info_json_roundtrip(self, store):
        """extracted_info 复杂结构保存/取回应保持一致。"""
        info = [{"_type": "search_results", "results": [{"title": "t", "url": "u"}]}]
        tid = save(store, extracted_info=info)
        assert store.get_task(tid)["extracted_info"] == info
