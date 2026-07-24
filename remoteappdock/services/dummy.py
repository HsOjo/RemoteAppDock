"""非 Windows 平台的占位（dummy）服务实现。

在 macOS 等系统上，RemoteAppDock 无法与系统任务栏/窗口管理交互，
因此使用这些 dummy 服务让主界面能够启动并预览布局；
实际窗口/托盘操作仅通过日志 mock，不做任何事。
"""

import logging

from PySide6.QtCore import QObject, Signal

from remoteappdock.models.application_window import ApplicationWindow
from remoteappdock.models.notify_icon import NotifyIcon


logger = logging.getLogger(__name__)


# 供 UI 预览用的模拟数据
_MOCK_WINDOWS = [
    ApplicationWindow(handle=0x10001, title="Visual Studio Code", state="active", proc_id=1001),
    ApplicationWindow(handle=0x10002, title="Terminal", state="normal", proc_id=1002),
    ApplicationWindow(handle=0x10003, title="Finder", state="minimized", proc_id=1003),
    ApplicationWindow(handle=0x10004, title="PySide6 Demo", state="normal", proc_id=1004),
]

_MOCK_ICONS = [
    NotifyIcon(hWnd=0x20001, uID=1, title="Mock Network"),
    NotifyIcon(hWnd=0x20002, uID=2, title="Mock Volume"),
    NotifyIcon(hWnd=0x20003, uID=3, title="Mock Chat"),
]


class DummyWindowManager(QObject):
    """占位窗口列表管理器，始终返回空列表。"""

    window_added = Signal(ApplicationWindow)
    window_removed = Signal(int)
    window_updated = Signal(ApplicationWindow)

    def __init__(self):
        super().__init__()
        self._windows: dict[int, ApplicationWindow] = {
            w.handle: w for w in _MOCK_WINDOWS
        }

    def get_windows(self) -> list[ApplicationWindow]:
        return list(self._windows.values())

    def clear(self) -> None:
        for hwnd in list(self._windows.keys()):
            self.window_removed.emit(hwnd)
        self._windows.clear()


class DummyTasksService(QObject):
    """占位任务服务，窗口操作仅打印日志。"""

    window_event = Signal(object)

    def __init__(self, window_manager: DummyWindowManager):
        super().__init__()
        self._window_manager = window_manager

    def start(self) -> None:
        logger.info("DummyTasksService.start() 被调用（非 Windows 平台无实际效果）")
        # 为 UI 预览注入几个模拟窗口
        for window in _MOCK_WINDOWS:
            self._window_manager.window_added.emit(window)

    def stop(self) -> None:
        logger.debug("DummyTasksService.stop() 被调用")
        self._window_manager.clear()

    def process_events(self) -> None:
        pass

    def activate_window(self, hwnd: int) -> None:
        logger.info("[mock] 激活窗口: hwnd=%s", hwnd)

    def minimize_window(self, hwnd: int) -> None:
        logger.info("[mock] 最小化窗口: hwnd=%s", hwnd)

    def maximize_window(self, hwnd: int) -> None:
        logger.info("[mock] 最大化窗口: hwnd=%s", hwnd)

    def restore_window(self, hwnd: int) -> None:
        logger.info("[mock] 恢复窗口: hwnd=%s", hwnd)

    def close_window(self, hwnd: int) -> None:
        logger.info("[mock] 关闭窗口: hwnd=%s", hwnd)


class DummyTrayService(QObject):
    """占位托盘服务，鼠标事件仅打印日志。"""

    icon_event = Signal(object)

    def __init__(self, notification_area: NotificationArea):
        super().__init__()
        self._notification_area = notification_area

    def start(self) -> None:
        logger.debug("DummyTrayService.start() 被调用（非 Windows 平台无实际效果）")
        # 为 UI 预览注入几个模拟托盘图标
        for icon in _MOCK_ICONS:
            self._notification_area.add_icon(icon)

    def stop(self) -> None:
        logger.debug("DummyTrayService.stop() 被调用")
        self._notification_area.clear()

    def process_events(self) -> None:
        pass

    def forward_mouse_event(self, hWnd: int, uID: int, callback_message: int, msg: int,
                            mouse: int = 0, version: int = 0) -> bool:
        logger.info("[mock] 转发托盘鼠标事件: hWnd=%s uID=%s msg=%s", hWnd, uID, msg)
        return False

    def forward_select_event(self, hWnd: int, uID: int, callback_message: int) -> bool:
        logger.info("[mock] 转发托盘选择事件: hWnd=%s uID=%s", hWnd, uID)
        return False

    def forward_keyselect_event(self, hWnd: int, uID: int, callback_message: int) -> bool:
        logger.info("[mock] 转发托盘键盘选择事件: hWnd=%s uID=%s", hWnd, uID)
        return False

    def update_icon_rect(self, hWnd: int, uID: int, guid, rect) -> None:
        pass

    def remove_icon_rect(self, hWnd: int, uID: int, guid=None) -> None:
        pass


class DummyAppBarManager:
    """占位 AppBar 管理器。"""

    def unregister(self) -> None:
        pass


class DummyHotkeyManager:
    """占位热键管理器。"""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class DummyExplorerHelper:
    """占位 Explorer 任务栏辅助（macOS 无 Explorer）。"""

    def hide_taskbar(self) -> None:
        pass

    def show_taskbar(self) -> None:
        pass


class DummySnapLayoutHelper:
    """占位分屏布局辅助（macOS 无 Aero Snap）。"""

    def disable(self) -> None:
        pass

    def restore(self) -> None:
        pass
