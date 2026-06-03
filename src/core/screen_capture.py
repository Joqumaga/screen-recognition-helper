"""屏幕截图封装。

基于 mss 库实现高性能屏幕区域截图，支持返回 numpy 数组和 PIL Image。
mss 底层调用 Windows GDI，速度远超 pyautogui 截图。
"""

from __future__ import annotations

import threading

import mss
import numpy as np
from PIL import Image


class ScreenCapture:
    """屏幕截图工具（线程安全）。

    每个线程自动持有独立的 mss 实例，避免 thread-local srcdc 未初始化错误。

    用法:
        cap = ScreenCapture()
        # 截取指定区域，返回 BGRA numpy 数组
        img_bgra = cap.capture({"left": 0, "top": 0, "width": 200, "height": 100})
        # 截取指定区域，返回 PIL Image
        img_pil = cap.capture_pil({"left": 0, "top": 0, "width": 200, "height": 100})
    """

    def __init__(self):
        self._local = threading.local()

    @property
    def _sct(self) -> mss.mss:
        """获取当前线程的 mss 实例（延迟创建，自动缓存）。"""
        if not hasattr(self._local, '_sct'):
            self._local._sct = mss.mss()
        return self._local._sct

    def capture(self, region: dict) -> np.ndarray:
        """截取指定屏幕区域，返回 BGRA 格式的 numpy 数组。

        Args:
            region: 包含 left, top, width, height 四个键的字典。

        Returns:
            shape=(height, width, 4) 的 BGRA numpy 数组。
        """
        screenshot = self._sct.grab({
            "left": region["left"],
            "top": region["top"],
            "width": region["width"],
            "height": region["height"],
        })
        return np.array(screenshot)

    def capture_pil(self, region: dict) -> Image.Image:
        """截取指定屏幕区域，返回 PIL Image（RGB 格式）。

        Args:
            region: 包含 left, top, width, height 四个键的字典。

        Returns:
            RGB 格式的 PIL Image。
        """
        screenshot = self._sct.grab({
            "left": region["left"],
            "top": region["top"],
            "width": region["width"],
            "height": region["height"],
        })
        return Image.frombytes("RGB", screenshot.size, screenshot.rgb)
