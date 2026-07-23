# RemoteAppDock

![RemoteAppDock 图标](assets/app-icon-256.png)

[English](README.md) | 简体中文

用 Python 实现的 Windows 任务栏替代方案，面向 RDP RemoteApp 环境部署。

## 使用场景

RemoteAppDock 面向通过 RDP RemoteApp 运行 Windows 程序、但又缺少完整 Windows 桌面外壳体验的用户。它主要解决 RemoteApp 会话中常见的以下缺失功能：

- **窗口管理**：RemoteApp 通常只显示单个程序窗口，RemoteAppDock 提供类任务栏的窗口列表，可查看并切换所有已打开的窗口。
- **托盘图标显示**：许多 Windows 程序将重要控制入口放在通知区域（系统托盘）。RemoteAppDock 承载这些托盘图标，使其在 RemoteApp 会话中可见、可用。
- **程序启动台**：RemoteApp 会话通常没有开始菜单或启动台，RemoteAppDock 提供简单的程序启动入口，方便在会话中启动其他程序。

关于如何在 RDP 中创建和发布 RemoteApp，可参考 [RemoteApp Tool](https://github.com/kimmknight/remoteapptool) 的说明。

## 范围

- 窗口管理（任务列表）
- 托盘管理（通知区域）
- 任务栏定位（AppBar）
- 多语言（i18n）

## 技术栈

- Python 3.13
- PySide6
- ctypes / pywin32
- PyInstaller
- uv

## 开发

```powershell
uv sync
uv run python -m remoteappdock.main
```

## 测试

```powershell
uv run --group dev pytest
```

## 打包

```powershell
uv run python -m PyInstaller RemoteAppDock.spec --clean --noconfirm
```

## 致谢

本项目的托盘协议、Explorer 任务栏控制等底层实现，参考并移植自
[ManagedShell](https://github.com/cairoshell/ManagedShell)（C# / .NET，
Apache License 2.0）。相关文件已在文件头标注衍生关系，归属详见 `NOTICE`，
Apache-2.0 许可全文见 `third_party/ManagedShell/LICENSE`。

## 许可

本项目整体依据 [GNU GPL v3](LICENSE) 或（由你选择）任何更新版本发布。
其中移植自 ManagedShell 的部分依据 Apache-2.0 授权并入本项目（Apache-2.0
与 GPLv3 兼容），需同时遵守其归属要求。
