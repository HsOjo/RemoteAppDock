"""Explorer 任务栏控制辅助。

负责隐藏/恢复 Explorer 原任务栏，避免 RemoteAppDock 与 Windows 默认任务栏冲突。
参考 ManagedShell ExplorerHelper 实现：
- 将 Explorer 任务栏设为 AutoHide。
- 通过 SetWindowPos(SWP_HIDEWINDOW) 隐藏 Shell_TrayWnd 与 Shell_SecondaryTrayWnd。
- 启动监控定时器，若 Explorer 重新显示任务栏则再次隐藏。
- 退出时恢复原始状态与可见性。

本文件部分内容改编自 ManagedShell（Copyright (c) Cairo Shell 及贡献者，
https://github.com/cairoshell/ManagedShell），依据 Apache License 2.0 授权。
Explorer 任务栏隐藏/恢复逻辑由 C# 移植为 Python，并已在此基础上修改。
Apache-2.0 许可全文见 third_party/ManagedShell/LICENSE，归属说明见项目根目录
NOTICE 文件。
"""

import logging
from ctypes import byref, sizeof

from PySide6.QtCore import QObject, QTimer

from remoteappdock.win32 import api, constants
from remoteappdock.win32.structs import APPBARDATA


logger = logging.getLogger(__name__)


class ExplorerHelper(QObject):
    """控制 Explorer 任务栏显隐，确保 RemoteAppDock 独占任务栏区域。"""

    MONITOR_INTERVAL_MS = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hidden = False
        self._startup_state: int | None = None
        self._monitor_timer: QTimer | None = None

    def hide_taskbar(self) -> None:
        """隐藏 Explorer 任务栏并启动监控。"""
        if self._hidden:
            return

        if self._startup_state is None:
            self._startup_state = self._get_taskbar_state()
            logger.debug("Explorer 任务栏原始状态: %s", self._startup_state)

        self._do_hide_taskbar()
        self._hidden = True
        self._start_monitor()
        logger.info("Explorer 任务栏已隐藏")

    def show_taskbar(self) -> None:
        """恢复 Explorer 任务栏并停止监控。"""
        if not self._hidden:
            return

        self._stop_monitor()
        self._set_taskbar_state(self._startup_state if self._startup_state is not None else constants.ABS_ALWAYSONTOP)
        self._set_taskbar_visibility(constants.SWP_SHOWWINDOW)
        self._hidden = False
        logger.info("Explorer 任务栏已恢复")

    def _do_hide_taskbar(self) -> None:
        """执行隐藏：先设 AutoHide，再隐藏窗口。"""
        self._set_taskbar_state(constants.ABS_AUTOHIDE)
        self._set_taskbar_visibility(constants.SWP_HIDEWINDOW)

    def _set_taskbar_visibility(self, swp: int) -> None:
        """设置 Explorer 任务栏可见性。"""
        flags = swp | constants.SWP_NOMOVE | constants.SWP_NOSIZE | constants.SWP_NOACTIVATE

        taskbar_hwnd = api.FindWindowW(constants.SHELL_TRAY_WND, None)
        if taskbar_hwnd:
            visible = api.IsWindowVisible(taskbar_hwnd)
            if (swp == constants.SWP_HIDEWINDOW and visible) or (swp == constants.SWP_SHOWWINDOW and not visible):
                api.SetWindowPos(taskbar_hwnd, constants.HWND_BOTTOM, 0, 0, 0, 0, flags)
                logger.debug("Shell_TrayWnd 可见性已调整: swp=0x%X", swp)

        # 处理多显示器下的副任务栏
        sec_hwnd = api.FindWindowExW(0, 0, "Shell_SecondaryTrayWnd", None)
        while sec_hwnd:
            visible = api.IsWindowVisible(sec_hwnd)
            if (swp == constants.SWP_HIDEWINDOW and visible) or (swp == constants.SWP_SHOWWINDOW and not visible):
                api.SetWindowPos(sec_hwnd, constants.HWND_BOTTOM, 0, 0, 0, 0, flags)
                logger.debug("Shell_SecondaryTrayWnd 可见性已调整: swp=0x%X", swp)
            sec_hwnd = api.FindWindowExW(0, sec_hwnd, "Shell_SecondaryTrayWnd", None)

    def _set_taskbar_state(self, state: int) -> None:
        """通过 SHAppBarMessage 设置 Explorer 任务栏状态。"""
        taskbar_hwnd = api.FindWindowW(constants.SHELL_TRAY_WND, None)
        if not taskbar_hwnd:
            return

        abd = APPBARDATA()
        abd.cbSize = sizeof(APPBARDATA)
        abd.hWnd = taskbar_hwnd
        abd.lParam = state
        api.SHAppBarMessage(constants.ABM_SETSTATE, byref(abd))
        logger.debug("Explorer 任务栏状态已设置: %d", state)

    def _get_taskbar_state(self) -> int:
        """通过 SHAppBarMessage 获取 Explorer 任务栏状态。"""
        taskbar_hwnd = api.FindWindowW(constants.SHELL_TRAY_WND, None)
        if not taskbar_hwnd:
            return constants.ABS_ALWAYSONTOP

        abd = APPBARDATA()
        abd.cbSize = sizeof(APPBARDATA)
        abd.hWnd = taskbar_hwnd
        return int(api.SHAppBarMessage(constants.ABM_GETSTATE, byref(abd)))

    def _start_monitor(self) -> None:
        """启动定时器监控 Explorer 是否重新显示任务栏。"""
        if self._monitor_timer is None:
            self._monitor_timer = QTimer(self)
            self._monitor_timer.timeout.connect(self._on_monitor_tick)
        self._monitor_timer.start(self.MONITOR_INTERVAL_MS)

    def _stop_monitor(self) -> None:
        """停止监控定时器。"""
        if self._monitor_timer is not None:
            self._monitor_timer.stop()

    def _on_monitor_tick(self) -> None:
        """若 Explorer 任务栏重新显示，则再次隐藏。"""
        if not self._hidden:
            return

        taskbar_hwnd = api.FindWindowW(constants.SHELL_TRAY_WND, None)
        if taskbar_hwnd and api.IsWindowVisible(taskbar_hwnd):
            logger.debug("Explorer 任务栏重新显示，再次隐藏")
            self._do_hide_taskbar()
            return

        sec_hwnd = api.FindWindowExW(0, 0, "Shell_SecondaryTrayWnd", None)
        while sec_hwnd:
            if api.IsWindowVisible(sec_hwnd):
                logger.debug("Explorer 副任务栏重新显示，再次隐藏")
                self._do_hide_taskbar()
                return
            sec_hwnd = api.FindWindowExW(0, sec_hwnd, "Shell_SecondaryTrayWnd", None)
