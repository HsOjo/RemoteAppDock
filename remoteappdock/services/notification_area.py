"""通知区域模型管理。"""

import logging
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QObject, Signal

from remoteappdock.models.notify_icon import NotifyIcon
from remoteappdock.win32 import constants


logger = logging.getLogger(__name__)

_NIF_MESSAGE = constants.NIF_MESSAGE
_NIF_ICON = constants.NIF_ICON
_NIF_TIP = constants.NIF_TIP
_NIF_STATE = constants.NIF_STATE
_NIF_GUID = constants.NIF_GUID


class NotificationArea(QObject):
    """维护托盘图标列表，并通知 UI 更新。"""

    icon_added = Signal(NotifyIcon)
    icon_modified = Signal(NotifyIcon)
    icon_removed = Signal(object)  # 发送 (hWnd, uID) tuple 或 guid

    def __init__(self):
        super().__init__()
        self._icons: dict[tuple[int, int], NotifyIcon] = {}
        self._guid_icons: dict[str, NotifyIcon] = {}

    def add_icon(self, icon: NotifyIcon) -> None:
        key = (icon.hWnd, icon.uID)
        self._icons[key] = icon
        if icon.guid:
            self._guid_icons[icon.guid] = icon
        self.icon_added.emit(icon)
        logger.debug("添加托盘图标: hWnd=%s uID=%s title=%s", icon.hWnd, icon.uID, icon.title)

    def modify_icon(self, icon: NotifyIcon) -> None:
        key = (icon.hWnd, icon.uID)
        existing = self._icons.get(key)
        if existing is None:
            # 某些实现会先发送 MODIFY，这里按 ADD 处理
            self.add_icon(icon)
            return

        # 按本次消息实际携带的字段做增量合并，避免用未设置的字段覆盖已有值。
        flags = icon.uflags
        if flags & _NIF_TIP and icon.title:
            existing.title = icon.title
        if flags & _NIF_MESSAGE:
            existing.callback_message = icon.callback_message
        if flags & _NIF_ICON:
            existing.hicon = icon.hicon
        if flags & _NIF_STATE:
            existing.is_hidden = icon.is_hidden
        if flags & _NIF_GUID and icon.guid:
            existing.guid = icon.guid
        if icon.icon_path:
            existing.icon_path = icon.icon_path

        self.icon_modified.emit(existing)
        logger.debug("修改托盘图标: hWnd=%s uID=%s title=%s hIcon=0x%X",
                     existing.hWnd, existing.uID, existing.title, existing.hicon)

    def remove_icon(self, hWnd: int, uID: int, guid: str | None = None) -> None:
        key = (hWnd, uID)
        icon = self._icons.pop(key, None)
        if icon is None and guid:
            icon = self._guid_icons.pop(guid, None)
        if icon is not None:
            self.icon_removed.emit((hWnd, uID))
            logger.debug("移除托盘图标: hWnd=%s uID=%s", hWnd, uID)

    def set_version(self, hWnd: int, uID: int, version: int) -> None:
        key = (hWnd, uID)
        icon = self._icons.get(key)
        if icon is not None:
            icon.version = version
            self.icon_modified.emit(icon)

    def get_icons(self) -> list[NotifyIcon]:
        return list(self._icons.values())

    def clear(self) -> None:
        for key in list(self._icons.keys()):
            self.icon_removed.emit(key)
        self._icons.clear()
        self._guid_icons.clear()
