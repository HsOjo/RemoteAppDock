"""Win32 API 封装。"""

import ctypes
from ctypes import WINFUNCTYPE, c_void_p, c_int, c_uint, c_long, c_ulong, c_longlong, c_ulonglong, c_short, c_ushort, c_byte, c_bool, c_char, c_wchar, POINTER, cast, pointer, sizeof, byref
from ctypes.wintypes import HWND, UINT, DWORD, ULONG, LONG, WORD, BYTE, BOOL, LPVOID, LPCVOID, LPWSTR, LPCWSTR, LPSTR, LPCSTR, RECT, POINT, MSG, COLORREF

# ctypes.wintypes 中部分句柄类型未定义，使用通用句柄别名
HANDLE = c_void_p
HINSTANCE = HANDLE
HICON = HANDLE
HCURSOR = HANDLE
HBRUSH = HANDLE
HMENU = HANDLE
HGLOBAL = HANDLE
HDC = HANDLE
HBITMAP = HANDLE
HRGN = HANDLE
HMODULE = HANDLE
HWND = HANDLE

from remoteappdock.win32 import structs
from remoteappdock.win32.structs import (
    COPYDATASTRUCT, SHELLTRAYDATA, NOTIFYICONDATA, NOTIFYICONDATAA,
    WINNOTIFYICONIDENTIFIER, APPBARDATA, APPBARMSGDATAV3, SHELLHOOKINFO,
    TBBUTTON, TRAYITEM, WNDCLASSW, WNDCLASSEXW, WINDOWPOS, MSG, MINMAXINFO,
    NMHDR, SHFILEINFO, GUITHREADINFO, MONITORINFO, ICONINFO, BITMAPINFO,
    SECURITY_ATTRIBUTES, GUID, POINT, RECT
)
from remoteappdock.win32 import constants

# 加载 DLL
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
dwmapi = ctypes.windll.dwmapi
gdi32 = ctypes.windll.gdi32
ole32 = ctypes.windll.ole32
comctl32 = ctypes.windll.comctl32

# 通用回调类型
WNDPROC = WINFUNCTYPE(c_longlong, HWND, UINT, c_ulonglong, c_longlong)
ENUMWINDOWSPROC = WINFUNCTYPE(BOOL, HWND, c_longlong)
WINEVENTPROC = WINFUNCTYPE(None, HANDLE, DWORD, HWND, LONG, LONG, DWORD, DWORD)


# ===== user32 =====

# 窗口类
RegisterClassW = user32.RegisterClassW
RegisterClassW.argtypes = [POINTER(WNDCLASSW)]
RegisterClassW.restype = c_ushort

RegisterClassExW = user32.RegisterClassExW
RegisterClassExW.argtypes = [POINTER(WNDCLASSEXW)]
RegisterClassExW.restype = c_ushort

UnregisterClassW = user32.UnregisterClassW
UnregisterClassW.argtypes = [LPCWSTR, HINSTANCE]
UnregisterClassW.restype = BOOL

# 窗口创建/销毁
CreateWindowExW = user32.CreateWindowExW
CreateWindowExW.argtypes = [DWORD, LPCWSTR, LPCWSTR, DWORD, c_int, c_int, c_int, c_int, HWND, HMENU, HINSTANCE, LPVOID]
CreateWindowExW.restype = HWND

DestroyWindow = user32.DestroyWindow
DestroyWindow.argtypes = [HWND]
DestroyWindow.restype = BOOL

DefWindowProcW = user32.DefWindowProcW
DefWindowProcW.argtypes = [HWND, UINT, c_ulonglong, c_longlong]
DefWindowProcW.restype = c_longlong

# 消息
GetMessageW = user32.GetMessageW
GetMessageW.argtypes = [POINTER(MSG), HWND, UINT, UINT]
GetMessageW.restype = c_int

DispatchMessageW = user32.DispatchMessageW
DispatchMessageW.argtypes = [POINTER(MSG)]
DispatchMessageW.restype = c_longlong

TranslateMessage = user32.TranslateMessage
TranslateMessage.argtypes = [POINTER(MSG)]
TranslateMessage.restype = BOOL

PeekMessageW = user32.PeekMessageW
PeekMessageW.argtypes = [POINTER(MSG), HWND, UINT, UINT, UINT]
PeekMessageW.restype = BOOL

