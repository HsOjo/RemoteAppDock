"""Win32 结构体定义。"""

import ctypes
from ctypes import Structure, c_void_p, c_int, c_uint, c_long, c_ulong, c_longlong, c_ulonglong, c_short, c_ushort, c_byte, c_char, c_wchar, c_bool, POINTER, sizeof, byref
from ctypes.wintypes import HWND, UINT, DWORD, ULONG, LONG, WORD, BYTE, BOOL, LPVOID, LPCVOID, HANDLE, LPWSTR, LPCWSTR, LPSTR, LPCSTR, RECT as _RECT, POINT as _POINT, MSG as _MSG

# ctypes.wintypes 中部分句柄类型未定义，使用通用句柄别名
HANDLE = c_void_p
HWND = HANDLE
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


class GUID(Structure):
    """GUID 结构体。"""
    _fields_ = [
        ("Data1", c_ulong),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", c_byte * 8),
    ]

    def __repr__(self):
        # Data4 为 c_byte（有符号），格式化前需 & 0xFF 还原为无符号字节，
        # 否则负值经 %02X 会输出错误（如 0x82 -> "-7E"）。
        b = [self.Data4[i] & 0xFF for i in range(8)]
        return "{%08X-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X}" % (
            self.Data1 & 0xFFFFFFFF, self.Data2 & 0xFFFF, self.Data3 & 0xFFFF,
            b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]
        )


