"""
Task Store - 任务历史存储

用 SQLite 保存每次任务执行的完整记录：
- 任务内容
- 执行状态
- 计划步骤
- 访问页面
- 提取信息
- 最终报告
- 执行日志
- 时间戳
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Any


DB_PATH = Path(__file__).resolve().parent / "data" / "tasks.db"


class TaskStore:
    """任务历史存储（SQLite）。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表。"""
        with sqlite3.connect(self.db_path) as conn:
            # 启用 WAL 模式，提升并发读写性能
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plan TEXT,
                    visited_pages TEXT,
                    extracted_info TEXT,
                    final_report TEXT,
                    logs TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    parent_id INTEGER
                )
            """)
            # 迁移：旧表没有 duration_seconds 列时自动添加
            try:
                conn.execute("SELECT duration_seconds FROM tasks LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE tasks ADD COLUMN duration_seconds INTEGER DEFAULT 0")
            # 迁移：旧表没有 parent_id 列时自动添加（追问轮的父子关联）
            try:
                conn.execute("SELECT parent_id FROM tasks LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE tasks ADD COLUMN parent_id INTEGER")
            conn.commit()

    def save_task(
        self,
        task: str,
        status: str,
        plan: list[dict],
        visited_pages: list[str],
        extracted_info: list[dict],
        final_report: str,
        logs: list[dict],
        duration_seconds: int = 0,
        parent_id: int | None = None,
    ) -> int:
        """保存任务记录，返回任务 ID。

        parent_id: 若是追问轮，传入上一轮任务的 ID，形成父子关联。
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (task, status, plan, visited_pages, extracted_info, final_report, logs, created_at, completed_at, duration_seconds, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task,
                    status,
                    json.dumps(plan, ensure_ascii=False),
                    json.dumps(visited_pages, ensure_ascii=False),
                    json.dumps(extracted_info, ensure_ascii=False),
                    final_report,
                    json.dumps(logs, ensure_ascii=False),
                    now,
                    now,
                    duration_seconds,
                    parent_id,
                ),
            )
            conn.commit()
            last_id = cursor.lastrowid
            if last_id is None:
                raise RuntimeError("SQLite 未返回插入 ID")
            return last_id

    def update_report(self, task_id: int, final_report: str) -> bool:
        """更新任务的最终报告（轻量重生成场景：复用已抓信息，不重跑 Agent）。"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE tasks SET final_report = ?, completed_at = ? WHERE id = ?",
                (final_report, now, task_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        """获取单个任务详情。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_tasks(
        self, limit: int = 50, offset: int = 0, q: str = "", status: str = "",
        summary: bool = False,
    ) -> list[dict[str, Any]]:
        """获取任务列表（按时间倒序）。"""
        where, params = self._filters(q, status)
        columns = (
            "id, task, status, created_at, duration_seconds, parent_id, "
            "substr(final_report, 1, 240) AS report_excerpt"
        ) if summary else "*"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT {columns} FROM tasks {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
            if summary:
                return [dict(row) for row in rows]
            return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _filters(q: str, status: str) -> tuple[str, list[str]]:
        clauses, params = [], []
        if q:
            clauses.append("(instr(lower(task), lower(?)) > 0 OR instr(lower(final_report), lower(?)) > 0)")
            params.extend([q, q])
        if status:
            clauses.append("status = ?")
            params.append(status)
        return ("WHERE " + " AND ".join(clauses) if clauses else ""), params

    def count_tasks(self, q: str = "", status: str = "") -> int:
        """获取任务总数。"""
        where, params = self._filters(q, status)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM tasks {where}", params).fetchone()
            return row[0]

    def delete_task(self, task_id: int) -> bool:
        """删除任务记录。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all_tasks(self) -> int:
        """清空所有任务记录，返回删除行数。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks")
            conn.commit()
            return cursor.rowcount

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """把数据库行转为字典，JSON 字段自动解析。"""
        d = dict(row)
        for field in ("plan", "visited_pages", "extracted_info", "logs"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
            else:
                d[field] = []
        return d


# 全局单例
store = TaskStore()
