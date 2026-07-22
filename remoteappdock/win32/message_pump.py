"""Win32 消息泵线程。

在独立线程中创建窗口并运行 GetMessage/DispatchMessage 循环，
避免阻塞 Qt 主线程。
"""

import ctypes
import queue
import threading
from ctypes import byref, c_void_p, c_int, c_uint, c_long, c_ulong, c_longlong, c_ulonglong, c_wchar_p, c_ushort, sizeof

from remoteappdock.win32 import constants, api
from remoteappdock.win32.api import (
    WNDPROC, RegisterClassW, UnregisterClassW, CreateWindowExW, DestroyWindow,
    DefWindowProcW, GetMessageW, DispatchMessageW, TranslateMessage, PeekMessageW,
    PostMessageW, GetModuleHandleW, GetLastError, SetWindowLongPtrW, GetWindowLongPtrW,
)
from remoteappdock.win32.structs import WNDCLASSW, MSG, POINT


class Win32MessageThread:
    """运行 Win32 消息泵的线程。"""

    _class_atom_counter = 0
    _class_atoms_lock = threading.Lock()

    def __init__(
        self,
        class_name: str | None = None,
        window_name: str = "",
        wndproc=None,
        style: int = 0,
        ex_style: int = 0,
        parent: int = 0,
        register_class: bool = True,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
    ):
        self._class_name = class_name or self._generate_class_name()
        self._window_name = window_name
        self._wndproc = wndproc
        self._style = style
        self._ex_style = ex_style
        self._parent = parent
        self._register_class = register_class
        self._x = x
        self._y = y
        self._width = width
        self._height = height

        self._thread: threading.Thread | None = None
        self._hwnd: int = 0
        self._class_atom: int = 0
        self._stop_event: threading.Event = threading.Event()
        self._command_queue: queue.Queue = queue.Queue()
        self._wndproc_ref = None  # 保持引用，避免 GC

    @classmethod
    def _generate_class_name(cls) -> str:
        with cls._class_atoms_lock:
            cls._class_atom_counter += 1
            return f"RemoteAppDockWin32MsgThread_{cls._class_atom_counter}"

    @property
    def hwnd(self) -> int:
        return self._hwnd

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="Win32MessageThread", daemon=True)
        self._thread.start()
        # 等待窗口创建完成
        self._hwnd = self._command_queue.get(timeout=5.0)
        if self._hwnd == 0:
            raise RuntimeError("Failed to create message window")

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        if self._hwnd:
            PostMessageW(self._hwnd, constants.WM_QUIT, 0, 0)
        self._thread.join(timeout=5.0)
        self._thread = None
        self._hwnd = 0

    def post_message(self, hwnd: int, msg: int, wparam: int = 0, lparam: int = 0) -> bool:
        """向指定窗口发送消息（Win32 线程安全）。"""
        if hwnd == 0:
            return False
        return bool(PostMessageW(hwnd, msg, wparam, lparam))

    def _run(self) -> None:
        """线程入口。"""
        try:
            class_exists = False
            if self._register_class:
                self._class_atom = self._register_class_impl()
                class_exists = self._class_atom == 0 and api.GetLastError() == 1411  # ERROR_CLASS_ALREADY_EXISTS
                if self._class_atom == 0 and not class_exists:
                    self._command_queue.put(0)
                    return

            self._hwnd = CreateWindowExW(
                self._ex_style,
                self._class_name,
                self._window_name,
                self._style,
                self._x, self._y, self._width, self._height,
                self._parent, 0,
                GetModuleHandleW(None),
                None,
            )
            if self._hwnd == 0:
                self._command_queue.put(0)
                if self._class_atom:
                    UnregisterClassW(self._class_name, GetModuleHandleW(None))
                return

            self._command_queue.put(self._hwnd)

            msg = MSG()
            while not self._stop_event.is_set():
                ret = GetMessageW(byref(msg), 0, 0, 0)
                if ret == 0 or msg.message == constants.WM_QUIT:
                    break
                TranslateMessage(byref(msg))
                DispatchMessageW(byref(msg))
        finally:
            if self._hwnd:
                DestroyWindow(self._hwnd)
                self._hwnd = 0
            if self._class_atom and self._class_name:
                UnregisterClassW(self._class_name, GetModuleHandleW(None))
                self._class_atom = 0

    def _register_class_impl(self) -> int:
        """注册窗口类。"""
        if self._wndproc is None:
            self._wndproc = self._default_wndproc
        self._wndproc_ref = WNDPROC(self._wndproc)

        wndclass = WNDCLASSW()
        wndclass.style = constants.CS_DBLCLKS
        wndclass.lpfnWndProc = ctypes.cast(self._wndproc_ref, c_void_p).value
        wndclass.hInstance = GetModuleHandleW(None)
        wndclass.lpszClassName = self._class_name

        atom = RegisterClassW(byref(wndclass))
        return atom

    @staticmethod
    def _default_wndproc(hwnd, msg, wparam, lparam):
        """默认 WndProc。"""
        return DefWindowProcW(hwnd, msg, wparam, lparam)
