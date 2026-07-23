"""Windows Aero Snap 分屏功能控制辅助。

在应用运行期间关闭 Aero Snap 总开关（对应"设置 > 系统 > 多任务处理 >
贴靠窗口"），退出时恢复原状。关闭后拖动窗口不会出现任何贴靠/分屏提示，
包括拖到屏幕顶部弹出的 Snap 布局格子条，以及拖到屏幕边缘的半屏贴靠。

通过 SystemParametersInfo(SPI_SETWINARRANGING) 实现，即时生效、无需重启
Explorer。禁用时缓存原始开关状态，恢复时写回。相较直接改注册表
EnableSnapBar/SnapAssist（需 Explorer 重启才生效），本方案能立即响应。
"""

import logging
from ctypes import byref, c_int

from remoteappdock.win32 import api, constants


logger = logging.getLogger(__name__)


class SnapLayoutHelper:
    """运行期间关闭 Aero Snap，退出时恢复。"""

    def __init__(self) -> None:
        self._disabled = False
        self._original: bool | None = None  # 原始开关状态；None 表示未缓存

    def disable(self) -> None:
        """缓存原始状态并关闭 Aero Snap。"""
        if self._disabled:
            return

        self._original = self._get_win_arranging()
        if self._original is None:
            logger.warning("读取 Aero Snap 状态失败，跳过禁用")
            return

        if self._set_win_arranging(False):
            self._disabled = True
            logger.info("Aero Snap 已关闭，原始状态: %s", self._original)

    def restore(self) -> None:
        """恢复 Aero Snap 到原始状态。"""
        if not self._disabled:
            return

        if self._original is not None:
            self._set_win_arranging(self._original)
        self._disabled = False
        self._original = None
        logger.info("Aero Snap 已恢复")

    @staticmethod
    def _get_win_arranging() -> bool | None:
        """读取 Aero Snap 总开关状态；失败返回 None。"""
        value = c_int(0)
        ok = api.SystemParametersInfoW(
            constants.SPI_GETWINARRANGING, 0, byref(value), 0
        )
        if not ok:
            return None
        return bool(value.value)

    @staticmethod
    def _set_win_arranging(enabled: bool) -> bool:
        """设置 Aero Snap 总开关，写入配置并广播变更；返回是否成功。"""
        ok = api.SystemParametersInfoW(
            constants.SPI_SETWINARRANGING,
            1 if enabled else 0,
            None,
            constants.SPIF_UPDATEINIFILE | constants.SPIF_SENDCHANGE,
        )
        if not ok:
            logger.warning("设置 Aero Snap 状态失败: enabled=%s", enabled)
        return bool(ok)