PostMessageW = user32.PostMessageW
PostMessageW.argtypes = [HWND, UINT, c_ulonglong, c_longlong]
PostMessageW.restype = BOOL

PostThreadMessageW = user32.PostThreadMessageW
PostThreadMessageW.argtypes = [DWORD, UINT, c_ulonglong, c_longlong]
PostThreadMessageW.restype = BOOL

SendMessageW = user32.SendMessageW
SendMessageW.argtypes = [HWND, UINT, c_ulonglong, c_longlong]
SendMessageW.restype = c_longlong

SendMessageTimeoutW = user32.SendMessageTimeoutW
SendMessageTimeoutW.argtypes = [HWND, UINT, c_ulonglong, c_longlong, UINT, UINT, POINTER(c_ulonglong)]
SendMessageTimeoutW.restype = c_longlong

SendNotifyMessageW = user32.SendNotifyMessageW
SendNotifyMessageW.argtypes = [HWND, UINT, c_ulonglong, c_longlong]
SendNotifyMessageW.restype = BOOL

RegisterWindowMessageW = user32.RegisterWindowMessageW
RegisterWindowMessageW.argtypes = [LPCWSTR]
RegisterWindowMessageW.restype = UINT

SystemParametersInfoW = user32.SystemParametersInfoW
SystemParametersInfoW.argtypes = [UINT, UINT, LPVOID, UINT]
SystemParametersInfoW.restype = BOOL

# 事件钩子
SetWinEventHook = user32.SetWinEventHook
SetWinEventHook.argtypes = [DWORD, DWORD, HMODULE, c_void_p, DWORD, DWORD, DWORD]
SetWinEventHook.restype = HANDLE

UnhookWinEvent = user32.UnhookWinEvent
UnhookWinEvent.argtypes = [HANDLE]
UnhookWinEvent.restype = BOOL

RegisterShellHookWindow = user32.RegisterShellHookWindow
RegisterShellHookWindow.argtypes = [HWND]
RegisterShellHookWindow.restype = BOOL

DeregisterShellHookWindow = user32.DeregisterShellHookWindow
DeregisterShellHookWindow.argtypes = [HWND]
DeregisterShellHookWindow.restype = BOOL

SetWindowsHookExW = user32.SetWindowsHookExW
SetWindowsHookExW.argtypes = [c_int, c_void_p, HINSTANCE, DWORD]
SetWindowsHookExW.restype = HANDLE

UnhookWindowsHookEx = user32.UnhookWindowsHookEx
UnhookWindowsHookEx.argtypes = [HANDLE]
UnhookWindowsHookEx.restype = BOOL

CallNextHookEx = user32.CallNextHookEx
CallNextHookEx.argtypes = [HANDLE, c_int, c_ulonglong, c_longlong]
CallNextHookEx.restype = c_longlong

# 窗口查询/枚举
EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [ENUMWINDOWSPROC, c_longlong]
EnumWindows.restype = BOOL

IsWindow = user32.IsWindow
IsWindow.argtypes = [HWND]
IsWindow.restype = BOOL

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [HWND]
IsWindowVisible.restype = BOOL

IsWindowEnabled = user32.IsWindowEnabled
IsWindowEnabled.argtypes = [HWND]
IsWindowEnabled.restype = BOOL

IsIconic = user32.IsIconic
IsIconic.argtypes = [HWND]
IsIconic.restype = BOOL

IsZoomed = user32.IsZoomed
IsZoomed.argtypes = [HWND]
IsZoomed.restype = BOOL

GetWindow = user32.GetWindow
GetWindow.argtypes = [HWND, UINT]
GetWindow.restype = HWND

GetParent = user32.GetParent
GetParent.argtypes = [HWND]
GetParent.restype = HWND

GetAncestor = user32.GetAncestor
GetAncestor.argtypes = [HWND, UINT]
GetAncestor.restype = HWND

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [HWND, LPWSTR, c_int]
GetWindowTextW.restype = c_int

GetClassNameW = user32.GetClassNameW
GetClassNameW.argtypes = [HWND, LPWSTR, c_int]
GetClassNameW.restype = c_int

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [HWND, POINTER(DWORD)]
GetWindowThreadProcessId.restype = DWORD

