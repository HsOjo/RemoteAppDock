"""主任务栏窗口。"""

import ctypes
import logging
import subprocess

from PySide6.QtCore import QCoreApplication, QTimer, Qt, QPoint
from PySide6.QtGui import QGuiApplication, QMouseEvent, QContextMenuEvent
from PySide6.QtWidgets import QMainWindow, QWidget, QBoxLayout, QSizePolicy, QApplication, QMenu, QMessageBox, QLabel

from remoteappdock.config import AppConfig
from remoteappdock.services.notification_area import NotificationArea
from remoteappdock.services.tray_service import TrayService
from remoteappdock.services.tasks_service import WindowManager, TasksService
from remoteappdock.services.appbar_manager import AppBarManager
from remoteappdock.services.snap_layout_helper import SnapLayoutHelper
from remoteappdock.ui.notify_icon_list import NotifyIconList
from remoteappdock.ui.task_button import TaskButton
from remoteappdock.update_checker import UpdateCheckThread, show_update_error, show_update_result
from remoteappdock.utils.helpers import get_app_icon_path
from remoteappdock.version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO
from remoteappdock.win32 import api, constants
from remoteappdock.win32.structs import MARGINS


logger = logging.getLogger(__name__)


class TaskbarWindow(QMainWindow):
    """主任务栏窗口，显示任务按钮与托盘图标。

    作为普通窗口运行：宽度大于高度时横向排列，高度大于宽度时纵向排列。
    """

    def __init__(self, notification_area: NotificationArea, tray_service: TrayService,
                 window_manager: WindowManager, tasks_service: TasksService,
                 appbar_manager: AppBarManager | None = None,
                 config: AppConfig | None = None, parent=None,
                 snap_layout_helper: SnapLayoutHelper | None = None):
        super().__init__(parent)
        self._notification_area = notification_area
        self._tray_service = tray_service
        self._window_manager = window_manager
        self._tasks_service = tasks_service
        self._appbar_manager = appbar_manager
        self._config = config or AppConfig.load()
        self._snap_layout_helper = snap_layout_helper
        self._buttons: dict[int, TaskButton] = {}
        self._update_thread: UpdateCheckThread | None = None

        self.setWindowTitle("")
        self.setMinimumWidth(72)

        # 窄边框窗体：保留系统细边框（避免无边框时透明区域点击穿透），
        # 但去掉标题栏与图标；并置顶显示。
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # 透明背景，配合 DWM Acrylic 材质透出模糊背景。
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 拖拽移动状态：记录按下时鼠标相对窗口左上角的偏移。
        self._drag_offset: QPoint | None = None

        central = QWidget(self)
        central.setMinimumSize(1, 1)
        self.setCentralWidget(central)

        # 垂直布局，两端对齐：任务按钮贴顶、托盘图标贴底，中间弹性空间撑开；
        # 所有子项水平居中。
        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, central)
        self._layout.setContentsMargins(4, 2, 4, 2)
        self._layout.setSpacing(2)

        # 顶部：任务按钮区域（固定垂直排列，按钮占满水平宽度）
        self._tasks_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self._tasks_layout.setSpacing(2)
        self._layout.addLayout(self._tasks_layout)

        # 中间弹性空间，把任务按钮与托盘图标推向两端
        self._layout.addStretch(1)

        # 底部：托盘图标区域（横排自动换行，占满宽度以便按窗口宽度换行）。
        # 垂直用 Minimum 策略，高度随换行行数（heightForWidth）自适应。
        # 追加 16px 底边距，使托盘整体离窗口底边有间距。
        self._icons_list = NotifyIconList(notification_area, tray_service, self)
        self._layout.addWidget(self._icons_list)
        self._layout.addSpacing(16)

        # 连接信号
        self._window_manager.window_added.connect(self._on_window_added)
        self._window_manager.window_removed.connect(self._on_window_removed)
        self._window_manager.window_updated.connect(self._on_window_updated)

        # 初始化现有窗口
        for window in self._window_manager.get_windows():
            self._on_window_added(window)

        # 普通窗口模式：不注册 AppBar
        if self._appbar_manager is not None:
            self._appbar_manager = None

        # 根据保存的配置恢复尺寸与位置
        self._restore_geometry()

        # 保存几何信息的防抖定时器（500ms 内无变化才写入，避免拖拽时频繁写盘）
        self._save_geometry_timer = QTimer(self)
        self._save_geometry_timer.setSingleShot(True)
        self._save_geometry_timer.timeout.connect(self._save_geometry)

        self._acrylic_applied = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # HWND 在 show 后才可用，此时启用 Acrylic 材质（仅需一次）。
        if not self._acrylic_applied:
            self._acrylic_applied = True
            self._apply_acrylic()

    def _apply_acrylic(self) -> None:
        """启用 Win11 Acrylic 亚克力背景材质（Win11 22H2+ 生效，旧系统静默忽略）。"""
        hwnd = int(self.winId())

        # 设置应用图标作为窗口图标（标题栏、Alt-Tab、任务切换等）。
        self._set_window_icon(hwnd)

        # 将 DWM 玻璃框扩展到整个客户区（margins 全 -1 = "sheet of glass"）。
        # 否则透明客户区不在 DWM 合成范围内，会显示为纯黑色。
        margins = MARGINS(-1, -1, -1, -1)
        api.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        backdrop = ctypes.c_int(constants.DWMSBT_TRANSIENTWINDOW)
        hr = api.DwmSetWindowAttribute(
            hwnd, constants.DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop), ctypes.sizeof(backdrop),
        )
        if hr != 0:
            logger.debug("启用 Acrylic 失败(HRESULT=0x%08X)，当前系统可能不支持", hr & 0xFFFFFFFF)

    def _set_window_icon(self, hwnd: int) -> None:
        """使用应用图标文件设置窗口大/小图标。"""
        icon_path = get_app_icon_path()
        if not icon_path.exists():
            logger.warning("应用图标文件不存在: %s", icon_path)
            return

        # 小图标（标题栏、任务管理器等）
        small_size = api.GetSystemMetrics(constants.SM_CXSMICON)
        hicon_small = api.LoadImageW(
            0,
            str(icon_path),
            constants.IMAGE_ICON,
            small_size,
            small_size,
            constants.LR_LOADFROMFILE | constants.LR_SHARED,
        )
        if hicon_small:
            api.SendMessageW(
                hwnd, constants.WM_SETICON, constants.ICON_SMALL, hicon_small
            )

        # 大图标（Alt-Tab、任务切换等）
        large_size = api.GetSystemMetrics(constants.SM_CXICON)
        hicon_big = api.LoadImageW(
            0,
            str(icon_path),
            constants.IMAGE_ICON,
            large_size,
            large_size,
            constants.LR_LOADFROMFILE | constants.LR_SHARED,
        )
        if hicon_big:
            api.SendMessageW(
                hwnd, constants.WM_SETICON, constants.ICON_BIG, hicon_big
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._icons_list.refresh_icon_rects()
        self._request_save_geometry()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        # 窗口移动后子图标的屏幕坐标变化，需重新上报以保证托盘菜单定位正确。
        self._icons_list.refresh_icon_rects()
        self._request_save_geometry()

    def closeEvent(self, event) -> None:
        # 关闭前立即保存一次几何信息，确保退出位置被记录
        self._save_geometry()
        super().closeEvent(event)

    def _request_save_geometry(self) -> None:
        """触发防抖保存窗口几何信息。"""
        if self._save_geometry_timer is not None:
            self._save_geometry_timer.start(500)

    def _save_geometry(self) -> None:
        """将当前窗口位置与尺寸写入配置。"""
        if self._config is None:
            return
        geo = self.geometry()
        self._config.geometry.x = geo.x()
        self._config.geometry.y = geo.y()
        self._config.geometry.width = geo.width()
        self._config.geometry.height = geo.height()
        self._config.save()

    def _restore_geometry(self) -> None:
        """从配置恢复窗口尺寸与位置，并确保不会超出屏幕。"""
        geo = self._config.geometry
        width = max(self.minimumWidth(), min(geo.width, 400))
        height = max(self.minimumHeight(), min(geo.height, 800))

        # 未记录过位置时给个合理的默认位置：主屏幕右下角
        if geo.x < 0 or geo.y < 0:
            screen = QGuiApplication.primaryScreen()
            if screen:
                rect = screen.availableGeometry()
                x = rect.right() - width
                y = rect.bottom() - height
            else:
                x, y = 100, 100
        else:
            x, y = geo.x, geo.y

        self.resize(width, height)
        self.move(x, y)
        self._ensure_geometry_on_screen()

    def _ensure_geometry_on_screen(self) -> None:
        """确保窗口整体位于某个屏幕工作区内；若超出则调整到最近的可见位置。"""
        app = QCoreApplication.instance()
        if app is None:
            return

        geo = self.geometry()
        # 先尝试查找窗口中心所在屏幕
        center = geo.center()
        screen = QGuiApplication.screenAt(center)
        if screen is None:
            # 若中心不在任何屏幕，则取离左上角最近的屏幕
            screens = QGuiApplication.screens()
            if not screens:
                return
            screen = screens[0]
            min_distance = float("inf")
            for s in screens:
                rect = s.availableGeometry()
                distance = abs(rect.x() - geo.x()) + abs(rect.y() - geo.y())
                if distance < min_distance:
                    min_distance = distance
                    screen = s

        if screen is None:
            return

        work = screen.availableGeometry()
        # 至少要保留 32x32 可见区域在屏幕内，方便用户拖拽
        min_visible = 32
        x = max(work.left() - geo.width() + min_visible, min(geo.x(), work.right() - min_visible))
        y = max(work.top() - geo.height() + min_visible, min(geo.y(), work.bottom() - min_visible))

        # 限制尺寸不超过工作区
        new_width = min(geo.width(), work.width())
        new_height = min(geo.height(), work.height())

        if (x, y, new_width, new_height) != (geo.x(), geo.y(), geo.width(), geo.height()):
            self.setGeometry(x, y, new_width, new_height)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 在窗体空白处按下左键开始拖拽移动；子控件（按钮/图标）会各自消费事件，
        # 不会传到这里，因此不会与点击操作冲突。
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            # 拖拽结束后立即保存位置，避免用户直接结束进程导致防抖定时器未触发
            self._save_geometry()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        # 窗体空白处右键菜单；子控件（任务按钮等）有自己的菜单，不会触发此处。
        menu = QMenu(self)
        menu.addAction(self.tr("Run"), self._open_run_dialog)
        menu.addAction(self.tr("Task Manager"), self._open_task_manager)
        menu.addAction(self.tr("Explorer"), self._open_explorer)
        menu.addAction(self.tr("Command Prompt"), self._open_cmd)
        menu.addSeparator()

        # 语言切换子菜单
        lang_menu = QMenu(self.tr("Language"), menu)
        current_lang = self._config.effective_language()
        for code, label in (("zh_CN", "简体中文"), ("en_US", "English")):
            action = lang_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(current_lang == code)
            action.triggered.connect(lambda checked, c=code: self._set_language(c))
        menu.addMenu(lang_menu)

        # 关闭 Aero Snap（拖动窗口时的贴靠与顶部分屏格子）
        snap_action = menu.addAction(self.tr("Disable Aero Snap"))
        snap_action.setCheckable(True)
        snap_action.setChecked(self._config.disable_snap_layout)
        snap_action.toggled.connect(self._set_disable_snap_layout)

        menu.addAction(self.tr("Check for Updates"), self._check_for_updates)

        menu.addSeparator()
        menu.addAction(self.tr("About"), self._show_about)
        menu.addAction(self.tr("Exit"), QApplication.quit)
        menu.exec(event.globalPos())

    def _open_run_dialog(self) -> None:
        """打开 Windows“运行”对话框（shell32 RunFileDlg）。"""
        try:
            shell = ctypes.windll.shell32
            # RunFileDlg 序号导出为 #61：RunFileDlg(hwnd, hIcon, lpszDir, lpszTitle, lpszDesc, flags)
            run_file_dlg = shell[61]
            run_file_dlg(int(self.winId()), 0, None, None, None, 0)
        except Exception:
            logger.exception("打开运行对话框失败")

    def _open_task_manager(self) -> None:
        """启动任务管理器。"""
        try:
            subprocess.Popen(["taskmgr.exe"])
        except Exception:
            logger.exception("启动任务管理器失败")

    def _open_explorer(self) -> None:
        try:
            subprocess.Popen(["explorer.exe"])
        except Exception:
            logger.exception("打开资源管理器失败")

    def _open_cmd(self) -> None:
        try:
            subprocess.Popen(["cmd.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception:
            logger.exception("打开命令提示符失败")

    def _set_language(self, language: str) -> None:
        """切换界面语言并持久化到配置（动态生效，已创建控件下次刷新时更新）。"""
        if self._config is None or self._config.effective_language() == language:
            return
        self._config.language = language
        self._config.save()

        qt_app = QCoreApplication.instance()
        if qt_app is None:
            return

        from remoteappdock.i18n import set_application_language
        set_application_language(qt_app, language)

    def _set_disable_snap_layout(self, enabled: bool) -> None:
        """切换 Win11 分屏禁用状态，实时生效并持久化到配置。"""
        if self._config is None or self._config.disable_snap_layout == enabled:
            return
        self._config.disable_snap_layout = enabled
        self._config.save()

        if self._snap_layout_helper is None:
            return
        if enabled:
            self._snap_layout_helper.disable()
        else:
            self._snap_layout_helper.restore()

    def _show_about(self) -> None:
        """显示关于对话框，介绍应用信息与仓库位置。"""
        repo_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
        text = self.tr(
            "<b>RemoteAppDock</b><br>"
            "Version: {version}<br><br>"
            "A Windows taskbar replacement for RDP RemoteApp environments.<br><br>"
            "Repository: <a href=\"{repo_url}\">{repo_url}</a>"
        ).format(version=APP_VERSION, repo_url=repo_url)
        # 不将对话框作为 AppBar 任务栏窗口的子窗口，避免拖移时父窗口影响其几何；
        # 使用独立顶层对话框 + 置顶 + 固定尺寸，彻底防止拖移后缩小。
        msg = QMessageBox()
        msg.setWindowModality(Qt.WindowModality.ApplicationModal)
        msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle(self.tr("About RemoteAppDock"))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        # 让 QMessageBox 内部 QLabel 的仓库链接可被点击并在默认浏览器打开；
        # 禁用自动换行，使短文本以自然宽度渲染，避免 URL 被折断。
        for label in msg.findChildren(QLabel):
            label.setOpenExternalLinks(True)
            if label.text():
                label.setWordWrap(False)
        msg.setFixedSize(msg.sizeHint())
        # 在任务栏窗口上居中显示。
        if self.isVisible():
            parent_geo = self.geometry()
            msg.move(
                parent_geo.x() + (parent_geo.width() - msg.width()) // 2,
                parent_geo.y() + (parent_geo.height() - msg.height()) // 2,
            )
        msg.exec()

    def _on_window_added(self, window) -> None:
        if window.handle in self._buttons:
            return
        button = TaskButton(window, self._tasks_service, self)
        self._buttons[window.handle] = button
        self._tasks_layout.addWidget(button)

    def _on_window_removed(self, hwnd: int) -> None:
        button = self._buttons.pop(hwnd, None)
        if button:
            self._tasks_layout.removeWidget(button)
            button.deleteLater()

    def _on_window_updated(self, window) -> None:
        button = self._buttons.get(window.handle)
        if button:
            button.update_window(window)

    def _check_for_updates(self) -> None:
        """手动触发后台更新检查。"""
        if self._update_thread is not None and self._update_thread.isRunning():
            return
        self._update_thread = UpdateCheckThread(force=True, parent=self)
        self._update_thread.finished.connect(self._on_update_finished)
        self._update_thread.error.connect(self._on_update_error)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.error.connect(self._update_thread.deleteLater)
        self._update_thread.start()

    def _on_update_finished(self, release, have_new: bool) -> None:
        """后台更新检查成功完成。"""
        self._update_thread = None
        show_update_result(self, release, have_new)

    def _on_update_error(self, message: str) -> None:
        """后台更新检查失败。"""
        self._update_thread = None
        show_update_error(self, message)
