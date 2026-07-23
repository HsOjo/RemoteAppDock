"""通用辅助函数。"""

import sys
from pathlib import Path


def get_app_root() -> Path:
    """返回应用根目录（兼容开发环境和 PyInstaller 打包环境）。"""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def get_app_icon_path() -> Path:
    """返回应用图标文件路径。"""
    return get_app_root() / "assets" / "app-icon.ico"