FindWindowW = user32.FindWindowW
FindWindowW.argtypes = [LPCWSTR, LPCWSTR]
FindWindowW.restype = HWND

FindWindowExW = user32.FindWindowExW
FindWindowExW.argtypes = [HWND, HWND, LPCWSTR, LPCWSTR]
FindWindowExW.restype = HWND

GetPropW = user32.GetPropW
GetPropW.argtypes = [HWND, LPCWSTR]
GetPropW.restype = HANDLE

SetPropW = user32.SetPropW
SetPropW.argtypes = [HWND, LPCWSTR, HANDLE]
SetPropW.restype = BOOL

RemovePropW = user32.RemovePropW
RemovePropW.argtypes = [HWND, LPCWSTR]
RemovePropW.restype = HANDLE

SetTaskmanWindow = user32.SetTaskmanWindow
SetTaskmanWindow.argtypes = [HWND]
SetTaskmanWindow.restype = HWND

# 窗口样式/属性
GetWindowLongPtrW = user32.GetWindowLongPtrW
GetWindowLongPtrW.argtypes = [HWND, c_int]
GetWindowLongPtrW.restype = c_longlong

SetWindowLongPtrW = user32.SetWindowLongPtrW
SetWindowLongPtrW.argtypes = [HWND, c_int, c_longlong]
SetWindowLongPtrW.restype = c_longlong

SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [HWND, HWND, c_int, c_int, c_int, c_int, UINT]
SetWindowPos.restype = BOOL

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [HWND, c_int]
ShowWindow.restype = BOOL

UpdateWindow = user32.UpdateWindow
UpdateWindow.argtypes = [HWND]
UpdateWindow.restype = BOOL

SetWindowTextW = user32.SetWindowTextW
SetWindowTextW.argtypes = [HWND, LPCWSTR]
SetWindowTextW.restype = BOOL

GetWindowRect = user32.GetWindowRect
GetWindowRect.argtypes = [HWND, POINTER(RECT)]
GetWindowRect.restype = BOOL

GetClientRect = user32.GetClientRect
GetClientRect.argtypes = [HWND, POINTER(RECT)]
GetClientRect.restype = BOOL

SetWindowRgn = user32.SetWindowRgn
SetWindowRgn.argtypes = [HWND, HRGN, BOOL]
SetWindowRgn.restype = c_int

GetWindowRgn = user32.GetWindowRgn
GetWindowRgn.argtypes = [HWND, HRGN]
GetWindowRgn.restype = c_int

GetWindowPlacement = user32.GetWindowPlacement
GetWindowPlacement.argtypes = [HWND, c_void_p]
GetWindowPlacement.restype = BOOL

SetWindowPlacement = user32.SetWindowPlacement
SetWindowPlacement.argtypes = [HWND, c_void_p]
SetWindowPlacement.restype = BOOL

# 前台窗口
SetForegroundWindow = user32.SetForegroundWindow
SetForegroundWindow.argtypes = [HWND]
SetForegroundWindow.restype = BOOL

AllowSetForegroundWindow = user32.AllowSetForegroundWindow
AllowSetForegroundWindow.argtypes = [DWORD]
AllowSetForegroundWindow.restype = BOOL

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.argtypes = []
GetForegroundWindow.restype = HWND

GetDesktopWindow = user32.GetDesktopWindow
GetDesktopWindow.argtypes = []
GetDesktopWindow.restype = HWND

SetActiveWindow = user32.SetActiveWindow
SetActiveWindow.argtypes = [HWND]
SetActiveWindow.restype = HWND

# 显示器
MonitorFromWindow = user32.MonitorFromWindow
MonitorFromWindow.argtypes = [HWND, DWORD]
MonitorFromWindow.restype = HANDLE

MonitorFromRect = user32.MonitorFromRect
MonitorFromRect.argtypes = [POINTER(RECT), DWORD]
MonitorFromRect.restype = HANDLE

GetMonitorInfoW = user32.GetMonitorInfoW
GetMonitorInfoW.argtypes = [HANDLE, POINTER(MONITORINFO)]
GetMonitorInfoW.restype = BOOL

GetSystemMetrics = user32.GetSystemMetrics
GetSystemMetrics.argtypes = [c_int]
GetSystemMetrics.restype = c_int

