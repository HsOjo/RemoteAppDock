"""应用版本信息。

开发环境下版本以 pyproject.toml 中的 project.version 为准；PyInstaller 打包后不再
附带 pyproject.toml，版本从安装包元数据中读取（仍由 pyproject.toml 生成）。
"""

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
    # 开发环境：pyproject.toml 位于 remoteappdock 包的上级目录
    dev_pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if dev_pyproject.exists():
        version_from_dev = _read_version_from_pyproject(dev_pyproject)
        if version_from_dev:
            return version_from_dev

    # 打包环境或安装环境：从安装包元数据读取（由 pyproject.toml 生成）
    try:
        return version("remoteappdock")
    except PackageNotFoundError:
        pass

    return "0.0.0"  # 回退版本：确保检查更新时始终能检测到新版


APP_VERSION = _get_version()
GITHUB_OWNER = "HsOjo"
GITHUB_REPO = "RemoteAppDock"
RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
