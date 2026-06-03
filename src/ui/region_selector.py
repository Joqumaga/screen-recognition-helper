"""全屏区域选择覆盖层。

通过全屏半透明遮罩，让用户用鼠标拖拽框选屏幕上的矩形区域。
支持取消操作（按 Escape），返回选中区域的左上角坐标和宽高。
"""

import tkinter as tk
from tkinter import Canvas

# 覆盖层外观
OVERLAY_ALPHA = 0.40         # 遮罩透明度（0=全透明，1=不透明）
RECT_OUTLINE_COLOR = "#FFD700"  # 选框边框色（金色，高对比度）
RECT_OUTLINE_WIDTH = 3       # 选框边框粗细


class RegionSelector:
    """全屏半透明选择覆盖层。

    使用方式:
        selector = RegionSelector()
        result = selector.select(parent_window)
        if result:
            left, top, width, height = result
    """

    def __init__(self):
        self._overlay = None
        self._canvas = None
        self._start_x = None
        self._start_y = None
        self._rect_id = None
        self._result = None

    def select(self, parent: tk.Tk) -> tuple[int, int, int, int] | None:
        """阻塞式打开覆盖层，等待用户框选。

        Args:
            parent: 父窗口（用于获取屏幕尺寸和模态挂载）

        Returns:
            (left, top, width, height) 元组；用户按 Escape 或选择过小则返回 None
        """
        self._result = None

        # 获取屏幕尺寸
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()

        # 创建全屏覆盖窗口
        self._overlay = tk.Toplevel(parent)
        self._overlay.title("选择监控区域 — 拖拽框选，按 Esc 取消")
        self._overlay.overrideredirect(True)
        self._overlay.geometry(f"{screen_w}x{screen_h}+0+0")
        self._overlay.attributes("-alpha", OVERLAY_ALPHA)
        self._overlay.attributes("-topmost", True)
        self._overlay.configure(bg="black", cursor="crosshair")

        # Canvas 用于绘制选框
        self._canvas = Canvas(
            self._overlay,
            bg="black",
            highlightthickness=0,
            cursor="crosshair",
        )
        self._canvas.pack(fill="both", expand=True)

        # 绑定鼠标事件
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

        # Escape 取消
        self._overlay.bind("<Escape>", lambda e: self._cancel())

        # 模态运行
        self._overlay.grab_set()
        self._overlay.focus_set()
        parent.wait_window(self._overlay)

        return self._result

    def _on_press(self, event: tk.Event) -> None:
        """鼠标按下：记录起始坐标，创建选框矩形。"""
        self._start_x = self._canvas.canvasx(event.x)
        self._start_y = self._canvas.canvasy(event.y)
        self._rect_id = self._canvas.create_rectangle(
            self._start_x,
            self._start_y,
            self._start_x,
            self._start_y,
            outline=RECT_OUTLINE_COLOR,
            width=RECT_OUTLINE_WIDTH,
            fill="",
            dash=(8, 4),            # 虚线，视觉上更清晰
        )

    def _on_drag(self, event: tk.Event) -> None:
        """鼠标拖拽：实时更新选框大小。"""
        if self._rect_id:
            x = self._canvas.canvasx(event.x)
            y = self._canvas.canvasy(event.y)
            self._canvas.coords(
                self._rect_id,
                self._start_x, self._start_y,
                x, y,
            )

    def _on_release(self, event: tk.Event) -> None:
        """鼠标释放：计算最终坐标，关闭覆盖层。"""
        if not self._rect_id:
            return

        x1, y1, x2, y2 = self._canvas.coords(self._rect_id)
        left = int(min(x1, x2))
        top = int(min(y1, y2))
        width = int(abs(x2 - x1))
        height = int(abs(y2 - y1))

        # 忽略过小的选择（＜15 像素，视为误触）
        if width < 15 or height < 15:
            self._cancel()
            return

        self._result = (left, top, width, height)
        self._close()

    def _cancel(self) -> None:
        """取消选择。"""
        self._result = None
        self._close()

    def _close(self) -> None:
        """关闭覆盖层，释放资源。"""
        if self._overlay:
            self._overlay.grab_release()
            self._overlay.destroy()
            self._overlay = None
