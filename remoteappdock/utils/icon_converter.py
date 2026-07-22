"""HICON 与图标转换工具。"""

import logging
import ctypes
from ctypes import byref, sizeof, create_unicode_buffer

from PySide6.QtGui import QImage, QPixmap

from remoteappdock.win32 import api, constants
from remoteappdock.win32.structs import HICON, SHFILEINFO, ICONINFO, BITMAPINFO, BITMAPINFOHEADER, RGBQUAD


logger = logging.getLogger(__name__)


class IconConverter:
    """将 Win32 HICON 转换为 Qt QPixmap。"""

    @staticmethod
    def hicon_to_pixmap(hicon: int) -> QPixmap | None:
        """将 HICON 转换为 QPixmap。"""
        if not hicon:
            return None
        try:
            # 先用 GetIconInfo 校验句柄并获取尺寸
            icon_info = ICONINFO()
            if not api.GetIconInfo(hicon, byref(icon_info)):
                logger.debug("跳过无效 HICON: hIcon=0x%X", hicon)
                return None
            try:
                # 尝试 Qt 内置转换
                image = QImage.fromHICON(hicon)
                if not image.isNull():
                    return QPixmap.fromImage(image)

                # Qt 内置转换失败时，手动通过 DrawIconEx 提取位图
                return IconConverter._draw_icon_to_pixmap(hicon, icon_info)
            finally:
                if icon_info.hbmMask:
                    api.DeleteObject(icon_info.hbmMask)
                if icon_info.hbmColor:
                    api.DeleteObject(icon_info.hbmColor)
        except Exception:
            logger.exception("HICON 转 QPixmap 失败: hIcon=%s", hicon)
            return None

    @staticmethod
    def _draw_icon_to_pixmap(hicon: int, icon_info: ICONINFO) -> QPixmap | None:
        """通过 DrawIconEx 将图标绘制到内存位图并转为 QPixmap。"""
        try:
            # 获取位图尺寸
            bmp_info = BITMAPINFO()
            bmp_info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
            hdc_screen = api.GetDC(0)
            if not hdc_screen:
                return None
            try:
                # 先从掩码位图获取宽高
                api.GetDIBits(hdc_screen, icon_info.hbmMask, 0, 0, None, byref(bmp_info), 0)
                width = abs(bmp_info.bmiHeader.biWidth)
                height = abs(bmp_info.bmiHeader.biHeight)
                if width == 0 or height == 0:
                    width = height = 16

                hdc_mem = api.CreateCompatibleDC(hdc_screen)
                if not hdc_mem:
                    return None
                try:
                    # 创建 32 位 RGBA 位图
                    bmp_info.bmiHeader.biWidth = width
                    bmp_info.bmiHeader.biHeight = -height  # 自顶向下
                    bmp_info.bmiHeader.biPlanes = 1
                    bmp_info.bmiHeader.biBitCount = 32
                    bmp_info.bmiHeader.biCompression = 0  # BI_RGB
                    bmp_info.bmiHeader.biSizeImage = width * height * 4

                    hbm = api.CreateDIBSection(hdc_screen, byref(bmp_info), 0, None, None, 0)
                    if not hbm:
                        return None
                    try:
                        old_bmp = api.SelectObject(hdc_mem, hbm)
                        api.DrawIconEx(hdc_mem, 0, 0, hicon, width, height, 0, 0, 0x0003)  # DI_NORMAL
                        api.SelectObject(hdc_mem, old_bmp)

                        # 读取位图数据
                        bits = (ctypes.c_byte * (width * height * 4))()
                        api.GetDIBits(hdc_screen, hbm, 0, height, bits, byref(bmp_info), 0)
                        image = QImage(bytes(bits), width, height, QImage.Format.Format_ARGB32)
                        return QPixmap.fromImage(image.copy())
                    finally:
                        api.DeleteObject(hbm)
                finally:
                    api.DeleteDC(hdc_mem)
            finally:
                api.ReleaseDC(0, hdc_screen)
        except Exception:
            logger.exception("DrawIconEx 提取图标失败")
            return None

    @staticmethod
    def hicon_to_path(hicon: int) -> str | None:
        """占位：HICON 没有文件路径，返回空。"""
        return None

    @staticmethod
    def extract_icon_from_file(path: str, index: int = 0, large: bool = True) -> int:
        """从可执行文件或 DLL 提取图标句柄。"""
        hicon_large = HICON()
        hicon_small = HICON()

        if large:
            count = api.ExtractIconExW(path, index, byref(hicon_large), None, 1)
            if count > 0:
                return hicon_large.value
        else:
            count = api.ExtractIconExW(path, index, None, byref(hicon_small), 1)
            if count > 0:
                return hicon_small.value
        return 0

    @staticmethod
    def extract_icon_from_file_info(path: str, large: bool = False) -> int:
        """通过 SHGetFileInfo 获取文件图标句柄。"""
        if not path:
            return 0
        shinfo = SHFILEINFO()
        flags = constants.SHGFI_ICON
        flags |= constants.SHGFI_LARGEICON if large else constants.SHGFI_SMALLICON
        api.SHGetFileInfoW(path, 0, byref(shinfo), sizeof(shinfo), flags)
        return shinfo.hIcon

    @staticmethod
    def extract_icon_from_window(hwnd: int, large: bool = False) -> int:
        """根据窗口句柄获取其进程可执行文件的图标句柄。"""
        if not hwnd:
            return 0
        pid = api.get_window_process_id(hwnd)
        h_process = api.OpenProcess(constants.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            h_process = api.OpenProcess(constants.PROCESS_QUERY_INFORMATION, False, pid)
        if not h_process:
            return 0
        try:
            buffer = create_unicode_buffer(constants.MAX_PATH)
            size = ctypes.c_ulong(constants.MAX_PATH)
            if api.QueryFullProcessImageNameW(h_process, 0, buffer, byref(size)):
                path = buffer.value
                # 优先使用 SHGetFileInfo 获取系统缓存图标，更稳定
                hicon = IconConverter.extract_icon_from_file_info(path, large=large)
                if hicon:
                    return hicon
                return IconConverter.extract_icon_from_file(path, index=0, large=large)
            return 0
        finally:
            api.CloseHandle(h_process)
