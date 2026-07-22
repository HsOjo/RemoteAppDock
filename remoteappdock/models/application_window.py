"""窗口数据模型。"""

from dataclasses import dataclass, field


@dataclass
class ApplicationWindow:
    """表示任务栏上的一个窗口。"""

    handle: int = 0
    title: str = ""
    icon_handle: int = 0
    overlay_icon_handle: int = 0
    state: str = "normal"  # normal, minimized, maximized, active, flashing
    monitor: int = 0
    show_in_taskbar: bool = True
    can_minimize: bool = True
    proc_id: int = 0
    class_name: str = ""
    app_user_model_id: str = ""
