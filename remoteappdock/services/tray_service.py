"""托盘宿主服务。

创建 Shell_TrayWnd 窗口，接收其他进程通过 WM_COPYDATA 发送的托盘图标消息。

本文件部分内容改编自 ManagedShell（Copyright (c) Cairo Shell 及贡献者，
https://github.com/cairoshell/ManagedShell），依据 Apache License 2.0 授权。
托盘协议处理与字段合并逻辑由 C# 移植为 Python，并已在此基础上修改。
Apache-2.0 许可全文见 third_party/ManagedShell/LICENSE，归属说明见项目根目录
NOTICE 文件。
"""

import ctypes
import logging
import queue
import threading
from ctypes import byref, cast, c_void_p, c_char, c_wchar, sizeof, POINTER, create_string_buffer

from PySide6.QtCore import QObject, QTimer, Signal

from remoteappdock.win32 import constants, api
from remoteappdock.win32.api import (
    SendMessageW, RegisterWindowMessageW, SendNotifyMessageW, FindWindowW,
    get_window_text, get_class_name,
)
from remoteappdock.win32.message_pump import Win32MessageThread
from remoteappdock.win32.wndproc import WndProcDispatcher
from remoteappdock.win32.structs import (
    COPYDATASTRUCT, SHELLTRAYDATA, NOTIFYICONDATA,
    GUID, LPPOINT, LPRECT,
    WINNOTIFYICONIDENTIFIER,
)
from remoteappdock.services.notification_area import NotificationArea
from remoteappdock.models.notify_icon import NotifyIcon
from remoteappdock.utils.icon_converter import IconConverter


logger = logging.getLogger(__name__)


