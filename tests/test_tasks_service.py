import pytest

from PySide6.QtCore import QCoreApplication

from remoteappdock.services.tasks_service import WindowManager, TasksService


@pytest.fixture
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_tasks_service_starts(qt_app):
    """验证 TasksService 能注册 Shell Hook 并枚举窗口。"""
    wm = WindowManager()
    service = TasksService(wm)
    service.start()

    try:
        assert service._hwnd != 0
        assert service._shell_hook_msg != 0
        assert len(wm.get_windows()) >= 1
        # 至少应该包含当前测试控制台窗口
        titles = [w.title for w in wm.get_windows()]
        print("枚举到的窗口:", titles)
    finally:
        service.stop()


def test_window_manager_filter():
    """验证 WindowManager 的过滤逻辑。"""
    wm = WindowManager()
    # 桌面窗口不应出现在任务栏
    from remoteappdock.win32 import api
    desktop = api.GetDesktopWindow()
    assert wm.add_or_update(desktop) is None
    assert wm.get_window(desktop) is None
