"""
pytest 全局配置
- 将项目根目录添加到 sys.path，使测试中可以 import 项目模块
- 提供公共 fixture
"""

import sys
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path，确保 import store / settings_store 等模块可用
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """返回一个临时 SQLite 数据库路径，用于 TaskStore 测试。"""
    return tmp_path / "test_tasks.db"


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """返回一个临时 JSON 配置文件路径，用于 SettingsStore 测试。"""
    return tmp_path / "test_config.json"
