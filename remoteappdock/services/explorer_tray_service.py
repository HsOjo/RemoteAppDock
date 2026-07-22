"""Explorer 托盘图标枚举服务。

程序启动前就已注册的托盘图标（音量、网络、OneDrive、微信、输入法等）不会
通过 TaskbarCreated 广播重新注册，必须主动枚举 Explorer 现有的托盘工具栏。

实现方式对照 ManagedShell ExplorerTrayService：
定位 Shell_TrayWnd > TrayNotifyWnd > SysPager > ToolbarWindow32，
通过 TB_BUTTONCOUNT / TB_GETBUTTON 跨进程读取每个按钮的 TRAYITEM 数据。
"""

import ctypes
import logging
from ctypes import byref, sizeof, cast, POINTER, c_size_t

from remoteappdock.win32 import api, constants
from remoteappdock.win32.structs import TBBUTTON, TRAYITEM, GUID
from remoteappdock.models.notify_icon import NotifyIcon


logger = logging.getLogger(__name__)


class ExplorerTrayService:
    """枚举 Explorer 现有托盘图标，补齐启动前已注册的常驻图标。"""

    def __init__(self, notification_area):
        self._notification_area = notification_area

    def run(self) -> int:
        """枚举一次 Explorer 托盘图标，返回成功导入的数量。"""
        try:
            return self._get_tray_items()
        except Exception:
            logger.exception("枚举 Explorer 托盘图标失败")
            return 0

    def _find_toolbar_hwnd(self) -> int:
        """定位 Explorer 托盘工具栏窗口。

        路径：Shell_TrayWnd > TrayNotifyWnd > SysPager > ToolbarWindow32。
        """
        hwnd = api.FindWindowW(constants.SHELL_TRAY_WND, None)
        if not hwnd:
            return 0
        hwnd = api.FindWindowExW(hwnd, 0, constants.TRAY_NOTIFY_WND, None)
        if not hwnd:
            return 0
        hwnd = api.FindWindowExW(hwnd, 0, "SysPager", None)
        if not hwnd:
            return 0
        return api.FindWindowExW(hwnd, 0, "ToolbarWindow32", None) or 0

    def _get_num_icons(self, toolbar_hwnd: int) -> int:
        """获取工具栏按钮数量。"""
        return int(api.SendMessageW(toolbar_hwnd, constants.TB_BUTTONCOUNT, 0, 0))

    def _get_tray_items(self) -> int:
        """枚举工具栏所有按钮并导入图标。"""
        toolbar_hwnd = self._find_toolbar_hwnd()
        if not toolbar_hwnd:
            # Win11 已移除传统 ToolbarWindow32 托盘，此为预期情况，非错误。
            logger.debug("未找到 Explorer 托盘工具栏（ToolbarWindow32），跳过枚举")
            return 0

        count = self._get_num_icons(toolbar_hwnd)
        if count < 1:
            logger.info("Explorer 托盘工具栏按钮数为 0")
            return 0

        pid = api.get_window_process_id(toolbar_hwnd)
        h_process = api.OpenProcess(constants.PROCESS_ALL_ACCESS, False, pid)
        if not h_process:
            logger.warning("无法打开 Explorer 进程（pid=%d），跳过枚举", pid)
            return 0

        # 在目标进程中分配缓冲区用于接收 TB_GETBUTTON 写回的 TBBUTTON
        remote_buf = api.VirtualAllocEx(
            h_process, None, sizeof(TBBUTTON),
            constants.MEM_COMMIT, constants.PAGE_READWRITE,
        )
        if not remote_buf:
            logger.warning("在 Explorer 进程分配内存失败")
            api.CloseHandle(h_process)
            return 0

        imported = 0
        try:
            for i in range(count):
                item = self._read_tray_item(i, toolbar_hwnd, h_process, remote_buf)
                if item is None:
                    continue
                if not item.hWnd or not api.IsWindow(item.hWnd):
                    logger.debug("忽略无效句柄的托盘项: %s", item.szIconText)
                    continue
                self._import_icon(item)
                imported += 1
        finally:
            api.VirtualFreeEx(h_process, remote_buf, 0, constants.MEM_RELEASE)
            api.CloseHandle(h_process)

        logger.info("从 Explorer 枚举到 %d 个托盘图标（共 %d 个按钮）", imported, count)
        return imported

    def _read_tray_item(self, index: int, toolbar_hwnd: int, h_process: int, remote_buf: int):
        """读取第 index 个按钮对应的 TRAYITEM。"""
        # 让 Explorer 把第 index 个 TBBUTTON 写入目标进程的 remote_buf
        api.SendMessageW(toolbar_hwnd, constants.TB_GETBUTTON, index, remote_buf)

        tb_button = TBBUTTON()
        read = c_size_t(0)
        ok = api.ReadProcessMemory(
            h_process, remote_buf, byref(tb_button), sizeof(TBBUTTON), byref(read),
        )
        if not ok or not tb_button.dwData:
            return None

        # TBBUTTON.dwData 指向目标进程中的 TRAYITEM
        tray_item = TRAYITEM()
        ok = api.ReadProcessMemory(
            h_process, tb_button.dwData, byref(tray_item), sizeof(TRAYITEM), byref(read),
        )
        if not ok:
            return None

        # 隐藏状态：fsState 含 TBSTATE_HIDDEN
        tray_item.dwState = 1 if (tb_button.fsState & constants.TBSTATE_HIDDEN) else 0
        return tray_item

    def _import_icon(self, item: TRAYITEM) -> None:
        """将 TRAYITEM 转为 NotifyIcon 并加入通知区域。"""
        icon = NotifyIcon(
            hWnd=item.hWnd or 0,
            uID=item.uID,
            title=item.szIconText or "",
            callback_message=item.uCallbackMessage,
            version=item.uVersion,
            hicon=item.hIcon or 0,
            is_hidden=bool(item.dwState),
        )
        guid_str = self._guid_to_string(item.guidItem)
        if guid_str:
            icon.guid = guid_str
        self._notification_area.add_icon(icon)
        logger.debug(
            "导入 Explorer 托盘图标: title=%s hWnd=0x%X uID=%d version=%d guid=%s",
            icon.title, icon.hWnd, icon.uID, icon.version, guid_str,
        )

    @staticmethod
    def _guid_to_string(guid: GUID) -> str:
        """将 GUID 结构体转为字符串。"""
        if not guid.Data1 and not any(guid.Data4):
            return ""
        return str(guid)
