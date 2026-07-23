"""配置持久化。"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QLocale, QStandardPaths

logger = logging.getLogger(__name__)


@dataclass
class WindowGeometry:
    """窗口位置与尺寸。"""

    x: int = -1
    y: int = -1
    width: int = 128
    height: int = 480

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WindowGeometry":
        if not data:
            return cls()
        return cls(
            x=data.get("x", -1),
            y=data.get("y", -1),
            width=data.get("width", 128),
            height=data.get("height", 480),
        )


@dataclass
class AppConfig:
    """应用配置。"""

    edge: str = "bottom"  # top, bottom, left, right
    auto_hide: bool = False
    show_clock: bool = True
    multi_monitor: bool = False
    taskbar_scale: float = 1.0
    language: str = "auto"  # auto, zh_CN, en_US
    geometry: WindowGeometry = field(default_factory=WindowGeometry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge": self.edge,
            "auto_hide": self.auto_hide,
            "show_clock": self.show_clock,
            "multi_monitor": self.multi_monitor,
            "taskbar_scale": self.taskbar_scale,
            "language": self.language,
            "geometry": self.geometry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            edge=data.get("edge", "bottom"),
            auto_hide=data.get("auto_hide", False),
            show_clock=data.get("show_clock", True),
            multi_monitor=data.get("multi_monitor", False),
            taskbar_scale=data.get("taskbar_scale", 1.0),
            language=data.get("language", "auto"),
            geometry=WindowGeometry.from_dict(data.get("geometry")),
        )

    @staticmethod
    def default_path() -> Path:
        """返回默认配置文件路径（位于应用数据目录）。"""
        config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def save(self, path: Path | str | None = None) -> None:
        """保存配置到 JSON。"""
        target = Path(path) if path else self.default_path()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("保存配置失败: %s", target)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "AppConfig":
        """从 JSON 加载配置；若不存在或解析失败则返回默认配置。"""
        target = Path(path) if path else cls.default_path()
        if not target.exists():
            return cls()
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            logger.exception("加载配置失败: %s", target)
            return cls()

    def effective_language(self) -> str:
        """返回实际生效的语言代码。"""
        if self.language and self.language != "auto":
            return self.language
        locale = QLocale.system().name()  # 例如 "zh_CN" / "en_US"
        return "zh_CN" if locale.startswith("zh") else "en_US"
