"""程序入口。

启动主窗口，运行游戏辅助工具。
兼容 Python 源码运行和 PyInstaller 打包两种模式。
"""

import sys
import os


def _setup_module_path():
    """根据运行环境（源码/PyInstaller）设置模块搜索路径。

    - 源码模式: __file__ = src/main.py → 添加 src/ 目录到路径
    - PyInstaller: sys._MEIPASS = 临时解压目录 → 添加 MEIPASS 到路径
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包模式：所有模块解压在 sys._MEIPASS 下
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and meipass not in sys.path:
            sys.path.insert(0, meipass)
    else:
        # 源码运行模式：添加 src/ 目录到搜索路径
        _dir = os.path.dirname(os.path.abspath(__file__))
        if _dir not in sys.path:
            sys.path.insert(0, _dir)


_setup_module_path()

import customtkinter as ctk
from ui.app_window import AppWindow

if __name__ == "__main__":
    # ── 全局主题设置 ──
    ctk.set_appearance_mode("light")       # 浅色模式
    ctk.set_default_color_theme("blue")    # 基础蓝色主题

    app = AppWindow()
    app.mainloop()