class POINT(Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class MARGINS(Structure):
    """DwmExtendFrameIntoClientArea 用的边距结构。"""
    _fields_ = [
        ("cxLeftWidth", c_int),
        ("cxRightWidth", c_int),
        ("cyTopHeight", c_int),
        ("cyBottomHeight", c_int),
    ]


class RECT(Structure):
    _fields_ = [("left", LONG), ("top", LONG), ("right", LONG), ("bottom", LONG)]


class SIZE(Structure):
    _fields_ = [("cx", LONG), ("cy", LONG)]


class COPYDATASTRUCT(Structure):
    """WM_COPYDATA 数据封装。"""
    _pack_ = 8
    _fields_ = [
        ("dwData", c_ulonglong),  # ULONG_PTR
        ("cbData", c_uint),       # DWORD
        ("lpData", LPVOID),
    ]


class SHELLTRAYDATA(Structure):
    """Explorer 发送给 Shell_TrayWnd 的托盘数据。

    参考 ManagedShell 实现：dwUnknown + dwMessage + NOTIFYICONDATA。
    """
    _pack_ = 4
    _fields_ = [
        ("dwUnknown", c_ulong),
        ("dwMessage", c_ulong),
        # 后续紧接 NOTIFYICONDATAW，长度可变，这里不声明字段，按偏移访问。
    ]


SHELLTRAYDATA_SIGNATURE = 0x34753423


class NOTIFYICONDATA(Structure):
    """NOTIFYICONDATAW 结构体（Unicode），WM_COPYDATA 传输布局。

    重要：通过 WM_COPYDATA 转发的 NOTIFYICONDATA 使用固定的 32 位句柄布局
    （hWnd / hIcon / hBalloonIcon 均为 4 字节 DWORD），与进程位数无关。
    这是 Explorer 内部使用的历史传输格式，正确大小为 956 字节。
    参考 ManagedShell NativeMethods.Shell32.cs 中的 NOTIFYICONDATA 定义。
    """
    _pack_ = 4
    _fields_ = [
        ("cbSize", DWORD),
        ("hWnd", DWORD),
        ("uID", UINT),
        ("uFlags", UINT),
        ("uCallbackMessage", UINT),
        ("hIcon", DWORD),
        ("szTip", c_wchar * 128),
        ("dwState", DWORD),
        ("dwStateMask", DWORD),
        ("szInfo", c_wchar * 256),
        ("union", UINT),  # uTimeout / uVersion 共用体
        ("szInfoTitle", c_wchar * 64),
        ("dwInfoFlags", DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", DWORD),
    ]

    @property
    def uTimeout(self):
        return self.union

    @uTimeout.setter
    def uTimeout(self, value):
        self.union = value

    @property
    def uVersion(self):
        return self.union

    @uVersion.setter
    def uVersion(self, value):
        self.union = value


class NOTIFYICONDATAA(Structure):
    """NOTIFYICONDATAA 结构体（ANSI），WM_COPYDATA 传输布局（32 位句柄）。"""
    _pack_ = 4
    _fields_ = [
        ("cbSize", DWORD),
        ("hWnd", DWORD),
        ("uID", UINT),
        ("uFlags", UINT),
        ("uCallbackMessage", UINT),
        ("hIcon", DWORD),
        ("szTip", c_char * 128),
        ("dwState", DWORD),
        ("dwStateMask", DWORD),
        ("szInfo", c_char * 256),
        ("union", UINT),
        ("szInfoTitle", c_char * 64),
        ("dwInfoFlags", DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", DWORD),
    ]


class WINNOTIFYICONIDENTIFIER(Structure):
    """用于查询托盘图标位置。"""
    _pack_ = 4
    _fields_ = [
        ("dwMagic", DWORD),
        ("dwMessage", DWORD),
        ("dwSize", DWORD),
        ("dwPadding", DWORD),
        ("hWnd", c_uint),
        ("uID", UINT),
        ("guidItem", GUID),
    ]


class APPBARDATA(Structure):
    """AppBar 数据。"""
    _pack_ = 4
    _fields_ = [
        ("cbSize", DWORD),
        ("hWnd", HWND),
        ("uCallbackMessage", UINT),
        ("uEdge", UINT),
        ("rc", RECT),
        ("lParam", LONG),
    ]


class APPBARDATAV2(Structure):
    """AppBar 数据 V2。"""
    _pack_ = 4
    _fields_ = [
        ("cbSize", DWORD),
        ("hWnd", HWND),
        ("uCallbackMessage", UINT),
        ("uEdge", UINT),
        ("rc", RECT),
        ("lParam", LONG),
        ("uMonitor", UINT),
    ]


class APPBARMSGDATAV3(Structure):
    """AppBar 进程间消息数据 V3。"""
    _pack_ = 4
    _fields_ = [
        ("dwMessage", DWORD),
        ("hWnd", HWND),
        ("uEdge", UINT),
        ("rc", RECT),
        ("lParam", LONG),
        ("uMonitor", UINT),
        ("dwProcessId", DWORD),
    ]


class SHELLHOOKINFO(Structure):
    """Shell Hook 消息附带数据。"""
    _pack_ = 4
    _fields_ = [
        ("hwnd", HWND),
        ("rc", RECT),
    ]


class TBBUTTON(Structure):
    """工具栏按钮结构（64 位布局，用于跨进程读取 Explorer 托盘工具栏）。

    dwData 指向目标进程中的 TRAYITEM。iString 为 INT_PTR（8 字节）。
    """
    _fields_ = [
        ("iBitmap", c_int),
        ("idCommand", c_int),
        ("fsState", c_byte),
        ("fsStyle", c_byte),
        ("bReserved", c_byte * 6),
        ("dwData", c_void_p),
        ("iString", c_longlong),
    ]


class TRAYITEM(Structure):
    """Explorer 托盘图标项（跨进程读取系统托盘工具栏 TBBUTTON.dwData 指向的数据）。

    这是 Explorer 进程内部的私有结构，布局对照 ManagedShell ExplorerTrayService.TrayItem。
    由于读取的是目标进程（explorer.exe）的内存，句柄字段为该进程的真实指针宽度。
    """
    _fields_ = [
        ("hWnd", HWND),
        ("uID", UINT),
        ("uCallbackMessage", UINT),
        ("dwState", UINT),
        ("uVersion", UINT),
        ("hIcon", HICON),
        ("uIconDemoteTimerID", HANDLE),
        ("dwUserPref", UINT),
        ("dwLastSoundTime", UINT),
        ("szExeName", c_wchar * 260),
        ("szIconText", c_wchar * 260),
        ("uNumSeconds", UINT),
        ("guidItem", GUID),
    ]


class WNDCLASSW(Structure):
    """WNDCLASSW 结构体。"""
    _fields_ = [
        ("style", UINT),
        ("lpfnWndProc", c_void_p),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", LPCWSTR),
        ("lpszClassName", LPCWSTR),
    ]


class WNDCLASSEXW(Structure):
    """WNDCLASSEXW 结构体。"""
    _fields_ = [
        ("cbSize", UINT),
        ("style", UINT),
        ("lpfnWndProc", c_void_p),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", LPCWSTR),
        ("lpszClassName", LPCWSTR),
        ("hIconSm", HICON),
    ]


class WINDOWPOS(Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("hwndInsertAfter", HWND),
        ("x", c_int),
        ("y", c_int),
        ("cx", c_int),
        ("cy", c_int),
        ("flags", UINT),
    ]


class MSG(Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("message", UINT),
        ("wParam", c_ulonglong),
        ("lParam", c_longlong),
        ("time", DWORD),
        ("pt", POINT),
    ]


class MINMAXINFO(Structure):
    _fields_ = [
        ("ptReserved", POINT),
        ("ptMaxSize", POINT),
        ("ptMaxPosition", POINT),
        ("ptMinTrackSize", POINT),
        ("ptMaxTrackSize", POINT),
    ]


class NMHDR(Structure):
    _fields_ = [
        ("hwndFrom", HWND),
        ("idFrom", c_ulonglong),
        ("code", UINT),
    ]


class SHFILEINFO(Structure):
    _fields_ = [
        ("hIcon", HICON),
        ("iIcon", c_int),
        ("dwAttributes", DWORD),
        ("szDisplayName", c_wchar * 260),
        ("szTypeName", c_wchar * 80),
    ]


class GUITHREADINFO(Structure):
    _fields_ = [
        ("cbSize", DWORD),
        ("flags", DWORD),
        ("hwndActive", HWND),
        ("hwndFocus", HWND),
        ("hwndCapture", HWND),
        ("hwndMenuOwner", HWND),
        ("hwndMoveSize", HWND),
        ("hwndCaret", HWND),
        ("rcCaret", RECT),
    ]


class MONITORINFO(Structure):
    _fields_ = [
        ("cbSize", DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", DWORD),
    ]


class ICONINFO(Structure):
    _fields_ = [
        ("fIcon", BOOL),
        ("xHotspot", DWORD),
        ("yHotspot", DWORD),
        ("hbmMask", HANDLE),
        ("hbmColor", HANDLE),
    ]


class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", LONG),
        ("biHeight", LONG),
        ("biPlanes", WORD),
        ("biBitCount", WORD),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]


class RGBQUAD(Structure):
    _fields_ = [
        ("rgbBlue", BYTE),
        ("rgbGreen", BYTE),
        ("rgbRed", BYTE),
        ("rgbReserved", BYTE),
    ]


class BITMAPINFO(Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


class SECURITY_ATTRIBUTES(Structure):
    _fields_ = [
        ("nLength", DWORD),
        ("lpSecurityDescriptor", LPVOID),
        ("bInheritHandle", BOOL),
    ]


# 常用类型别名
LPRECT = POINTER(RECT)
LPPOINT = POINTER(POINT)
LPMSG = POINTER(MSG)
LPWNDCLASSW = POINTER(WNDCLASSW)
LPWNDCLASSEXW = POINTER(WNDCLASSEXW)
LPAPPBARDATA = POINTER(APPBARDATA)
LPAPPBARMSGDATAV3 = POINTER(APPBARMSGDATAV3)
LPSHELLTRAYDATA = POINTER(SHELLTRAYDATA)
LPNOTIFYICONDATA = POINTER(NOTIFYICONDATA)
LPNOTIFYICONDATAA = POINTER(NOTIFYICONDATAA)
LPWINNOTIFYICONIDENTIFIER = POINTER(WINNOTIFYICONIDENTIFIER)
LPSHFILEINFO = POINTER(SHFILEINFO)
LPSECURITY_ATTRIBUTES = POINTER(SECURITY_ATTRIBUTES)

# 结构体大小断言
assert sizeof(NOTIFYICONDATA) == 956, f"NOTIFYICONDATAW size mismatch: {sizeof(NOTIFYICONDATA)}"
assert sizeof(NOTIFYICONDATAA) == 508, f"NOTIFYICONDATAA size mismatch: {sizeof(NOTIFYICONDATAA)}"
assert sizeof(APPBARDATA) == 40, f"APPBARDATA size mismatch: {sizeof(APPBARDATA)}"
assert sizeof(COPYDATASTRUCT) == 24, f"COPYDATASTRUCT size mismatch: {sizeof(COPYDATASTRUCT)}"
assert sizeof(TBBUTTON) == 32, f"TBBUTTON size mismatch: {sizeof(TBBUTTON)}"
assert sizeof(GUID) == 16, f"GUID size mismatch: {sizeof(GUID)}"
assert sizeof(WINNOTIFYICONIDENTIFIER) == 40, f"WINNOTIFYICONIDENTIFIER size mismatch: {sizeof(WINNOTIFYICONIDENTIFIER)}"
assert sizeof(SHELLTRAYDATA) == 8, f"SHELLTRAYDATA size mismatch: {sizeof(SHELLTRAYDATA)}"
assert sizeof(WINDOWPOS) == 40, f"WINDOWPOS size mismatch: {sizeof(WINDOWPOS)}"
assert sizeof(MSG) == 48, f"MSG size mismatch: {sizeof(MSG)}"