# 输入/菜单
GetCursorPos = user32.GetCursorPos
GetCursorPos.argtypes = [POINTER(POINT)]
GetCursorPos.restype = BOOL

SetCursorPos = user32.SetCursorPos
SetCursorPos.argtypes = [c_int, c_int]
SetCursorPos.restype = BOOL

GetAsyncKeyState = user32.GetAsyncKeyState
GetAsyncKeyState.argtypes = [c_int]
GetAsyncKeyState.restype = c_short

RegisterHotKey = user32.RegisterHotKey
RegisterHotKey.argtypes = [HWND, c_int, UINT, UINT]
RegisterHotKey.restype = BOOL

UnregisterHotKey = user32.UnregisterHotKey
UnregisterHotKey.argtypes = [HWND, c_int]
UnregisterHotKey.restype = BOOL

CreatePopupMenu = user32.CreatePopupMenu
CreatePopupMenu.argtypes = []
CreatePopupMenu.restype = HMENU

DestroyMenu = user32.DestroyMenu
DestroyMenu.argtypes = [HMENU]
DestroyMenu.restype = BOOL

AppendMenuW = user32.AppendMenuW
AppendMenuW.argtypes = [HMENU, UINT, c_ulonglong, LPCWSTR]
AppendMenuW.restype = BOOL

TrackPopupMenuEx = user32.TrackPopupMenuEx
TrackPopupMenuEx.argtypes = [HMENU, UINT, c_int, c_int, HWND, c_void_p]
TrackPopupMenuEx.restype = BOOL

# 图标
GetIconInfo = user32.GetIconInfo
GetIconInfo.argtypes = [HICON, POINTER(ICONINFO)]
GetIconInfo.restype = BOOL

LoadImageW = user32.LoadImageW
LoadImageW.argtypes = [HINSTANCE, LPCWSTR, UINT, c_int, c_int, UINT]
LoadImageW.restype = HANDLE

DrawIconEx = user32.DrawIconEx
DrawIconEx.argtypes = [HDC, c_int, c_int, HICON, c_int, c_int, UINT, HBRUSH, UINT]
DrawIconEx.restype = BOOL

DestroyIcon = user32.DestroyIcon
DestroyIcon.argtypes = [HICON]
DestroyIcon.restype = BOOL

GetDC = user32.GetDC
GetDC.argtypes = [HWND]
GetDC.restype = HDC

ReleaseDC = user32.ReleaseDC
ReleaseDC.argtypes = [HWND, HDC]
ReleaseDC.restype = c_int

# 消息框
MessageBoxW = user32.MessageBoxW
MessageBoxW.argtypes = [HWND, LPCWSTR, LPCWSTR, UINT]
MessageBoxW.restype = c_int

# 线程/进程
GetCurrentThreadId = kernel32.GetCurrentThreadId
GetCurrentThreadId.argtypes = []
GetCurrentThreadId.restype = DWORD

GetCurrentProcessId = kernel32.GetCurrentProcessId
GetCurrentProcessId.argtypes = []
GetCurrentProcessId.restype = DWORD

GetModuleHandleW = kernel32.GetModuleHandleW
GetModuleHandleW.argtypes = [LPCWSTR]
GetModuleHandleW.restype = HMODULE

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [DWORD, BOOL, DWORD]
OpenProcess.restype = HANDLE

QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, POINTER(DWORD)]
QueryFullProcessImageNameW.restype = BOOL

# 跨进程内存操作（用于枚举 Explorer 托盘工具栏按钮数据）
VirtualAllocEx = kernel32.VirtualAllocEx
VirtualAllocEx.argtypes = [HANDLE, LPVOID, ctypes.c_size_t, DWORD, DWORD]
VirtualAllocEx.restype = LPVOID

VirtualFreeEx = kernel32.VirtualFreeEx
VirtualFreeEx.argtypes = [HANDLE, LPVOID, ctypes.c_size_t, DWORD]
VirtualFreeEx.restype = BOOL

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [HANDLE, LPCVOID, LPVOID, ctypes.c_size_t, POINTER(ctypes.c_size_t)]
ReadProcessMemory.restype = BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.restype = BOOL

GetLastError = kernel32.GetLastError
GetLastError.argtypes = []
GetLastError.restype = DWORD

Sleep = kernel32.Sleep
Sleep.argtypes = [DWORD]
Sleep.restype = None

