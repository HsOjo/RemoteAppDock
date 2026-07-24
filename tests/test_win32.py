import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 平台支持")

if sys.platform == "win32":
    from remoteappdock.win32 import constants, structs
    from remoteappdock.win32.message_pump import Win32MessageThread


def test_notify_icon_data_size():
    """验证 NOTIFYICONDATA 结构体大小（64 位布局，用于解析 WM_COPYDATA）。"""
    assert structs.sizeof(structs.NOTIFYICONDATA) == 956
    assert structs.sizeof(structs.NOTIFYICONDATAA) == 508


def test_appbar_data_size():
    """验证 APPBARDATA 结构体大小。"""
    assert structs.sizeof(structs.APPBARDATA) == 40


def test_copydata_struct_size():
    """验证 COPYDATASTRUCT 结构体大小。"""
    assert structs.sizeof(structs.COPYDATASTRUCT) == 24


def test_guid_size():
    """验证 GUID 结构体大小。"""
    assert structs.sizeof(structs.GUID) == 16


def test_message_pump_can_create_window():
    """验证 Win32 消息泵能在线程中创建窗口并接收消息。"""
    thread = Win32MessageThread(window_name="TestMessagePump")
    thread.start()
    assert thread.hwnd != 0

    # 发送一条自定义 WM_USER 消息验证窗口存活
    result = thread.post_message(thread.hwnd, constants.WM_USER, 123, 456)
    assert result is True

    thread.stop()
    assert thread.hwnd == 0
