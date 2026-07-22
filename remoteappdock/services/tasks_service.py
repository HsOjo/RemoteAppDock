"""任务列表服务。"""

import logging
import queue

from PySide6.QtCore import QObject, Signal

from remoteappdock.models.application_window import ApplicationWindow
from remoteappdock.win32 import api, constants
from remoteappdock.win32.api import (
    RegisterWindowMessageW, RegisterShellHookWindow, DeregisterShellHookWindow,
    SetWinEventHook, UnhookWinEvent, SetTaskmanWindow,
)
from remoteappdock.win32.message_pump import Win32MessageThread
from remoteappdock.win32.wndproc import WndProcDispatcher
from remoteappdock.win32.structs import SHELLHOOKINFO


logger = logging.getLogger(__name__)


class WindowManager(QObject):
    """维护任务栏窗口列表。"""

    window_added = Signal(ApplicationWindow)
    window_removed = Signal(int)  # handle
    window_updated = Signal(ApplicationWindow)

    def __init__(self):
        super().__init__()
        self._windows: dict[int, ApplicationWindow] = {}

    def add_or_update(self, hwnd: int) -> ApplicationWindow | None:
        """添加或更新窗口，如果不应显示则返回 None。"""
        if not self._should_show(hwnd):
            self.remove(hwnd)
            return None

        existing = self._windows.get(hwnd)
        if existing is not None:
            updated = self._update_window(existing)
            if updated:
                self.window_updated.emit(existing)
            return existing

        window = self._create_window(hwnd)
        if window is None:
            return None
        self._windows[hwnd] = window
        self.window_added.emit(window)
        logger.debug("添加窗口: hwnd=0x%X title=%s", hwnd, window.title)
        return window

    def remove(self, hwnd: int) -> None:
        if hwnd in self._windows:
            del self._windows[hwnd]
            self.window_removed.emit(hwnd)
            logger.debug("移除窗口: hwnd=0x%X", hwnd)

    def get_window(self, hwnd: int) -> ApplicationWindow | None:
        return self._windows.get(hwnd)

    def get_windows(self) -> list[ApplicationWindow]:
        return list(self._windows.values())

    def clear(self) -> None:
        for hwnd in list(self._windows.keys()):
            self.window_removed.emit(hwnd)
        self._windows.clear()

    def _should_show(self, hwnd: int) -> bool:
        """判断窗口是否应该出现在任务栏。"""
        if not api.IsWindow(hwnd):
            return False
        if not api.IsWindowVisible(hwnd):
            return False
        if api.is_window_cloaked(hwnd):
            return False

        ex_style = api.GetWindowLongPtrW(hwnd, constants.GWL_EXSTYLE)
        if ex_style & constants.WS_EX_TOOLWINDOW:
            return False
        if ex_style == 0:
            return False

        style = api.GetWindowLongPtrW(hwnd, constants.GWL_STYLE)
        if not (style & constants.WS_CAPTION):
            return False

        return True

    def _create_window(self, hwnd: int) -> ApplicationWindow | None:
        title = api.get_window_text(hwnd)
        class_name = api.get_class_name(hwnd)
        proc_id = api.get_window_process_id(hwnd)
        window = ApplicationWindow(
            handle=hwnd,
            title=title,
            class_name=class_name,
            proc_id=proc_id,
        )
        self._update_state(window)
        return window

    def _update_window(self, window: ApplicationWindow) -> bool:
        """更新窗口属性，返回是否有变化。"""
        old_title = window.title
        old_state = window.state

        window.title = api.get_window_text(window.handle)
        self._update_state(window)

        return window.title != old_title or window.state != old_state

    def _update_state(self, window: ApplicationWindow) -> None:
        hwnd = window.handle
        if api.IsIconic(hwnd):
            window.state = "minimized"
        elif api.IsZoomed(hwnd):
            window.state = "maximized"
        elif hwnd == api.GetForegroundWindow():
            window.state = "active"
        else:
            window.state = "normal"

    # 窗口操作

    def activate_window(self, hwnd: int) -> None:
        if api.IsWindow(hwnd):
            api.AllowSetForegroundWindow(0xFFFFFFFF)
            api.SetForegroundWindow(hwnd)
            if api.IsIconic(hwnd):
                api.ShowWindow(hwnd, constants.SW_RESTORE)
            api.SetForegroundWindow(hwnd)

    def minimize_window(self, hwnd: int) -> None:
        if api.IsWindow(hwnd):
            api.ShowWindow(hwnd, constants.SW_MINIMIZE)

    def maximize_window(self, hwnd: int) -> None:
        if api.IsWindow(hwnd):
            api.ShowWindow(hwnd, constants.SW_MAXIMIZE)

    def restore_window(self, hwnd: int) -> None:
        if api.IsWindow(hwnd):
            api.ShowWindow(hwnd, constants.SW_RESTORE)

    def close_window(self, hwnd: int) -> None:
        if api.IsWindow(hwnd):
            api.PostMessageW(hwnd, constants.WM_CLOSE, 0, 0)

    def enumerate_existing_windows(self) -> None:
        """枚举所有现有窗口并加入列表。"""
        api.EnumWindows(api.ENUMWINDOWSPROC(self._enum_callback), 0)

    def _enum_callback(self, hwnd: int, _lparam: int) -> bool:
        self.add_or_update(hwnd)
        return True