CreateMutexW = kernel32.CreateMutexW
CreateMutexW.argtypes = [LPVOID, BOOL, LPCWSTR]
CreateMutexW.restype = HANDLE

ReleaseMutex = kernel32.ReleaseMutex
ReleaseMutex.argtypes = [HANDLE]
ReleaseMutex.restype = BOOL

WaitForSingleObject = kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [HANDLE, DWORD]
WaitForSingleObject.restype = DWORD

GlobalAlloc = kernel32.GlobalAlloc
GlobalAlloc.argtypes = [UINT, c_ulonglong]
GlobalAlloc.restype = HGLOBAL

GlobalFree = kernel32.GlobalFree
GlobalFree.argtypes = [HGLOBAL]
GlobalFree.restype = HGLOBAL

GlobalLock = kernel32.GlobalLock
GlobalLock.argtypes = [HGLOBAL]
GlobalLock.restype = LPVOID

GlobalUnlock = kernel32.GlobalUnlock
GlobalUnlock.argtypes = [HGLOBAL]
GlobalUnlock.restype = BOOL

# ===== shell32 =====

SHAppBarMessage = shell32.SHAppBarMessage
SHAppBarMessage.argtypes = [DWORD, POINTER(APPBARDATA)]
SHAppBarMessage.restype = c_ulonglong

SHGetFileInfoW = shell32.SHGetFileInfoW
SHGetFileInfoW.argtypes = [LPCWSTR, DWORD, POINTER(SHFILEINFO), UINT, UINT]
SHGetFileInfoW.restype = c_ulonglong

ExtractIconExW = shell32.ExtractIconExW
ExtractIconExW.argtypes = [LPCWSTR, c_int, POINTER(HICON), POINTER(HICON), UINT]
ExtractIconExW.restype = UINT

# shell32 共享内存函数为内部导出，默认不直接绑定以避免函数名缺失导致导入失败。
# 需要时在 AppBar 模块中通过 GetProcAddress 动态解析。

# SHLockShared = shell32.SHLockShared
# SHLockShared.argtypes = [HANDLE, DWORD]
# SHLockShared.restype = LPVOID

# SHUnlockShared = shell32.SHUnlockShared
# SHUnlockShared.argtypes = [LPVOID]
# SHUnlockShared.restype = BOOL

# SHAllocShared = shell32.SHAllocShared
# SHAllocShared.argtypes = [LPVOID, DWORD, DWORD]
# SHAllocShared.restype = HANDLE

# SHFreeShared = shell32.SHFreeShared
# SHFreeShared.argtypes = [HANDLE, DWORD]
# SHFreeShared.restype = BOOL

# ===== dwmapi =====

DwmGetWindowAttribute = dwmapi.DwmGetWindowAttribute
DwmGetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
DwmGetWindowAttribute.restype = c_long

DwmSetWindowAttribute = dwmapi.DwmSetWindowAttribute
DwmSetWindowAttribute.argtypes = [HWND, DWORD, LPVOID, DWORD]
DwmSetWindowAttribute.restype = c_long

DwmExtendFrameIntoClientArea = dwmapi.DwmExtendFrameIntoClientArea
DwmExtendFrameIntoClientArea.argtypes = [HWND, LPVOID]
DwmExtendFrameIntoClientArea.restype = c_long

# ===== gdi32 =====

CreateCompatibleDC = gdi32.CreateCompatibleDC
CreateCompatibleDC.argtypes = [HDC]
CreateCompatibleDC.restype = HDC

DeleteDC = gdi32.DeleteDC
DeleteDC.argtypes = [HDC]
DeleteDC.restype = BOOL

SelectObject = gdi32.SelectObject
SelectObject.argtypes = [HDC, HANDLE]
SelectObject.restype = HANDLE

GetDIBits = gdi32.GetDIBits
GetDIBits.argtypes = [HDC, HBITMAP, UINT, UINT, LPVOID, POINTER(BITMAPINFO), UINT]
GetDIBits.restype = c_int

DeleteObject = gdi32.DeleteObject
DeleteObject.argtypes = [HANDLE]
DeleteObject.restype = BOOL

CreateBitmap = gdi32.CreateBitmap
CreateBitmap.argtypes = [c_int, c_int, UINT, UINT, c_void_p]
CreateBitmap.restype = HBITMAP

