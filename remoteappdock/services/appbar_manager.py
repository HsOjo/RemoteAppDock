"""AppBar 定位管理。"""

import logging
from ctypes import byref, sizeof

from PySide6.QtCore import QObject, QTimer, Signal

from remoteappdock.win32 import api, constants
from remoteappdock.win32.api import SHAppBarMessage
from remoteappdock.win32.structs import APPBARDATA, RECT, MONITORINFO


logger = logging.getLogger(__name__)


class AppBarManager(QObject):
    """管理任务栏作为 AppBar 的定位与自动隐藏。"""

    position_changed = Signal(object)

    def __init__(self, edge: str = "bottom", auto_hide: bool = False, monitor: int = 0):
        super().__init__()
        self._edge = edge
        self._auto_hide = auto_hide
        self._monitor = monitor
        self._hwnd: int = 0
        self._registered: bool = False
        self._hidden: bool = False
        self._auto_hide_timer: QTimer | None = None

    @property
    def edge(self) -> str:
        return self._edge

    def set_edge(self, edge: str) -> None:
        self._edge = edge
        if self._registered:
            self._update_position()

    def set_auto_hide(self, auto_hide: bool) -> None:
        self._auto_hide = auto_hide
        if self._registered:
            self._register()

    def register(self, hwnd: int) -> bool:
        """注册 AppBar。"""
        self._hwnd = hwnd
        if self._registered:
            return True

        abd = self._create_appbar_data()
        result = SHAppBarMessage(constants.ABM_NEW, byref(abd))
        self._registered = result != 0
        if not self._registered:
            logger.error("AppBar 注册失败: hwnd=0x%X", hwnd)
            return False

        self._update_position()
        logger.info("AppBar 已注册: hwnd=0x%X, edge=%s", hwnd, self._edge)
        return True

    def unregister(self) -> None:
        """注销 AppBar。"""
        if not self._registered:
            return
        abd = self._create_appbar_data()
        SHAppBarMessage(constants.ABM_REMOVE, byref(abd))
        self._registered = False
        logger.info("AppBar 已注销: hwnd=0x%X", self._hwnd)

    def _create_appbar_data(self) -> APPBARDATA:
        abd = APPBARDATA()
        abd.cbSize = sizeof(APPBARDATA)  # noqa: F821
        abd.hWnd = self._hwnd
        abd.uCallbackMessage = constants.WM_USER + 100
        abd.uEdge = self._edge_to_abd(self._edge)
        abd.lParam = 1 if self._auto_hide else 0
        return abd

    def _edge_to_abd(self, edge: str) -> int:
        return {
            "left": constants.ABE_LEFT,
            "top": constants.ABE_TOP,
            "right": constants.ABE_RIGHT,
            "bottom": constants.ABE_BOTTOM,
        }.get(edge, constants.ABE_BOTTOM)

    def _update_position(self) -> None:
        if not self._registered:
            return

        abd = self._create_appbar_data()
        edge = abd.uEdge

        # 获取目标显示器工作区
        monitor = api.MonitorFromWindow(self._hwnd, constants.MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = sizeof(MONITORINFO)  # noqa: F821
        work_area = mi.rcWork
        if monitor and api.GetMonitorInfoW(monitor, byref(mi)):
            work_area = mi.rcWork

        # 查询位置
        if edge == constants.ABE_LEFT:
            abd.rc.left = work_area.left
            abd.rc.top = work_area.top
            abd.rc.right = work_area.left + 40
            abd.rc.bottom = work_area.bottom
        elif edge == constants.ABE_TOP:
            abd.rc.left = work_area.left
            abd.rc.top = work_area.top
            abd.rc.right = work_area.right
            abd.rc.bottom = work_area.top + 40
        elif edge == constants.ABE_RIGHT:
            abd.rc.left = work_area.right - 40
            abd.rc.top = work_area.top
            abd.rc.right = work_area.right
            abd.rc.bottom = work_area.bottom
        else:  # bottom
            abd.rc.left = work_area.left
            abd.rc.top = work_area.bottom - 40
            abd.rc.right = work_area.right
            abd.rc.bottom = work_area.bottom

        SHAppBarMessage(constants.ABM_QUERYPOS, byref(abd))
        SHAppBarMessage(constants.ABM_SETPOS, byref(abd))

        self.position_changed.emit(abd.rc)

    def handle_appbar_notification(self, hwnd: int, msg: int, wparam: int, lparam: int) -> bool:
        """处理 AppBar 通知消息。"""
        if msg != constants.WM_USER + 100:
            return False
        if wparam == constants.ABN_POSCHANGED:
            self._update_position()
        elif wparam == constants.ABN_FULLSCREENAPP:
            # 全屏应用时自动隐藏
            pass
        elif wparam == constants.ABN_STATECHANGE:
            pass
        return True

    def show(self) -> None:
        if self._hidden:
            self._hidden = False
            self._update_position()

    def hide(self) -> None:
        if not self._hidden:
            self._hidden = True
            # 移动到屏幕外
            pass
