"""鼠标点击控制模块。

基于 PyAutoGUI 实现鼠标移动和点击，
支持点击延时和随机偏移（模拟更自然的点击行为）。
"""

from __future__ import annotations

import random
import time

import pyautogui

# 关闭 PyAutoGUI 的安全失效保护（防止鼠标移动到角落时抛出异常）
pyautogui.FAILSAFE = False


class MouseClicker:
    """鼠标点击控制器。

    用法:
        clicker = MouseClicker()
        clicker.click_at(100, 200)   # 在屏幕坐标 (100, 200) 处点击
        clicker.click_center(result) # 在 OCRResult 的中心点击

    支持动态调节：
        clicker.delay_ms = 200      # 改为 200ms 延时
        clicker.area_radius = 10    # 改为 10px 随机偏移范围
    """

    def __init__(self, delay_ms: int = 50, area_radius: int = 5):
        """
        Args:
            delay_ms: 移动鼠标后到点击之间的延时（毫秒）
            area_radius: 点击位置随机偏移的半径（像素），
                        0 表示精确点击中心。
        """
        self._delay = delay_ms / 1000.0       # 内部存储秒
        self._radius = area_radius

    # ── 属性 ──────────────────────────────────────

    @property
    def delay_ms(self) -> int:
        """点击延时（毫秒）。"""
        return int(self._delay * 1000)

    @delay_ms.setter
    def delay_ms(self, value: int):
        self._delay = max(0, value) / 1000.0

    @property
    def area_radius(self) -> int:
        """点击随机偏移半径（像素）。"""
        return self._radius

    @area_radius.setter
    def area_radius(self, value: int):
        self._radius = max(0, value)

    # ── 点击方法 ──────────────────────────────────

    def click_at(self, x: int, y: int):
        """移动到屏幕坐标 (x, y) 并点击。

        Args:
            x: 屏幕横坐标
            y: 屏幕纵坐标
        """
        # 计算随机偏移
        if self._radius > 0:
            offset_x = random.randint(-self._radius, self._radius)
            offset_y = random.randint(-self._radius, self._radius)
        else:
            offset_x = offset_y = 0

        target_x = x + offset_x
        target_y = y + offset_y

        # 确保不会移出屏幕边界
        screen_w, screen_h = pyautogui.size()
        target_x = max(0, min(target_x, screen_w - 1))
        target_y = max(0, min(target_y, screen_h - 1))

        # 移动 + 点击
        pyautogui.moveTo(target_x, target_y, duration=0.05)
        time.sleep(self._delay)
        pyautogui.click()

    def click_at_region_offset(
        self,
        screen_x: int,
        screen_y: int,
        region_left: int,
        region_top: int,
    ):
        """将相对于区域的坐标转换为屏幕坐标后点击。

        如果 OCR 返回的 center() 是相对于截图区域的偏移，
        需要加上区域的屏幕左上角坐标才是真实屏幕位置。

        Args:
            screen_x: OCR 结果中心 x（相对于区域）
            screen_y: OCR 结果中心 y（相对于区域）
            region_left: 区域的屏幕 left
            region_top: 区域的屏幕 top
        """
        abs_x = region_left + screen_x
        abs_y = region_top + screen_y
        self.click_at(abs_x, abs_y)
