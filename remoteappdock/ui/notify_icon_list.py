"""托盘图标列表 UI。"""

from PySide6.QtWidgets import QWidget, QSizePolicy

from remoteappdock.services.notification_area import NotificationArea
from remoteappdock.models.notify_icon import NotifyIcon
from remoteappdock.ui.notify_icon_widget import NotifyIconWidget
from remoteappdock.ui.flow_layout import FlowLayout


class NotifyIconList(QWidget):
    """显示通知区域图标列表，按可用宽度自动换行。"""

    def __init__(self, notification_area: NotificationArea, tray_service, parent=None):
        super().__init__(parent)
        self._notification_area = notification_area
        self._tray_service = tray_service
        self._widgets: dict[tuple[int, int], NotifyIconWidget] = {}

        self._layout = FlowLayout(self, margin=0, spacing=2, centered=True)

        # 宽度由父布局决定，高度随换行行数变化（heightForWidth）。
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

        self._notification_area.icon_added.connect(self._on_icon_added)
        self._notification_area.icon_modified.connect(self._on_icon_modified)
        self._notification_area.icon_removed.connect(self._on_icon_removed)

        for icon in self._notification_area.get_icons():
            self._on_icon_added(icon)

    def refresh_icon_rects(self) -> None:
        """重新上报所有图标的屏幕位置（父窗口移动/尺寸变化后调用）。"""
        for widget in self._widgets.values():
            widget._report_rect()

    def _on_icon_added(self, icon: NotifyIcon) -> None:
        key = (icon.hWnd, icon.uID)
        if key in self._widgets:
            return
        widget = NotifyIconWidget(icon, self._tray_service, self)
        self._widgets[key] = widget
        self._layout.addWidget(widget)

    def _on_icon_modified(self, icon: NotifyIcon) -> None:
        key = (icon.hWnd, icon.uID)
        widget = self._widgets.get(key)
        if widget is not None:
            widget.update_icon(icon)

    def _on_icon_removed(self, key) -> None:
        widget = self._widgets.pop(key, None)
        if widget is not None:
            if hasattr(self._tray_service, "remove_icon_rect"):
                hWnd, uID = key
                self._tray_service.remove_icon_rect(hWnd, uID)
            self._layout.removeWidget(widget)
            widget.deleteLater()
