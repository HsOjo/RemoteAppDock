"""单个托盘图标控件。"""

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent, QWheelEvent, QCursor
from PySide6.QtWidgets import QLabel

from remoteappdock.models.notify_icon import NotifyIcon
from remoteappdock.platform import IS_WINDOWS
from remoteappdock.utils.icon_converter import IconConverter

if IS_WINDOWS:
    from remoteappdock.win32 import constants, api
    from remoteappdock.win32.structs import POINT
else:
    # 非 Windows 平台只需要消息常量名供 _forward/mock 使用
    class _MockConstants:
        def __getattr__(self, name: str) -> int:
            return 0
    constants = _MockConstants()


logger = logging.getLogger(__name__)


class NotifyIconWidget(QLabel):
    """托盘图标控件，显示图标并转发鼠标事件。"""

    ICON_SIZE = 16
    DOUBLE_CLICK_MS = 300

    # 无边框按钮风格：默认透明，hover/pressed 时半透明高亮反馈。
    # 类型选择器限定，避免样式级联到该控件的 QToolTip（否则 tooltip 变黑）。
    _ICON_STYLE = (
        "NotifyIconWidget { border: none; border-radius: 4px; background: transparent; }"
        "NotifyIconWidget:hover { background: rgba(255, 255, 255, 40); }"
    )
    # 无图标占位符：给默认背景色和边框，确保在非 Windows 预览或系统主题下可见。
    _PLACEHOLDER_STYLE = (
        "NotifyIconWidget { color: white; border: 1px solid rgba(255, 255, 255, 80); "
        "border-radius: 4px; background: rgba(80, 80, 80, 160); }"
        "NotifyIconWidget:hover { background: rgba(255, 255, 255, 40); }"
    )

    def __init__(self, icon: NotifyIcon, tray_service, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._tray_service = tray_service

        self.setFixedSize(self.ICON_SIZE + 8, self.ICON_SIZE + 4)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 右键交由 mousePressEvent/mouseReleaseEvent 转发给原窗口，禁止 Qt 合成
        # QContextMenuEvent 冒泡到父级任务栏，否则会误触发任务栏本体的右键菜单。
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.setToolTip(icon.title or f"Icon {icon.uID}")
        self.setStyleSheet(self._ICON_STYLE)
        self._update_icon()

        self._last_l_click = 0
        self._last_m_click = 0
        self._last_r_click = 0
        self._double_click_timer: QTimer | None = None

    def update_icon(self, icon: NotifyIcon) -> None:
        """更新图标数据。"""
        self._icon = icon
        self.setToolTip(icon.title or f"Icon {icon.uID}")
        self._update_icon()
        self._report_rect()

    def _report_rect(self) -> None:
        """上报图标在屏幕上的矩形（物理像素）给托盘服务，供菜单定位查询。"""
        if not hasattr(self._tray_service, "update_icon_rect"):
            return
        try:
            top_left = self.mapToGlobal(self.rect().topLeft())
            # 逻辑坐标 -> 物理像素：乘以 devicePixelRatio。
            dpr = self.devicePixelRatioF() or 1.0
            left = round(top_left.x() * dpr)
            top = round(top_left.y() * dpr)
            right = round((top_left.x() + self.width()) * dpr)
            bottom = round((top_left.y() + self.height()) * dpr)
            self._tray_service.update_icon_rect(
                self._icon.hWnd, self._icon.uID, self._icon.guid,
                (left, top, right, bottom),
            )
        except Exception:
            logger.debug("上报图标位置失败", exc_info=True)

    @staticmethod
    def _packed_cursor_pos() -> int:
        """获取当前光标屏幕坐标（物理像素）并打包为 (x & 0xFFFF) | (y << 16)。

        Windows 下直接用 Win32 GetCursorPos 取物理像素，绕开 Qt 的 DPI 逻辑坐标转换，
        保证 version 4 图标菜单定位在高 DPI 下正确。
        非 Windows 平台使用 QCursor.pos() 作为 mock。
        """
        if IS_WINDOWS:
            pt = POINT()
            if api.GetCursorPos(pt):
                return (pt.x & 0xFFFF) | ((pt.y & 0xFFFF) << 16)
            return 0

        pos = QCursor.pos()
        return (pos.x() & 0xFFFF) | ((pos.y() & 0xFFFF) << 16)

    def _forward(self, msg: int) -> bool:
        """转发鼠标消息，自动附带光标坐标与图标 version。"""
        return self._tray_service.forward_mouse_event(
            self._icon.hWnd, self._icon.uID, self._icon.callback_message, msg,
            mouse=self._packed_cursor_pos(), version=self._icon.version,
        )

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._report_rect()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._report_rect()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._report_rect()

    def _update_icon(self) -> None:
        if self._icon.hicon:
            pixmap = IconConverter.hicon_to_pixmap(self._icon.hicon)
            if pixmap and not pixmap.isNull():
                # 按屏幕 DPI 渲染，避免高 DPI 下模糊。
                # 目标物理像素 = 逻辑尺寸 × devicePixelRatio。
                dpr = self.devicePixelRatioF() or 1.0
                target_px = max(1, round(self.ICON_SIZE * dpr))
                scaled = pixmap.scaled(
                    target_px, target_px,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                scaled.setDevicePixelRatio(dpr)
                self.setPixmap(scaled)
                self.setStyleSheet(self._ICON_STYLE)
                return
        # 没有图标时显示标题首字母作为占位
        text = (self._icon.title or "")[:1] or "?"
        self.setText(text)
        self.setStyleSheet(self._PLACEHOLDER_STYLE)

    def _is_double_click(self, last_time: int, current_time: int) -> bool:
        """判断两次点击是否构成双击。"""
        return (current_time - last_time) <= self.DOUBLE_CLICK_MS

    def mousePressEvent(self, event: QMouseEvent) -> None:
        msg = self._map_mouse_button(event.button(), press=True)
        if msg:
            if event.button() == Qt.MouseButton.LeftButton:
                if self._is_double_click(self._last_l_click, event.timestamp()):
                    self._forward(constants.WM_LBUTTONDBLCLK)
                else:
                    self._forward(msg)
            elif event.button() == Qt.MouseButton.MiddleButton:
                if self._is_double_click(self._last_m_click, event.timestamp()):
                    self._forward(constants.WM_MBUTTONDBLCLK)
                else:
                    self._forward(msg)
            elif event.button() == Qt.MouseButton.RightButton:
                if self._is_double_click(self._last_r_click, event.timestamp()):
                    self._forward(constants.WM_RBUTTONDBLCLK)
                else:
                    self._forward(msg)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        msg = self._map_mouse_button(event.button(), press=False)
        if not msg:
            super().mouseReleaseEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._forward(msg)
            if self._icon.version >= 3:
                self._forward(constants.NIN_SELECT)
            self._last_l_click = event.timestamp()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._forward(msg)
            self._last_m_click = event.timestamp()
        elif event.button() == Qt.MouseButton.RightButton:
            self._forward(msg)
            if self._icon.version >= 3:
                self._forward(constants.WM_CONTEXTMENU)
            self._last_r_click = event.timestamp()

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """滚轮事件转发，走统一的 forward 通道（SendNotifyMessage）。"""
        self._forward(constants.WM_MOUSEWHEEL)
        super().wheelEvent(event)

    def enterEvent(self, event) -> None:
        self._forward(constants.WM_MOUSEMOVE)
        if self._icon.version > 3:
            self._forward(constants.NIN_POPUPOPEN)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._forward(constants.WM_MOUSELEAVE)
        if self._icon.version > 3:
            self._forward(constants.NIN_POPUPCLOSE)
        super().leaveEvent(event)

    def _map_mouse_button(self, button, press: bool) -> int | None:
        if button == Qt.MouseButton.LeftButton:
            return constants.WM_LBUTTONDOWN if press else constants.WM_LBUTTONUP
        if button == Qt.MouseButton.RightButton:
            return constants.WM_RBUTTONDOWN if press else constants.WM_RBUTTONUP
        if button == Qt.MouseButton.MiddleButton:
            return constants.WM_MBUTTONDOWN if press else constants.WM_MBUTTONUP
        return None
