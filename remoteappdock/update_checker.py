"""更新检查的 UI 线程封装与结果展示。"""

import logging
import webbrowser

from PySide6.QtCore import QCoreApplication, QThread, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QWidget, QApplication

from remoteappdock.updater import check_update, Release
from remoteappdock.version import APP_VERSION, RELEASES_URL


logger = logging.getLogger(__name__)


def _tr(source_text: str, *args, **kwargs) -> str:
    """使用 UpdateChecker 上下文翻译文本。"""
    return QCoreApplication.translate("UpdateChecker", source_text, *args, **kwargs)


class UpdateCheckThread(QThread):
    """在后台线程执行 GitHub 更新检查，避免阻塞 UI。"""

    finished = Signal(object, bool)  # release, have_new
    error = Signal(str)

    def __init__(self, force: bool = False, parent=None):
        super().__init__(parent)
        self._force = force

    def run(self):
        try:
            release, have_new = check_update(force=self._force)
            self.finished.emit(release, have_new)
        except Exception as exc:
            logger.exception("检查更新失败")
            self.error.emit(str(exc))


def show_update_result(parent: QWidget | None, release: Release, have_new: bool) -> None:
    """根据检查结果弹出提示框。"""
    if have_new:
        title = _tr("New Version Available")
        text = _tr(
            "A new version is available:\n\n"
            "Current: {current}\n"
            "Latest: {latest}\n\n"
            "Published at: {published}\n\n"
            "{body}"
        ).format(
            current=APP_VERSION,
            latest=release.tag_name,
            published=release.published_at or _tr("Unknown"),
            body=release.body or "",
        )
        msg = QMessageBox()
        msg.setWindowModality(Qt.WindowModality.ApplicationModal)
        msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle(title)
        msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close)
        msg.setDefaultButton(QMessageBox.StandardButton.Open)
        msg.button(QMessageBox.StandardButton.Open).setText(_tr("View Download Page"))
        msg.button(QMessageBox.StandardButton.Close).setText(_tr("Close"))
        # 固定尺寸并在父窗口居中，避免作为 AppBar 子窗口拖移后缩小。
        msg.setFixedSize(msg.sizeHint())
        _center_dialog(msg, parent)
        if msg.exec() == QMessageBox.StandardButton.Open:
            webbrowser.open(release.html_url or RELEASES_URL)
    else:
        msg = QMessageBox()
        msg.setWindowModality(Qt.WindowModality.ApplicationModal)
        msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle(_tr("No Updates"))
        msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            _tr("You are using the latest version ({version}).").format(version=APP_VERSION)
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        # 固定尺寸并在父窗口居中，避免作为 AppBar 子窗口拖移后缩小。
        msg.setFixedSize(msg.sizeHint())
        _center_dialog(msg, parent)
        msg.exec()


def show_update_error(parent: QWidget | None, message: str) -> None:
    """检查失败时弹出错误提示。"""
    msg = QMessageBox()
    msg.setWindowModality(Qt.WindowModality.ApplicationModal)
    msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
    msg.setWindowTitle(_tr("Update Check Failed"))
    msg.setTextFormat(Qt.TextFormat.PlainText)
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setText(_tr("Failed to check for updates:\n{message}").format(message=message))
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    # 固定尺寸并在父窗口居中，避免作为 AppBar 子窗口拖移后缩小。
    msg.setFixedSize(msg.sizeHint())
    _center_dialog(msg, parent)
    msg.exec()


def _center_dialog(dialog: QWidget, parent: QWidget | None) -> None:
    """将对话框在父窗口上居中；父窗口不可见时则居中于主屏幕。"""
    if parent is not None and parent.isVisible():
        parent_geo = parent.geometry()
        dialog.move(
            parent_geo.x() + (parent_geo.width() - dialog.width()) // 2,
            parent_geo.y() + (parent_geo.height() - dialog.height()) // 2,
        )
    else:
        screen = QApplication.primaryScreen()
        if screen is not None:
            center = screen.availableGeometry().center()
            dialog.move(center.x() - dialog.width() // 2, center.y() - dialog.height() // 2)
