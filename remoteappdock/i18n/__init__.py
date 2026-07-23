"""国际化与翻译加载。"""

import logging
import os
import sys

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


DEFAULT_LANGUAGE = "en_US"
SUPPORTED_LANGUAGES = {"zh_CN", "en_US"}

_current_translator: QTranslator | None = None


def get_i18n_dir() -> str:
    """返回翻译文件所在目录。兼容开发环境与 PyInstaller 打包环境。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "remoteappdock", "i18n")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)))


def normalize_language(language: str) -> str:
    """将语言代码归一化为受支持的语言；auto 则跟随系统语言。"""
    if language and language != "auto" and language in SUPPORTED_LANGUAGES:
        return language
    locale_name = QLocale.system().name()
    if locale_name.startswith("zh"):
        return "zh_CN"
    return "en_US"


def install_translator(app: QApplication, language: str) -> QTranslator | None:
    """为应用安装指定语言的翻译器；返回安装的翻译器实例。"""
    global _current_translator

    lang = normalize_language(language)
    if lang == DEFAULT_LANGUAGE:
        _current_translator = None
        return None

    translator = QTranslator(app)
    i18n_dir = get_i18n_dir()
    qm_path = os.path.join(i18n_dir, f"{lang}.qm")

    if os.path.exists(qm_path):
        loaded = translator.load(qm_path)
    else:
        loaded = translator.load(QLocale(lang), lang, "", i18n_dir, ".qm")

    if loaded:
        app.installTranslator(translator)
        _current_translator = translator
        logger.debug("已安装翻译: %s", lang)
        return translator

    logger.warning("未找到翻译文件，使用默认英文: %s", qm_path)
    _current_translator = None
    return None


def set_application_language(app: QApplication, language: str) -> None:
    """切换应用语言：移除旧翻译器并安装新翻译器。"""
    global _current_translator

    if _current_translator is not None:
        app.removeTranslator(_current_translator)
        _current_translator = None

    install_translator(app, language)
