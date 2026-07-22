"""RemoteAppDock 应用入口。"""

import sys

import signal

from PySide6.QtWidgets import QApplication

from remoteappdock.app import App


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RemoteAppDock")
    app.setApplicationVersion("0.1.0")

    # 全局 QToolTip 样式：明确前景/背景色，避免继承深色主题后白底白字或黑底黑字。
    app.setStyleSheet(
        "QToolTip { color: #1a1a1a; background-color: #ffffcc; "
        "border: 1px solid #999; padding: 2px; }"
    )

    retro_app = App()
    retro_app.start()

    # 确保任何退出方式（窗口关闭、Ctrl+C、正常退出）都会清理并恢复 Explorer 任务栏
    app.aboutToQuit.connect(retro_app.shutdown)

    def _sigint_handler(signum, frame):
        app.quit()

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        sys.exit(app.exec())
    finally:
        # aboutToQuit 在 exec() 返回前触发，此处作为最终兜底
        retro_app.shutdown()


if __name__ == "__main__":
    main()
