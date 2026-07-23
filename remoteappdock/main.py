"""RemoteAppDock 应用入口。

RemoteAppDock - Windows 任务栏替代方案。
Copyright (C) 2026 HsOjo

本程序为自由软件：你可以依据自由软件基金会发布的 GNU 通用公共许可证
（GPL）第 3 版，或（由你选择）任何更新版本，重新发布和/或修改它。

本程序基于"希望其有用"的目的发布，但不提供任何担保；甚至不含对适销性或
特定用途适用性的默示担保。详见 GNU 通用公共许可证。

你应已随本程序收到一份 GNU 通用公共许可证副本（见项目根目录 LICENSE）。
如果没有，请参见 <https://www.gnu.org/licenses/>。

本项目部分内容改编自 ManagedShell（Apache-2.0），归属说明见 NOTICE 文件。
"""

import sys

import signal

from PySide6.QtWidgets import QApplication

from remoteappdock.app import App
from remoteappdock.config import AppConfig
from remoteappdock.i18n import install_translator
from remoteappdock.single_instance import SingleInstanceManager
from remoteappdock.version import APP_VERSION


def main():
    single = SingleInstanceManager()
    if not single.try_acquire():
        # 已有实例在运行：尝试激活现有窗口后退出
        single.activate_existing_instance()
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName("RemoteAppDock")
    app.setOrganizationName("remoteappdock")
    app.setApplicationVersion(APP_VERSION)

    # 加载配置（必须在 setOrganizationName 之后，否则 QStandardPaths 路径不一致）
    config = AppConfig.load()
    install_translator(app, config.effective_language())

    # 全局 QToolTip 样式：明确前景/背景色，避免继承深色主题后白底白字或黑底黑字。
    app.setStyleSheet(
        "QToolTip { color: #1a1a1a; background-color: #ffffcc; "
        "border: 1px solid #999; padding: 2px; }"
    )

    retro_app = App(config)
    single.set_on_activate(retro_app.activate)
    retro_app.add_drain_callback(single.process_activate_event)
    single.start_listener()
    retro_app.start()

    # 确保任何退出方式（窗口关闭、Ctrl+C、正常退出）都会清理并恢复 Explorer 任务栏
    app.aboutToQuit.connect(retro_app.shutdown)
    app.aboutToQuit.connect(single.release)

    def _sigint_handler(signum, frame):
        app.quit()

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        sys.exit(app.exec())
    finally:
        # aboutToQuit 在 exec() 返回前触发，此处作为最终兜底
        retro_app.shutdown()
        single.release()


if __name__ == "__main__":
    main()
