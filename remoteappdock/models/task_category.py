"""任务分类。"""

from enum import Enum


class TaskCategory(Enum):
    """任务按钮分类。"""

    PINNED = "pinned"
    RUNNING = "running"
    COMBINED = "combined"
