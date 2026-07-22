"""主任务栏窗口。"""

import ctypes
import logging
import subprocess

from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtGui import QMouseEvent, QContextMenuEvent
from PySide6.QtWidgets import QMainWindow, QWidget, QBoxLayout, QSizePolicy, QApplication, QMenu

from remoteappdock.services.notification_area import NotificationArea
from remoteappdock.services.tray_service import TrayService
from remoteappdock.services.tasks_service import WindowManager, TasksService
from remoteappdock.services.appbar_manager import AppBarManager
from remoteappdock.ui.notify_icon_list import NotifyIconList
from remoteappdock.ui.task_button import TaskButton
from remoteappdock.win32 import api, constants
from remoteappdock.win32.structs import MARGINS


logger = logging.getLogger(__name__)


class TaskbarWindow(QMainWindow):
    """主任务栏窗口，显示任务按钮与托盘图标。

    作为普通窗口运行：宽度大于高度时横向排列，高度大于宽度时纵向排列。
    """

    def __init__(self, notification_area: NotificationArea, tray_service: TrayService,
                 window_manager: WindowManager, tasks_service: TasksService,
                 appbar_manager: AppBarManager | None = None, parent=None):
        super().__init__(parent)
        self._notification_area = notification_area
        self._tray_service = tray_service
        self._window_manager = window_manager
        self._tasks_service = tasks_service
        self._appbar_manager = appbar_manager
        self._buttons: dict[int, TaskButton] = {}

        self.setWindowTitle("")
        self.resize(128, 480)
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

        # 强制移除标题栏图标：置空 ICON_SMALL/ICON_BIG，避免 Windows 继承默认图标。
        api.SendMessageW(hwnd, constants.WM_SETICON, constants.ICON_SMALL, 0)
        api.SendMessageW(hwnd, constants.WM_SETICON, constants.ICON_BIG, 0)

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._icons_list.refresh_icon_rects()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        # 窗口移动后子图标的屏幕坐标变化，需重新上报以保证托盘菜单定位正确。
        self._icons_list.refresh_icon_rects()

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
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        # 窗体空白处右键菜单；子控件（任务按钮等）有自己的菜单，不会触发此处。
        menu = QMenu(self)
        menu.addAction("运行程序", self._open_run_dialog)
        menu.addAction("打开资源管理器", self._open_explorer)
        menu.addAction("打开命令提示符", self._open_cmd)
        menu.addSeparator()
        menu.addAction("退出", QApplication.quit)
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