class TrayService(QObject):
    """托盘宿主服务，负责创建 Shell_TrayWnd/TrayNotifyWnd 并解析 WM_COPYDATA。"""

    icon_event = Signal(object)  # 异步事件，通知主线程处理

    # Windows 系统托盘图标（SystemControlArea，音量/网络/电源/安全中心等）的
    # 固定 GUID（对照 ManagedShell NotificationArea 中的 *_GUID 常量）。
    # 这些系统图标由 Explorer/XAML 托管，本项目无法正确渲染与交互，全部过滤。
    _FILTERED_GUIDS = frozenset({
        "{7820AE73-23E3-4229-82C1-E41CB67D5B9C}",  # VOLUME     音量
        "{7820AE74-23E3-4229-82C1-E41CB67D5B9C}",  # NETWORK    网络
        "{7820AE75-23E3-4229-82C1-E41CB67D5B9C}",  # POWER      电源
        "{7820AE76-23E3-4229-82C1-E41CB67D5B9C}",  # HEALTH     Windows 安全中心
        "{7820AE77-23E3-4229-82C1-E41CB67D5B9C}",  # LOCATION   定位
        "{7820AE78-23E3-4229-82C1-E41CB67D5B9C}",  # HARDWARE   硬件安全删除
        "{7820AE81-23E3-4229-82C1-E41CB67D5B9C}",  # UPDATE     更新
        "{7820AE82-23E3-4229-82C1-E41CB67D5B9C}",  # MICROPHONE 麦克风
        "{7820AE83-23E3-4229-82C1-E41CB67D5B9C}",  # MEETNOW    立即开会
    })

    # 部分系统托盘图标（如 Windows 安全中心）并非通过固定 GUID 注册，而是由
    # 独立系统进程用普通 hWnd/uID 注册，GUID 过滤对其无效。改按创建图标的
    # 进程可执行名（小写）过滤。
    _FILTERED_PROCESSES = frozenset({
        "securityhealthsystray.exe",  # Windows 安全中心
    })

    def __init__(self, notification_area: NotificationArea, class_name: str | None = None):
        super().__init__()
        self._notification_area = notification_area
        self._class_name = class_name or constants.SHELL_TRAY_WND
        self._icon_converter = IconConverter()
        self._thread: Win32MessageThread | None = None
        self._notify_thread: Win32MessageThread | None = None
        self._hwnd: int = 0
        self._hwnd_notify: int = 0
        self._hwnd_fwd: int = 0
        self._dispatcher = WndProcDispatcher()
        self._event_queue: queue.Queue = queue.Queue()
        self._taskbar_created_msg: int = 0
        # 图标屏幕位置表（物理像素），供 WM_COPYDATA dwData==3 位置查询使用。
        # 由 UI 线程更新，Win32 线程读取；dict 的原子读写在 CPython 下线程安全。
        # key: (hWnd, uID) 或 guid 字符串；value: (left, top, right, bottom)
        self._icon_rects: dict = {}

        self._dispatcher.register(constants.WM_COPYDATA, self._on_copydata)
        self._dispatcher.register(constants.WM_DESTROY, self._on_destroy)
        self._dispatcher.register(constants.WM_WINDOWPOSCHANGED, self._on_windowposchanged)
        self._dispatcher.set_default_handler(self._on_default)

    def _on_default(self, hwnd, msg, wparam, lparam) -> int | None:
        """默认消息处理：对 COPYDATA/ACTIVATEAPP/COMMAND/>=WM_USER 的消息做转发。"""
        if msg == constants.WM_COPYDATA or msg == constants.WM_ACTIVATEAPP or msg == constants.WM_COMMAND or msg >= constants.WM_USER:
            return self._forward_msg(hwnd, msg, wparam, lparam)
        return None

    def start(self) -> None:
        """启动托盘宿主。"""
        self._taskbar_created_msg = RegisterWindowMessageW("TaskbarCreated")

        # 创建 Shell_TrayWnd。窗口需有实际尺寸（对齐 ManagedShell：屏幕宽 x 23），
        # 0x0 尺寸的窗口可能不被系统/部分程序识别为有效托盘宿主。
        screen_w = api.GetSystemMetrics(constants.SM_CXSCREEN)
        self._thread = Win32MessageThread(
            class_name=self._class_name,
            window_name="",
            wndproc=self._dispatcher.wndproc,
            style=constants.WS_POPUP | constants.WS_CLIPCHILDREN | constants.WS_CLIPSIBLINGS,
            ex_style=constants.WS_EX_TOPMOST | constants.WS_EX_TOOLWINDOW,
            register_class=True,
            x=0, y=0, width=screen_w, height=23,
        )
        self._thread.start()
        self._hwnd = self._thread.hwnd
        logger.info("Shell_TrayWnd 已创建: hwnd=0x%X", self._hwnd)

        # 创建 TrayNotifyWnd 子窗口，使系统认为我们是合法任务栏
        self._notify_thread = Win32MessageThread(
            class_name=constants.TRAY_NOTIFY_WND,
            window_name="",
            wndproc=self._dispatcher.wndproc,
            style=constants.WS_CHILD | constants.WS_CLIPCHILDREN | constants.WS_CLIPSIBLINGS,
            ex_style=0,
            parent=self._hwnd,
            register_class=True,
            x=0, y=0, width=screen_w, height=23,
        )
        self._notify_thread.start()
        self._hwnd_notify = self._notify_thread.hwnd
        logger.info("TrayNotifyWnd 已创建: hwnd=0x%X", self._hwnd_notify)

        # 把 Explorer 的任务栏沉到底，让系统选择我们的 Shell_TrayWnd
        self._set_explorer_tray_bottommost()

        # 发送 TaskbarCreated 广播，让托盘图标重新注册。
        # 必须使用 SendNotifyMessage（对齐 ManagedShell），PostMessage 对
        # RegisterWindowMessage 广播不可靠，部分现代程序（如微信）收不到。
        if self._taskbar_created_msg:
            SendNotifyMessageW(constants.HWND_BROADCAST, self._taskbar_created_msg, 0, 0)
            logger.info("已发送 TaskbarCreated 广播")

        # 定时确保我们的 Shell_TrayWnd 位于顶层
        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(self._ensure_topmost)
        self._topmost_timer.start(100)

    def stop(self) -> None:
        """停止托盘宿主。"""
        if self._topmost_timer is not None:
            self._topmost_timer.stop()
            self._topmost_timer = None
        if self._notify_thread is not None:
            self._notify_thread.stop()
            self._notify_thread = None
            self._hwnd_notify = 0
        if self._thread is not None:
            self._thread.stop()
            self._thread = None
            self._hwnd = 0
        self._notification_area.clear()

    def _set_explorer_tray_bottommost(self) -> None:
        """将 Explorer 的 Shell_TrayWnd 沉到 Z 顺序底部。"""
        hwnd = api.FindWindowW(constants.SHELL_TRAY_WND, None)
        while hwnd:
            if hwnd != self._hwnd:
                api.SetWindowPos(
                    hwnd, constants.HWND_BOTTOM, 0, 0, 0, 0,
                    constants.SWP_NOMOVE | constants.SWP_NOSIZE | constants.SWP_NOACTIVATE
                )
                logger.debug("将 Explorer Shell_TrayWnd(%#x) 沉到底", hwnd)
            hwnd = api.FindWindowExW(0, hwnd, constants.SHELL_TRAY_WND, None)

    def _ensure_topmost(self) -> None:
        """保持我们的 Shell_TrayWnd 在最顶层，确保接收托盘消息。"""
        if not self._hwnd or not api.IsWindow(self._hwnd):
            return

        # 如果当前最顶层的 Shell_TrayWnd 不是我们，重新置顶
        top = api.FindWindowW(constants.SHELL_TRAY_WND, None)
        if top and top != self._hwnd:
            self._set_explorer_tray_bottommost()

        api.SetWindowPos(
            self._hwnd, constants.HWND_TOPMOST, 0, 0, 0, 0,
            constants.SWP_NOMOVE | constants.SWP_NOSIZE | constants.SWP_NOACTIVATE | constants.SWP_SHOWWINDOW
        )

    # 触发菜单的鼠标消息：转发前需允许目标进程抢占前台，否则弹出的菜单
    # 不会获得焦点，导致点击别处时菜单不消失（对齐 ManagedShell IconMouseDown）。
    _MENU_TRIGGER_MSGS = frozenset({
        constants.WM_LBUTTONDOWN, constants.WM_LBUTTONUP,
        constants.WM_RBUTTONDOWN, constants.WM_RBUTTONUP,
        constants.WM_MBUTTONDOWN, constants.WM_MBUTTONUP,
        constants.WM_CONTEXTMENU, constants.WM_LBUTTONDBLCLK,
        constants.NIN_SELECT, constants.NIN_KEYSELECT,
    })

    def forward_mouse_event(self, hWnd: int, uID: int, callback_message: int, msg: int,
                            mouse: int = 0, version: int = 0) -> bool:
        """将鼠标事件转发给托盘图标的原窗口。

        托盘回调消息格式随图标注册的 NOTIFYICON_VERSION 而不同
        （对齐 ManagedShell NotifyIcon.SendMessage）：

          version > 3（NOTIFYICON_VERSION_4）：
            wParam = 光标屏幕坐标，LOWORD=x、HIWORD=y（物理像素）
            lParam = 鼠标消息 | (uID << 16)
          version <= 3（旧版）：
            wParam = uID
            lParam = 鼠标消息

        `mouse` 为已打包的光标坐标 (x & 0xFFFF) | (y << 16)。version>3 的图标
        依赖 wParam 中的坐标来定位右键菜单；旧实现始终传 wParam=uID，导致
        version 4 图标把 uID 当坐标解析（y 恒为 0，菜单弹到屏幕顶部）。
        """
        if hWnd == 0 or callback_message == 0:
            return False
        # 允许图标所属进程将其菜单窗口设为前台，确保菜单能正常获得焦点/关闭。
        if msg in self._MENU_TRIGGER_MSGS:
            try:
                pid = api.get_window_process_id(hWnd)
                if pid:
                    api.AllowSetForegroundWindow(pid)
            except Exception:
                logger.debug("AllowSetForegroundWindow 失败: hWnd=0x%X", hWnd)

        if version > 3:
            wParam = mouse & 0xFFFFFFFF
            lParam = (msg & 0xFFFF) | ((uID & 0xFFFF) << 16)
        else:
            wParam = uID
            lParam = msg
        # 必须用 SendNotifyMessage（对齐 ManagedShell NotifyIcon.SendMessage）。
        # Explorer 派发托盘回调用的是 sent 语义而非 posted：部分程序只处理
        # SendNotifyMessage 投递的回调，用 PostMessage 会被直接忽略，表现为
        # 点击/右键无反应（RDP 下时序变化时尤为明显）。
        return bool(SendNotifyMessageW(hWnd, callback_message, wParam, lParam))

    def forward_select_event(self, hWnd: int, uID: int, callback_message: int) -> bool:
        """转发左键选择（NIN_SELECT）。"""
        return self.forward_mouse_event(hWnd, uID, callback_message, constants.NIN_SELECT)

    def forward_keyselect_event(self, hWnd: int, uID: int, callback_message: int) -> bool:
        """转发键盘选择（NIN_KEYSELECT）。"""
        return self.forward_mouse_event(hWnd, uID, callback_message, constants.NIN_KEYSELECT)

    def drain_events(self) -> list:
        """主线程调用，消费 Win32 线程产生的事件。"""
        events = []
        while True:
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def process_events(self) -> None:
        """处理所有待处理事件。"""
        for event in self.drain_events():
            try:
                self._process_event(event)
            except Exception:
                logger.exception("处理托盘事件失败: %s", event)

    def _on_copydata(self, hwnd, msg, wparam, lparam) -> int:
        """WndProc 中处理 WM_COPYDATA。"""
        try:
            cds = cast(lparam, POINTER(COPYDATASTRUCT)).contents
            if cds.dwData == 1:
                self._parse_shelltraydata(cds)
                return 1
            elif cds.dwData == 3:
                return self._parse_icon_identifier(cds)
            elif cds.dwData == 0:
                # AppBar 消息：转发给 Explorer 处理
                result = self._forward_msg(hwnd, msg, wparam, lparam)
                if result is not None:
                    return result
            else:
                logger.debug("未知 WM_COPYDATA dwData: %d", cds.dwData)
        except Exception:
            logger.exception("解析 WM_COPYDATA 失败")
        return 1  # TRUE

    def _parse_shelltraydata(self, cds: COPYDATASTRUCT) -> None:
        """解析 COPYDATASTRUCT 中的 SHELLTRAYDATA。"""
        if cds.cbData < sizeof(SHELLTRAYDATA):
            return

        tray_data = cast(cds.lpData, POINTER(SHELLTRAYDATA)).contents
        # 注意：dwUnknown 不是固定魔数，ManagedShell 不做校验，此处同样直接解析。

        # SHELLTRAYDATA 后紧跟 NOTIFYICONDATA（Unicode，固定 32 位句柄布局）。
        data_addr = ctypes.addressof(tray_data) + sizeof(SHELLTRAYDATA)
        nid = cast(data_addr, POINTER(NOTIFYICONDATA)).contents
        # 关键：nid 指向 WM_COPYDATA 的临时缓冲区，消息返回后即失效。
        # 必须在此处（缓冲区仍有效时）立即解析为 NotifyIcon，再入队，
        # 不能把指向临时缓冲区的 nid 传给稍后在主线程运行的处理逻辑。
        icon = self._icon_from_notify_icon_data(nid)
        version = nid.uVersion
        self._queue_icon_event(tray_data.dwMessage, icon, version)

    def _parse_icon_identifier(self, cds: COPYDATASTRUCT) -> int:
        """解析 WINNOTIFYICONIDENTIFIER（dwData == 3），返回图标屏幕位置。

        系统/程序弹出托盘菜单前会通过此消息查询图标矩形（物理像素）：
          dwMessage==1 -> 返回矩形左上角 (left, top)
          dwMessage==2 -> 返回矩形右下角 (right, bottom)
        返回值打包为 LPARAM：低 16 位 = x，高 16 位 = y。
        对齐 ManagedShell NotificationArea.IconDataCallback。
        """
        if cds.cbData < sizeof(WINNOTIFYICONIDENTIFIER):
            return 0
        identifier = cast(cds.lpData, POINTER(WINNOTIFYICONIDENTIFIER)).contents

        guid = self._guid_to_string(identifier.guidItem)
        rect = self._icon_rects.get(guid) if guid else None
        if rect is None:
            rect = self._icon_rects.get((identifier.hWnd, identifier.uID))
        if rect is None:
            logger.debug("位置查询未命中: hwnd=0x%X uID=%d guid=%s",
                         identifier.hWnd, identifier.uID, guid)
            return 0

        left, top, right, bottom = rect
        if identifier.dwMessage == 2:
            result = self._make_lparam(right, bottom)
            logger.debug("位置查询命中(右下): dwMessage=%d rect=%s -> lparam=0x%X",
                         identifier.dwMessage, rect, result & 0xFFFFFFFF)
        else:
            result = self._make_lparam(left, top)
            logger.debug("位置查询命中(左上): dwMessage=%d rect=%s -> lparam=0x%X",
                         identifier.dwMessage, rect, result & 0xFFFFFFFF)
        return result

    @staticmethod
    def _make_lparam(lo: int, hi: int) -> int:
        """打包坐标为 LPARAM：低 16 位 x，高 16 位 y（有符号截断，对齐 ManagedShell）。"""
        return ((int(hi) & 0xFFFF) << 16) | (int(lo) & 0xFFFF)

    def update_icon_rect(self, hWnd: int, uID: int, guid, rect) -> None:
        """UI 线程调用：更新图标的屏幕矩形（物理像素）。

        rect: (left, top, right, bottom)
        """
        self._icon_rects[(hWnd, uID)] = rect
        if guid:
            self._icon_rects[guid] = rect

    def remove_icon_rect(self, hWnd: int, uID: int, guid=None) -> None:
        """UI 线程调用：移除图标位置记录。"""
        self._icon_rects.pop((hWnd, uID), None)
        if guid:
            self._icon_rects.pop(guid, None)

    def _on_destroy(self, hwnd, msg, wparam, lparam) -> int | None:
        logger.info("Shell_TrayWnd 收到 WM_DESTROY")
        return None

    def _on_windowposchanged(self, hwnd, msg, wparam, lparam) -> int | None:
        """当 Shell_TrayWnd 被显示时移除 WS_VISIBLE 样式，保持隐藏。"""
        from ctypes import cast, POINTER
        from remoteappdock.win32.structs import WINDOWPOS
        try:
            wnd_pos = cast(lparam, POINTER(WINDOWPOS)).contents
            if wnd_pos.flags & constants.SWP_SHOWWINDOW:
                style = api.GetWindowLongPtrW(self._hwnd, constants.GWL_STYLE)
                if style & constants.WS_VISIBLE:
                    api.SetWindowLongPtrW(
                        self._hwnd, constants.GWL_STYLE,
                        style & ~constants.WS_VISIBLE
                    )
                    logger.debug("Shell_TrayWnd 被显示，已移除 WS_VISIBLE")
        except Exception:
            logger.exception("处理 WM_WINDOWPOSCHANGED 失败")
        return None

    def _forward_msg(self, hwnd, msg, wparam, lparam) -> int | None:
        """将未处理消息转发给 Explorer 的 Shell_TrayWnd（如果存在）。"""
        if not self._hwnd_fwd or not api.IsWindow(self._hwnd_fwd):
            self._hwnd_fwd = api.FindWindowW(constants.SHELL_TRAY_WND, None)
            if self._hwnd_fwd == self._hwnd:
                self._hwnd_fwd = api.FindWindowExW(0, self._hwnd, constants.SHELL_TRAY_WND, None)
        if not self._hwnd_fwd:
            return None
        try:
            result = SendMessageW(self._hwnd_fwd, msg, wparam, lparam)
            return result
        except Exception:
            logger.exception("转发消息 0x%04X 失败", msg)
        return None

    def _queue_icon_event(self, message: int, icon: NotifyIcon, version: int) -> None:
        """将已解析的图标事件放入队列，供主线程处理。

        icon 必须是已从临时缓冲区拷贝出来的 NotifyIcon（不含指向临时内存的引用）。
        """
        self._event_queue.put((message, icon, version))
        self.icon_event.emit((message, icon, version))

    def _process_event(self, event: tuple) -> None:
        """主线程处理图标事件。"""
        message, icon, version = event

        # 过滤系统托盘图标（如音量）：Win11 下无法正确接管，直接丢弃其增删改事件。
        if icon.guid and icon.guid.upper() in self._FILTERED_GUIDS:
            logger.debug("过滤系统托盘图标(GUID): guid=%s title=%r", icon.guid, icon.title)
            return

        # 按创建进程可执行名过滤（如 Windows 安全中心，不走 GUID 注册）。
        if icon.hWnd and self._FILTERED_PROCESSES:
            try:
                image_path = api.get_process_image_path(icon.hWnd)
                if image_path:
                    exe_name = image_path.rsplit("\\", 1)[-1].lower()
                    if exe_name in self._FILTERED_PROCESSES:
                        logger.debug("过滤系统托盘图标(进程): exe=%s title=%r",
                                     exe_name, icon.title)
                        return
            except Exception:
                logger.debug("获取托盘图标进程名失败: hWnd=0x%X", icon.hWnd, exc_info=True)

        # 有效性过滤（对照 ManagedShell SysTrayCallback）：
        # 新增/修改图标必须有有效的窗口句柄（或 GUID），否则视为无效数据丢弃。
        if message in (constants.NIM_ADD, constants.NIM_MODIFY):
            has_guid = bool(icon.guid)
            if not icon.hWnd or not api.IsWindow(icon.hWnd):
                if not has_guid or message == constants.NIM_ADD:
                    logger.debug("忽略无效托盘图标: hWnd=0x%X uID=%d title=%r",
                                 icon.hWnd or 0, icon.uID, icon.title)
                    return

        if message == constants.NIM_ADD:
            self._notification_area.add_icon(icon)
        elif message == constants.NIM_MODIFY:
            self._notification_area.modify_icon(icon)
        elif message == constants.NIM_DELETE:
            self._notification_area.remove_icon(icon.hWnd, icon.uID, icon.guid)
        elif message == constants.NIM_SETVERSION:
            self._notification_area.set_version(icon.hWnd, icon.uID, version)
        elif message == constants.NIM_SETFOCUS:
            pass
        else:
            logger.warning("未知的 NIM 消息: %d", message)

    def _icon_from_notify_icon_data(self, nid: NOTIFYICONDATA) -> NotifyIcon:
        """从 NOTIFYICONDATA 创建模型。

        仅在对应 uFlags 位有效时才填充字段，避免用未设置的字段覆盖已有值。
        字段合并逻辑对照 ManagedShell NotificationArea.SysTrayCallback。
        """
        icon = NotifyIcon(hWnd=nid.hWnd, uID=nid.uID)
        icon.uflags = nid.uFlags

        if nid.uFlags & constants.NIF_TIP and nid.szTip:
            icon.title = nid.szTip
        if nid.uFlags & constants.NIF_MESSAGE:
            icon.callback_message = nid.uCallbackMessage
        if nid.uFlags & constants.NIF_ICON:
            icon.hicon = nid.hIcon
        if nid.uFlags & constants.NIF_STATE:
            icon.is_hidden = bool(nid.dwState & constants.NIS_HIDDEN)
        if nid.uFlags & constants.NIF_GUID:
            icon.guid = self._guid_to_string(nid.guidItem)
        return icon

    @staticmethod
    def _guid_to_string(guid: GUID) -> str:
        """将 GUID 结构体转为字符串。"""
        if not guid.Data1:
            return ""
        return str(guid)
