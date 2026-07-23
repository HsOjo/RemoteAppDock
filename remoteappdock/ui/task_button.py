"""任务按钮 UI。"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QMouseEvent, QContextMenuEvent, QFontMetrics
from PySide6.QtWidgets import QPushButton, QMenu, QSizePolicy

from remoteappdock.services.tasks_service import WindowManager, TasksService
from remoteappdock.models.application_window import ApplicationWindow
from remoteappdock.utils.icon_converter import IconConverter


class TaskButton(QPushButton):
    """单个任务按钮。窗口标题过长时自动缩略显示，并显示进程图标。"""

    ICON_SIZE = 20
    BUTTON_HEIGHT = 36
    # 按钮宽度低于此阈值时只显示图标，不显示文本。
    TEXT_HIDE_WIDTH = 72

    # 有文本时图标与文本左对齐并留出内边距；仅图标时居中显示。
    _BUTTON_STYLE = "TaskButton { text-align: left; padding: 4px 8px; }"
    _BUTTON_STYLE_ICON_ONLY = "TaskButton { text-align: center; padding: 4px; }"

    def __init__(self, window: ApplicationWindow, tasks_service: TasksService, parent=None):
        super().__init__(parent)
        self._window = window
        self._tasks_service = tasks_service
        self._full_title = window.title

        self.setCheckable(True)
        self.setFlat(True)
        self.setToolTip(window.title)
        self.setChecked(window.state == "active")
        self.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self._apply_text()

        # 固定高度，水平方向占满可用宽度；最小宽度仅需容纳图标，
        # 以便窗体收窄时按钮可缩小并隐藏文本。
        self.setFixedHeight(self.BUTTON_HEIGHT)
        self.setMinimumWidth(self.ICON_SIZE + 12)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._load_icon()

        self.clicked.connect(self._on_clicked)

    def _load_icon(self) -> None:
        """从窗口进程可执行文件加载图标。"""
        try:
            hicon = IconConverter.extract_icon_from_window(self._window.handle, large=False)
            if hicon:
                pixmap = IconConverter.hicon_to_pixmap(hicon)
                if pixmap:
                    self.setIcon(pixmap)
                    # SHGetFileInfo 返回的图标通常由系统缓存，我们不负责销毁
        except Exception:
            pass

    def update_window(self, window: ApplicationWindow) -> None:
        self._window = window
        self._full_title = window.title
        self.setToolTip(window.title)
        self._apply_text()
        self.setChecked(window.state == "active")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_text()

    def _apply_text(self) -> None:
        """设置按钮文本，并根据是否显示文本切换对齐样式（仅图标时居中）。"""
        text = self._elided_text()
        self.setText(text)
        self.setStyleSheet(self._BUTTON_STYLE if text else self._BUTTON_STYLE_ICON_ONLY)

    def _elided_text(self) -> str:
        """根据按钮内容宽度缩略标题；宽度低于阈值时只显示图标（返回空文本）。"""
        if not self._full_title:
            return ""
        # 宽度过窄时隐藏文本，仅保留图标（完整标题仍可通过 tooltip 查看）。
        if self.width() < self.TEXT_HIDE_WIDTH:
            return ""
        metrics = QFontMetrics(self.font())
        # 预留图标宽度 + 左右内边距(8+8) + 图标与文本间距。
        available = max(0, self.contentsRect().width() - self.ICON_SIZE - 24)
        return metrics.elidedText(self._full_title, Qt.TextElideMode.ElideRight, available)

    def _on_clicked(self) -> None:
        if self._window.state == "active":
            self._tasks_service.minimize_window(self._window.handle)
        else:
            self._tasks_service.activate_window(self._window.handle)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.addAction(self.tr("Restore"), lambda: self._tasks_service.restore_window(self._window.handle))
        menu.addAction(self.tr("Minimize"), lambda: self._tasks_service.minimize_window(self._window.handle))
        menu.addAction(self.tr("Maximize"), lambda: self._tasks_service.maximize_window(self._window.handle))
        menu.addSeparator()
        menu.addAction(self.tr("Close"), lambda: self._tasks_service.close_window(self._window.handle))
        menu.exec(event.globalPos())
