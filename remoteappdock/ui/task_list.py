"""任务列表 UI。"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap

from remoteappdock.services.tasks_service import WindowManager
from remoteappdock.models.application_window import ApplicationWindow
from remoteappdock.utils.icon_converter import IconConverter


class TaskListModel(QAbstractListModel):
    """任务列表数据模型。"""

    def __init__(self, window_manager: WindowManager, parent=None):
        super().__init__(parent)
        self._window_manager = window_manager

        window_manager.window_added.connect(self._on_window_added)
        window_manager.window_removed.connect(self._on_window_removed)
        window_manager.window_updated.connect(self._on_window_updated)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._window_manager.get_windows())

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        windows = self._window_manager.get_windows()
        if index.row() >= len(windows):
            return None
        window = windows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return window.title
        if role == Qt.ItemDataRole.UserRole:
            return window
        if role == Qt.ItemDataRole.DecorationRole:
            # TODO: 从窗口提取图标
            return None
        return None

    def _on_window_added(self, window: ApplicationWindow) -> None:
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self.endInsertRows()

    def _on_window_removed(self, hwnd: int) -> None:
        windows = self._window_manager.get_windows()
        for i, w in enumerate(windows):
            if w.handle == hwnd:
                self.beginRemoveRows(QModelIndex(), i, i)
                self.endRemoveRows()
                return

    def _on_window_updated(self, window: ApplicationWindow) -> None:
        windows = self._window_manager.get_windows()
        for i, w in enumerate(windows):
            if w.handle == window.handle:
                self.dataChanged.emit(self.index(i), self.index(i))
                return

    def get_window(self, row: int) -> ApplicationWindow | None:
        windows = self._window_manager.get_windows()
        if 0 <= row < len(windows):
            return windows[row]
        return None