class TasksService(QObject):
    """任务列表服务，负责注册 Shell Hook 并接收窗口事件。"""

    window_event = Signal(object)

    def __init__(self, window_manager: WindowManager):
        super().__init__()
        self._window_manager = window_manager
        self._thread: Win32MessageThread | None = None
        self._hwnd: int = 0
        self._dispatcher = WndProcDispatcher()
        self._event_queue: queue.Queue = queue.Queue()
        self._shell_hook_msg: int = 0
        self._win_event_hook = 0
        self._win_event_proc_ref = api.WINEVENTPROC(self._win_event_proc)

        self._dispatcher.register(constants.WM_CREATE, self._on_create)
        self._dispatcher.register(constants.WM_DESTROY, self._on_destroy)
        self._dispatcher.set_default_handler(self._on_default)

    def start(self) -> None:
        self._shell_hook_msg = RegisterWindowMessageW("SHELLHOOK")
        if self._shell_hook_msg == 0:
            raise RuntimeError("无法注册 SHELLHOOK 消息")

        self._thread = Win32MessageThread(
            class_name=None,  # 使用内部生成的唯一类名
            window_name="RemoteAppDockTasks",
            wndproc=self._dispatcher.wndproc,
            style=0,
            ex_style=0,
        )
        self._thread.start()
        self._hwnd = self._thread.hwnd

        # 注册 Shell Hook
        if not RegisterShellHookWindow(self._hwnd):
            raise RuntimeError("RegisterShellHookWindow 失败")

        # 设置 Taskman 窗口，让系统知道这个任务栏窗口
        SetTaskmanWindow(self._hwnd)

        # 监听 DWM cloaked 和位置变化
        self._win_event_hook = SetWinEventHook(
            constants.EVENT_OBJECT_CREATE, constants.EVENT_OBJECT_LOCATIONCHANGE,
            0, self._win_event_proc_ref,
            0, 0, constants.WINEVENT_OUTOFCONTEXT | constants.WINEVENT_SKIPOWNPROCESS
        )

        # 枚举现有窗口
        self._window_manager.enumerate_existing_windows()
        logger.info("TasksService 已启动: hwnd=0x%X", self._hwnd)

    def stop(self) -> None:
        if self._win_event_hook:
            UnhookWinEvent(self._win_event_hook)
            self._win_event_hook = 0
        if self._thread is not None:
            DeregisterShellHookWindow(self._hwnd)
            self._thread.stop()
            self._thread = None
            self._hwnd = 0
        self._window_manager.clear()

    def drain_events(self) -> list:
        events = []
        while True:
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def process_events(self) -> None:
        for event in self.drain_events():
            try:
                self._process_event(event)
            except Exception:
                logger.exception("处理任务事件失败: %s", event)

    def _on_default(self, hwnd, msg, wparam, lparam) -> int | None:
        if msg == self._shell_hook_msg:
            self._on_shell_hook(wparam, lparam)
            return 0
        return None

    def _on_shell_hook(self, wparam, lparam) -> None:
        event = int(wparam) & 0x7FFF
        hwnd = int(lparam)

        if event in (constants.HSHELL_WINDOWCREATED, constants.HSHELL_WINDOWACTIVATED,
                     constants.HSHELL_RUDEAPPACTIVATED, constants.HSHELL_FLASH,
                     constants.HSHELL_REDRAW, constants.HSHELL_MONITORCHANGED):
            self._queue_event(("update", hwnd))
        elif event == constants.HSHELL_WINDOWDESTROYED:
            self._queue_event(("destroy", hwnd))
        elif event == constants.HSHELL_GETMINRECT:
            # 返回最小化按钮矩形，需要同步处理
            pass

    def _on_create(self, hwnd, msg, wparam, lparam) -> int | None:
        return None

    def _on_destroy(self, hwnd, msg, wparam, lparam) -> int | None:
        logger.info("Tasks 窗口收到 WM_DESTROY")
        return None

    def _win_event_proc(self, hook, event, hwnd, id_object, id_child, event_thread, event_time) -> None:
        if event in (constants.EVENT_OBJECT_CREATE, constants.EVENT_OBJECT_SHOW,
                     constants.EVENT_OBJECT_HIDE, constants.EVENT_OBJECT_LOCATIONCHANGE,
                     constants.EVENT_OBJECT_STATECHANGE, constants.EVENT_OBJECT_NAMECHANGE):
            self._queue_event(("update", hwnd))

    def _queue_event(self, event) -> None:
        """将事件放入队列，并尝试触发主线程处理。"""
        try:
            self.window_event.emit(event)
        except RuntimeError:
            # Qt 对象已被销毁（退出过程中），忽略信号发射
            pass
        self._event_queue.put(event)

    def _process_event(self, event) -> None:
        action, hwnd = event
        if action == "destroy":
            self._window_manager.remove(hwnd)
        elif action == "update":
            self._window_manager.add_or_update(hwnd)

    def activate_window(self, hwnd: int) -> None:
        self._window_manager.activate_window(hwnd)

    def minimize_window(self, hwnd: int) -> None:
        self._window_manager.minimize_window(hwnd)

    def maximize_window(self, hwnd: int) -> None:
        self._window_manager.maximize_window(hwnd)

    def restore_window(self, hwnd: int) -> None:
        self._window_manager.restore_window(hwnd)

    def close_window(self, hwnd: int) -> None:
        self._window_manager.close_window(hwnd)
