"""应用版本信息。

版本以 pyproject.toml 中的 project.version 为准。运行时优先读取打包或源码目录
中的 pyproject.toml，否则回退到安装包元数据。
"""

import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _read_version_from_pyproject(path: Path) -> str | None:
    """从 pyproject.toml 读取 project.version。"""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version")
    except Exception:
        return None


def _get_version() -> str:
    """返回应用版本号。"""
    # PyInstaller 打包环境：pyproject.toml 位于 sys._MEIPASS 根目录
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            version_from_bundle = _read_version_from_pyproject(Path(meipass) / "pyproject.toml")
            if version_from_bundle:
                return version_from_bundle

    # 开发环境：pyproject.toml 位于 remoteappdock 包的上级目录
    dev_pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if dev_pyproject.exists():
        version_from_dev = _read_version_from_pyproject(dev_pyproject)
        if version_from_dev:
            return version_from_dev

    # 回退到安装包元数据（仍由 pyproject.toml 生成）
    try:
        return version("remoteappdock")
    except PackageNotFoundError:
        pass

    return "0.0.0"  # 回退版本：确保检查更新时始终能检测到新版


APP_VERSION = _get_version()
GITHUB_OWNER = "HsOjo"
GITHUB_REPO = "RemoteAppDock"
RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
