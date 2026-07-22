"""配置持久化。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    """应用配置。"""

    edge: str = "bottom"  # top, bottom, left, right
    auto_hide: bool = False
    show_clock: bool = True
    multi_monitor: bool = False
    taskbar_scale: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge": self.edge,
            "auto_hide": self.auto_hide,
            "show_clock": self.show_clock,
            "multi_monitor": self.multi_monitor,
            "taskbar_scale": self.taskbar_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            edge=data.get("edge", "bottom"),
            auto_hide=data.get("auto_hide", False),
            show_clock=data.get("show_clock", True),
            multi_monitor=data.get("multi_monitor", False),
            taskbar_scale=data.get("taskbar_scale", 1.0),
        )

    def save(self, path: Path | None = None) -> None:
        """保存配置到 JSON。"""
        raise NotImplementedError

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        """从 JSON 加载配置。"""
        raise NotImplementedError
