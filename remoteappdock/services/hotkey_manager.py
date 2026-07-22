"""热键管理（Win+数字）。"""

import logging

from PySide6.QtCore import QObject, Signal

from remoteappdock.win32 import constants, api
from remoteappdock.win32.api import RegisterHotKey, UnregisterHotKey
from remoteappdock.win32.message_pump import Win32MessageThread
from remoteappdock.win32.wndproc import WndProcDispatcher


logger = logging.getLogger(__name__)


class HotkeyManager(QObject):
    """管理 Win+数字 热键，激活对应任务栏窗口。"""

    hotkey_activated = Signal(int)  # 1-10

    def __init__(self, tasks_service):
        super().__init__()
        self._tasks_service = tasks_service
        self._thread: Win32MessageThread | None = None
        self._hwnd: int = 0
        self._dispatcher = WndProcDispatcher()
        self._registered: set[int] = set()

        self._dispatcher.register(constants.WM_HOTKEY, self._on_hotkey)

    def start(self) -> None:
        self._thread = Win32MessageThread(
            class_name=None,
            window_name="RemoteAppDockHotkeys",
            wndproc=self._dispatcher.wndproc,
        )
        self._thread.start()
        self._hwnd = self._thread.hwnd

        # 注册 Win+1 到 Win+9, Win+0 作为第 10 个
        vks = [0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30]
        for i, vk in enumerate(vks, start=1):
            if RegisterHotKey(self._hwnd, i, constants.MOD_WIN, vk):
                self._registered.add(i)
                logger.debug("注册热键 Win+%d", i if i < 10 else 0)
            else:
                # Windows 保留 Win+数字给默认 Shell，注册失败属于预期行为
                logger.debug("跳过系统保留热键 Win+%d", i if i < 10 else 0)

    def stop(self) -> None:
        for hotkey_id in list(self._registered):
            UnregisterHotKey(self._hwnd, hotkey_id)
        self._registered.clear()
        if self._thread is not None:
            self._thread.stop()
            self._thread = None
            self._hwnd = 0

    def _on_hotkey(self, hwnd, msg, wparam, lparam) -> int:
        hotkey_id = int(wparam)
        self.hotkey_activated.emit(hotkey_id)
        self._activate_window(hotkey_id)
        return 0

    def _activate_window(self, index: int) -> None:
        """激活任务栏上第 index 个窗口。"""
        windows = self._tasks_service._window_manager.get_windows()
        if 1 <= index <= len(windows):
            window = windows[index - 1]
            self._tasks_service.activate_window(window.handle)
