import sys

import pytest

from PySide6.QtCore import QCoreApplication

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 平台支持")

if sys.platform == "win32":
    import ctypes
    from ctypes import byref, cast, sizeof, create_string_buffer
    from remoteappdock.win32 import constants, api
    from remoteappdock.win32.api import SendMessageW, PostMessageW, FindWindowW
    from remoteappdock.win32.structs import COPYDATASTRUCT, SHELLTRAYDATA, NOTIFYICONDATA, GUID
    from remoteappdock.services.notification_area import NotificationArea
    from remoteappdock.services.tray_service import TrayService


@pytest.fixture
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_tray_service_receives_copydata(qt_app):
    """验证 TrayService 能接收并解析 WM_COPYDATA 托盘图标消息。"""
    notification_area = NotificationArea()
    # 使用唯一类名，避免与其他测试或 Explorer 的 Shell_TrayWnd 冲突
    tray_service = TrayService(notification_area, class_name="RemoteAppDockTestTray_1")
    tray_service.start()

    try:
        hwnd = tray_service._hwnd
        assert hwnd != 0

        # 构造 NOTIFYICONDATA。使用真实窗口句柄（托盘服务自身的 hwnd），
        # 以通过有效性过滤（对无效窗口句柄的图标会被丢弃）。
        nid = NOTIFYICONDATA()
        nid.cbSize = sizeof(NOTIFYICONDATA)
        nid.hWnd = hwnd
        nid.uID = 42
        nid.uFlags = constants.NIF_ICON | constants.NIF_TIP | constants.NIF_MESSAGE
        nid.uCallbackMessage = constants.WM_USER + 1
        nid.szTip = "Test Icon"

        # 构造 SHELLTRAYDATA
        total_size = sizeof(SHELLTRAYDATA) + sizeof(NOTIFYICONDATA)
        buffer = create_string_buffer(total_size)
        tray_data = cast(buffer, ctypes.POINTER(SHELLTRAYDATA)).contents
        tray_data.dwMessage = constants.NIM_ADD
        ctypes.memmove(
            ctypes.addressof(buffer) + sizeof(SHELLTRAYDATA),
            ctypes.byref(nid),
            sizeof(NOTIFYICONDATA),
        )

        cds = COPYDATASTRUCT()
        cds.dwData = 1
        cds.cbData = total_size
        cds.lpData = cast(buffer, ctypes.c_void_p)

        result = SendMessageW(hwnd, constants.WM_COPYDATA, 0, ctypes.cast(ctypes.byref(cds), ctypes.c_void_p).value)
        assert result == 1

        # 处理事件
        tray_service.process_events()

        icons = notification_area.get_icons()
        assert len(icons) == 1
        icon = icons[0]
        assert icon.hWnd == hwnd
        assert icon.uID == 42
        assert icon.title == "Test Icon"
    finally:
        tray_service.stop()
