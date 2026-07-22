"""托盘图标数据模型。"""

from dataclasses import dataclass, field


@dataclass
class NotifyIcon:
    """表示系统托盘中的一个图标。"""

    hWnd: int = 0
    uID: int = 0
    guid: str | None = None
    title: str = ""
    icon_path: str | None = None
    hicon: int = 0  # 原始 HICON 句柄
    callback_message: int = 0
    version: int = 0
    uflags: int = 0  # 最近一次消息携带的 NIF_* 标志
    placement: object = None
    is_hidden: bool = False
    is_pinned: bool = False
    missed_notifications: int = 0
