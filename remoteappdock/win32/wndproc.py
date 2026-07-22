"""WndProc 工厂与分发。

将不同 Win32 消息分发给对应的 service 处理，并负责返回值。
"""

import ctypes
import logging
from collections import defaultdict
from typing import Callable

from remoteappdock.win32 import constants, api
from remoteappdock.win32.api import DefWindowProcW, WNDPROC


logger = logging.getLogger(__name__)


class WndProcDispatcher:
    """WndProc 分发器。"""

    def __init__(self):
        self._handlers: dict[int, list[Callable]] = defaultdict(list)
        self._default_handler: Callable | None = None
        self._wndproc_ref = WNDPROC(self._wndproc)

    @property
    def wndproc(self):
        """返回 ctypes 回调引用，必须保持强引用。"""
        return self._wndproc_ref

    def register(self, msg: int, handler: Callable) -> None:
        """注册某条消息的处理器。"""
        self._handlers[msg].append(handler)

    def unregister(self, msg: int, handler: Callable) -> None:
        """注销消息处理器。"""
        if handler in self._handlers[msg]:
            self._handlers[msg].remove(handler)

    def set_default_handler(self, handler: Callable) -> None:
        """设置默认处理器。"""
        self._default_handler = handler

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """ctypes WndProc 回调。"""
        try:
            if msg in self._handlers:
                for handler in self._handlers[msg]:
                    result = handler(hwnd, msg, wparam, lparam)
                    if result is not None:
                        return result

            if self._default_handler is not None:
                result = self._default_handler(hwnd, msg, wparam, lparam)
                if result is not None:
                    return result

        except Exception:
            logger.exception("WndProc 处理消息 0x%04X 时发生异常", msg)

        return DefWindowProcW(hwnd, msg, wparam, lparam)


def create_default_wndproc() -> WndProcDispatcher:
    """创建默认 WndProc 分发器。"""
    return WndProcDispatcher()
