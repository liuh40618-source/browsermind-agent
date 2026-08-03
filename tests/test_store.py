"""
TaskStore 单元测试

使用 tmp_path 创建临时 SQLite 数据库，测试所有 CRUD 操作，
不依赖任何外部服务或真实数据。
"""

from pathlib import Path

import pytest

from store import TaskStore

# ── Fixture ──────────────────────────────────────────────


@pytest.fixture
def store(tmp_path: Path) -> TaskStore:
    """创建一个使用临时数据库的 TaskStore 实例。"""
    db_path = tmp_path / "test_tasks.db"
    return TaskStore(db_path=db_path)


def _make_task(task: str = "搜索测试", status: str = "done") -> dict:
    """构造一个合法的任务参数字典，减少重复代码。"""
    return dict(
        task=task,
        status=status,
        plan=[{"name": "step1", "type": "search"}],
        visited_pages=["https://example.com"],
        extracted_info=[{"key": "info", "value": "data"}],
        final_report="这是最终报告",
        logs=[{"time": "12:00:00", "agent": "test", "action": "run"}],
        duration_seconds=42,
    )


# ── save_task ────────────────────────────────────────────


class TestSaveTask:
    """save_task 相关测试。"""

    def test_save_task_returns_valid_id(self, store: TaskStore):
        """save_task 应返回一个正整数 ID。"""
        task_id = store.save_task(**_make_task())
        assert isinstance(task_id, int)
        assert task_id > 0

    def test_save_multiple_tasks_returns_incrementing_ids(self, store: TaskStore):
        """连续保存多条任务，ID 应递增。"""
        id1 = store.save_task(**_make_task(task="任务1"))
        id2 = store.save_task(**_make_task(task="任务2"))
        assert id2 > id1


# ── get_task ─────────────────────────────────────────────


class TestGetTask:
    """get_task 相关测试。"""

    def test_get_task_returns_correct_data(self, store: TaskStore):
        """get_task 应返回与保存时一致的数据。"""
        params = _make_task(task="查找信息")
        task_id = store.save_task(**params)

        result = store.get_task(task_id)
        assert result is not None
        assert result["task"] == "查找信息"
        assert result["status"] == "done"
        assert result["final_report"] == "这是最终报告"
        assert result["duration_seconds"] == 42

    def test_get_task_nonexistent_id_returns_none(self, store: TaskStore):
        """查询不存在的 ID 应返回 None。"""
        result = store.get_task(9999)
        assert result is None

    def test_get_task_json_fields_parsed(self, store: TaskStore):
        """JSON 字段（plan, visited_pages 等）应被解析为 Python 对象。"""
        params = _make_task()
        task_id = store.save_task(**params)

        result = store.get_task(task_id)
        assert isinstance(result["plan"], list)
        assert isinstance(result["visited_pages"], list)
        assert isinstance(result["extracted_info"], list)
        assert isinstance(result["logs"], list)
        # 内容也应一致
        assert result["plan"] == [{"name": "step1", "type": "search"}]
        assert result["visited_pages"] == ["https://example.com"]


# ── list_tasks ───────────────────────────────────────────


class TestListTasks:
    """list_tasks 分页与排序测试。"""

    def test_list_tasks_empty(self, store: TaskStore):
        """空数据库应返回空列表。"""
        assert store.list_tasks() == []

    def test_list_tasks_returns_all(self, store: TaskStore):
        """保存 3 条任务后，list_tasks 应返回 3 条。"""
        for i in range(3):
            store.save_task(**_make_task(task=f"任务{i}"))
        tasks = store.list_tasks()
        assert len(tasks) == 3

    def test_list_tasks_descending_order(self, store: TaskStore):
        """list_tasks 应按 ID 倒序返回（最新的在前）。"""
        id1 = store.save_task(**_make_task(task="先保存"))
        id2 = store.save_task(**_make_task(task="后保存"))
        tasks = store.list_tasks()
        assert tasks[0]["id"] == id2
        assert tasks[1]["id"] == id1

    def test_list_tasks_pagination_limit(self, store: TaskStore):
        """limit 参数应限制返回数量。"""
        for i in range(5):
            store.save_task(**_make_task(task=f"任务{i}"))
        tasks = store.list_tasks(limit=2)
        assert len(tasks) == 2

    def test_list_tasks_pagination_offset(self, store: TaskStore):
        """offset 参数应跳过前面的记录。"""
        ids = []
        for i in range(5):
            ids.append(store.save_task(**_make_task(task=f"任务{i}")))
        tasks = store.list_tasks(limit=2, offset=2)
        assert len(tasks) == 2
        # offset=2 意味着跳过最新的 2 条，返回第 3、4 新的
        assert tasks[0]["id"] == ids[-3]  # 第3新
        assert tasks[1]["id"] == ids[-4]  # 第4新


# ── count_tasks ──────────────────────────────────────────


class TestCountTasks:
    """count_tasks 相关测试。"""

    def test_count_tasks_empty(self, store: TaskStore):
        """空数据库计数应为 0。"""
        assert store.count_tasks() == 0

    def test_count_tasks_after_save(self, store: TaskStore):
        """保存后计数应正确。"""
        for i in range(3):
            store.save_task(**_make_task(task=f"任务{i}"))
        assert store.count_tasks() == 3

    def test_count_tasks_after_delete(self, store: TaskStore):
        """删除后计数应减少。"""
        tid = store.save_task(**_make_task())
        assert store.count_tasks() == 1
        store.delete_task(tid)
        assert store.count_tasks() == 0


# ── delete_task ──────────────────────────────────────────


class TestDeleteTask:
    """delete_task 相关测试。"""

    def test_delete_existing_task_returns_true(self, store: TaskStore):
        """删除存在的任务应返回 True。"""
        tid = store.save_task(**_make_task())
        assert store.delete_task(tid) is True

    def test_delete_nonexistent_task_returns_false(self, store: TaskStore):
        """删除不存在的任务应返回 False。"""
        assert store.delete_task(9999) is False

    def test_deleted_task_not_retrievable(self, store: TaskStore):
        """删除后 get_task 应返回 None。"""
        tid = store.save_task(**_make_task())
        store.delete_task(tid)
        assert store.get_task(tid) is None


# ── clear_all_tasks ──────────────────────────────────────


class TestClearAllTasks:
    """clear_all_tasks 相关测试。"""

    def test_clear_all_returns_deleted_count(self, store: TaskStore):
        """clear_all_tasks 应返回被删除的行数。"""
        for i in range(3):
            store.save_task(**_make_task(task=f"任务{i}"))
        deleted = store.clear_all_tasks()
        assert deleted == 3

    def test_clear_all_empties_database(self, store: TaskStore):
        """清空后数据库应为空。"""
        for i in range(3):
            store.save_task(**_make_task(task=f"任务{i}"))
        store.clear_all_tasks()
        assert store.count_tasks() == 0
        assert store.list_tasks() == []

    def test_clear_all_on_empty(self, store: TaskStore):
        """空数据库调用 clear_all_tasks 应返回 0。"""
        assert store.clear_all_tasks() == 0
