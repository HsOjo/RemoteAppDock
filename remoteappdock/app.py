"""应用生命周期与单实例管理。"""

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QMainWindow

from remoteappdock.ui.taskbar_window import TaskbarWindow
from remoteappdock.services.notification_area import NotificationArea
from remoteappdock.services.tray_service import TrayService
from remoteappdock.services.explorer_tray_service import ExplorerTrayService
from remoteappdock.services.tasks_service import WindowManager, TasksService
from remoteappdock.services.appbar_manager import AppBarManager
from remoteappdock.services.hotkey_manager import HotkeyManager
from remoteappdock.services.explorer_helper import ExplorerHelper


class App:
    """管理应用启动、关闭与单实例。"""

    def __init__(self):
        self._main_window: QMainWindow | None = None
        self._notification_area: NotificationArea | None = None
        self._tray_service: TrayService | None = None
        self._window_manager: WindowManager | None = None
        self._tasks_service: TasksService | None = None
        self._appbar_manager: AppBarManager | None = None
        self._hotkey_manager: HotkeyManager | None = None
        self._explorer_helper: ExplorerHelper | None = None
        self._timer: QTimer | None = None

    def start(self):
        QCoreApplication.setApplicationName("RemoteAppDock")
        QCoreApplication.setOrganizationName("remoteappdock")

        self._notification_area = NotificationArea()

        # 在隐藏 Explorer 任务栏之前，先枚举其现有托盘图标（仅 Win10 及带
        # ToolbarWindow32 的旧版任务栏有效；Win11 XAML 托盘会返回 0，不报错）。
        # 补齐启动前已注册、不会响应 TaskbarCreated 广播的常驻第三方图标。
        ExplorerTrayService(self._notification_area).run()

        # 隐藏 Explorer 任务栏，避免 RemoteAppDock 与之冲突
        self._explorer_helper = ExplorerHelper()
        self._explorer_helper.hide_taskbar()

        # 托盘服务：接管后续新注册的托盘图标
        self._tray_service = TrayService(self._notification_area)
        self._tray_service.start()

        # 任务列表服务
        self._window_manager = WindowManager()
        self._tasks_service = TasksService(self._window_manager)
        self._tasks_service.start()

        # AppBar 管理
        self._appbar_manager = AppBarManager(edge="bottom", auto_hide=False)

        # 热键管理（可选增强）
        self._hotkey_manager = HotkeyManager(self._tasks_service)
        self._hotkey_manager.start()

        # 主窗口
        self._main_window = TaskbarWindow(
            self._notification_area, self._tray_service,
            self._window_manager, self._tasks_service,
            self._appbar_manager
        )
        self._main_window.show()

        # 每 50ms 从 Win32 线程 drain 事件到主线程
        self._timer = QTimer()
        self._timer.timeout.connect(self._drain_all_events)
        self._timer.start(50)

        # 当服务产生事件时立即触发 drain
        self._tray_service.icon_event.connect(self._drain_all_events)
        self._tasks_service.window_event.connect(self._drain_all_events)

    def _drain_all_events(self) -> None:
        if self._tray_service is not None:
            self._tray_service.process_events()
        if self._tasks_service is not None:
            self._tasks_service.process_events()

    def shutdown(self):
        if self._main_window is not None:
            self._main_window.close()
            self._main_window = None
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._appbar_manager is not None:
            self._appbar_manager.unregister()
            self._appbar_manager = None
        if self._hotkey_manager is not None:
            self._hotkey_manager.stop()
            self._hotkey_manager = None
        if self._tasks_service is not None:
            self._tasks_service.stop()
            self._tasks_service = None
            self._window_manager = None
        # 必须在恢复 Explorer 任务栏之前停止我们自己的 Shell_TrayWnd，
        # 否则 FindWindow('Shell_TrayWnd') 会找到我们自己的窗口，导致恢复失败。
        if self._tray_service is not None:
            self._tray_service.stop()
            self._tray_service = None
            self._notification_area = None
        if self._explorer_helper is not None:
            self._explorer_helper.show_taskbar()
            self._explorer_helper = None