CreateCompatibleBitmap = gdi32.CreateCompatibleBitmap
CreateCompatibleBitmap.argtypes = [HDC, c_int, c_int]
CreateCompatibleBitmap.restype = HBITMAP

CreateDIBSection = gdi32.CreateDIBSection
CreateDIBSection.argtypes = [HDC, c_void_p, UINT, POINTER(c_void_p), HANDLE, DWORD]
CreateDIBSection.restype = HBITMAP

BitBlt = gdi32.BitBlt
BitBlt.argtypes = [HDC, c_int, c_int, c_int, c_int, HDC, c_int, c_int, DWORD]
BitBlt.restype = BOOL

CreateRectRgn = gdi32.CreateRectRgn
CreateRectRgn.argtypes = [c_int, c_int, c_int, c_int]
CreateRectRgn.restype = HRGN

# ===== ole32 =====

CoInitialize = ole32.CoInitialize
CoInitialize.argtypes = [LPVOID]
CoInitialize.restype = c_long

CoUninitialize = ole32.CoUninitialize
CoUninitialize.argtypes = []
CoUninitialize.restype = None


# 便捷函数

def register_window_message(name: str) -> int:
    """注册或获取全局窗口消息。"""
    return RegisterWindowMessageW(name)


def get_window_text(hwnd: int) -> str:
    """获取窗口标题。"""
    length = 256
    buffer = ctypes.create_unicode_buffer(length)
    GetWindowTextW(hwnd, buffer, length)
    return buffer.value


def get_class_name(hwnd: int) -> str:
    """获取窗口类名。"""
    length = 256
    buffer = ctypes.create_unicode_buffer(length)
    GetClassNameW(hwnd, buffer, length)
    return buffer.value


def get_window_process_id(hwnd: int) -> int:
    """获取窗口所属进程 ID。"""
    pid = DWORD()
    GetWindowThreadProcessId(hwnd, byref(pid))
    return pid.value


def get_process_image_path(hwnd: int) -> str:
    """获取窗口所属进程的可执行文件完整路径，失败返回空串。"""
    if not hwnd:
        return ""
    pid = get_window_process_id(hwnd)
    if not pid:
        return ""
    h_process = OpenProcess(constants.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        h_process = OpenProcess(constants.PROCESS_QUERY_INFORMATION, False, pid)
    if not h_process:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(constants.MAX_PATH)
        size = DWORD(constants.MAX_PATH)
        if QueryFullProcessImageNameW(h_process, 0, buffer, byref(size)):
            return buffer.value
        return ""
    finally:
        CloseHandle(h_process)


def get_last_error() -> int:
    """获取最后一个 Win32 错误码。"""
    return GetLastError()


def get_shell_tray_hwnd() -> int | None:
    """查找 Explorer 的 Shell_TrayWnd 窗口。"""
    hwnd = FindWindowW(constants.SHELL_TRAY_WND, None)
    return hwnd if hwnd else None


def get_tray_notify_hwnd() -> int | None:
    """查找 Explorer 的 TrayNotifyWnd 窗口。"""
    hwnd = FindWindowExW(0, 0, constants.SHELL_TRAY_WND, None)
    if hwnd:
        hwnd = FindWindowExW(hwnd, 0, constants.TRAY_NOTIFY_WND, None)
    return hwnd if hwnd else None


def is_window_cloaked(hwnd: int) -> bool:
    """通过 DWM 判断窗口是否被 cloaked。"""
    from ctypes import c_int
    cloaked = DWORD()
    result = DwmGetWindowAttribute(hwnd, constants.DWMWA_CLOAKED, byref(cloaked), sizeof(DWORD))
    return result == 0 and cloaked.value != 0


def get_monitor_rect(hwnd: int) -> RECT | None:
    """获取窗口所在显示器的工作区。"""
    hmonitor = MonitorFromWindow(hwnd, constants.MONITOR_DEFAULTTONEAREST)
    if not hmonitor:
        return None
    mi = MONITORINFO()
    mi.cbSize = sizeof(MONITORINFO)
    if GetMonitorInfoW(hmonitor, byref(mi)):
        return mi.rcWork
    return None


def get_instance_handle() -> int:
    """获取当前模块实例句柄。"""
    return GetModuleHandleW(None)
