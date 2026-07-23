"""应用单实例启动管理。

通过命名互斥体（named mutex）检测是否已有实例在运行，并通过隐藏的消息窗口
向已有实例发送激活请求。
"""

import ctypes
import logging
import threading
from typing import Callable

from remoteappdock.win32 import constants, api
from remoteappdock.win32.api import (
    CreateMutexW, ReleaseMutex, CloseHandle, FindWindowW, PostMessageW,
    RegisterWindowMessageW, GetLastError,
)
from remoteappdock.win32.message_pump import Win32MessageThread
from remoteappdock.win32.wndproc import WndProcDispatcher


logger = logging.getLogger(__name__)

DEFAULT_MUTEX_NAME = r"Local\RemoteAppDock_SingleInstance"
DEFAULT_WINDOW_CLASS = "RemoteAppDock_SingleInstance_MsgWindow"
ACTIVATION_MESSAGE = "RemoteAppDock_ActivateInstance"


class SingleInstanceManager:
    """管理单实例启动与跨实例激活。

    用法：
        single = SingleInstanceManager()
        if not single.try_acquire():
            # 已有实例在运行，尝试激活后退出
            single.activate_existing_instance()
            sys.exit(0)

        # 首个实例：启动监听并连接激活回调
        single.set_on_activate(app.activate)
        single.start_listener()
        ...
        single.release()
    """

    def __init__(
        self,
        mutex_name: str = DEFAULT_MUTEX_NAME,
        window_class_name: str = DEFAULT_WINDOW_CLASS,
        on_activate: Callable[[], None] | None = None,
    ):
        self._mutex_name = mutex_name
        self._class_name = window_class_name
        self._on_activate = on_activate
        self._mutex: ctypes.c_void_p | None = None
        self._thread: Win32MessageThread | None = None
        self._hwnd: int = 0
        self._activation_msg: int = 0
        self._activate_event = threading.Event()
        self._is_first_instance: bool | None = None

    def _on_activation(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int | None:
        """收到来自其他实例的激活请求。"""
        if msg == self._activation_msg:
            logger.debug("收到实例激活消息")
            self._activate_event.set()
            return 0
        return None

    def try_acquire(self) -> bool:
        """尝试获取单实例互斥体。

        返回 True 表示当前是第一个实例；False 表示已有其他实例在运行。
        对于已有实例的情况，本方法会立即关闭获得的句柄，调用方无需释放。
        """
        mutex = CreateMutexW(None, False, self._mutex_name)
        if not mutex:
            err = GetLastError()
            raise RuntimeError(f"创建单实例互斥体失败，错误码: {err}")

        if GetLastError() == constants.ERROR_ALREADY_EXISTS:
            CloseHandle(mutex)
            self._is_first_instance = False
            return False

        self._mutex = mutex
        self._is_first_instance = True
        return True

    def is_first_instance(self) -> bool:
        """返回 try_acquire 的结果；调用前必须先执行 try_acquire。"""
        if self._is_first_instance is None:
            raise RuntimeError("is_first_instance() 必须在 try_acquire() 之后调用")
        return self._is_first_instance

    def start_listener(self) -> None:
        """创建隐藏消息窗口并监听激活请求。仅应在首个实例中调用。"""
        if self._is_first_instance is None:
            raise RuntimeError("start_listener() 必须先调用 try_acquire()")
        if not self._is_first_instance:
            raise RuntimeError("非首个实例不应启动监听器")

        self._activation_msg = RegisterWindowMessageW(ACTIVATION_MESSAGE)

        dispatcher = WndProcDispatcher()
        dispatcher.register(self._activation_msg, self._on_activation)

        self._thread = Win32MessageThread(
            class_name=self._class_name,
            window_name="RemoteAppDockSingleInstance",
            wndproc=dispatcher.wndproc,
            style=0,
            ex_style=0,
            parent=constants.HWND_MESSAGE,
            register_class=True,
            x=0, y=0, width=0, height=0,
        )
        self._thread.start()
        self._hwnd = self._thread.hwnd
        logger.info("单实例消息窗口已创建: hwnd=0x%X", self._hwnd)

    def process_activate_event(self) -> None:
        """由主线程调用，处理待处理的激活请求。"""
        if not self._activate_event.is_set():
            return
        self._activate_event.clear()
        logger.info("处理实例激活请求")
        if self._on_activate is not None:
            try:
                self._on_activate()
            except Exception:
                logger.exception("执行激活回调时发生异常")

    def set_on_activate(self, callback: Callable[[], None] | None) -> None:
        """设置收到激活请求时的回调函数。"""
        self._on_activate = callback

    def activate_existing_instance(self) -> bool:
        """向已有实例发送激活请求。

        返回 True 表示消息已成功投递；False 表示未找到已有实例窗口或投递失败。
        """
        self._activation_msg = RegisterWindowMessageW(ACTIVATION_MESSAGE)
        hwnd = FindWindowW(self._class_name, None)
        if not hwnd:
            logger.warning("未找到已有实例的消息窗口")
            return False
        if not PostMessageW(hwnd, self._activation_msg, 0, 0):
            err = GetLastError()
            logger.warning("发送激活消息失败，错误码: %s", err)
            return False
        logger.info("已向已有实例发送激活请求")
        return True

    def release(self) -> None:
        """释放互斥体并停止消息窗口。可安全重复调用。"""
        if self._thread is not None:
            self._thread.stop()
            self._thread = None
            self._hwnd = 0
        if self._mutex is not None:
            ReleaseMutex(self._mutex)
            CloseHandle(self._mutex)
            self._mutex = None
        self._is_first_instance = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
