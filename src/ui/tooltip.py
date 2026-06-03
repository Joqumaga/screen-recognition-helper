"""Tooltip 提示工具。

在鼠标悬停时显示简短的引导说明文字，
帮助新手理解各控件的用途。

用法:
    tooltip = Tooltip(widget, "点击这里开始监控")
    tooltip = Tooltip(widget, "设置扫描频率", delay=1.0)
"""

from __future__ import annotations

import customtkinter as ctk

from config import COLOR_TEXT, COLOR_BG, COLOR_BORDER


class Tooltip:
    """控件悬停提示。

    当鼠标进入控件区域时，延迟显示提示框，
    移出时自动隐藏。

    Args:
        widget: 要附加提示的控件
        text: 提示文字
        delay: 悬停后延迟显示秒数（默认 0.5s）
        wrap_length: 文字换行宽度（默认 200px）
    """

    def __init__(
        self,
        widget: ctk.CTkBaseClass,
        text: str,
        delay: float = 0.5,
        wrap_length: int = 200,
    ):
        self._widget = widget
        self._text = text
        self._delay = delay
        self._wrap_length = wrap_length
        self._tooltip_window: ctk.CTkToplevel | None = None
        self._after_id: str | None = None

        # 绑定鼠标事件
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        """鼠标进入：启动定时器准备显示提示。"""
        # 如果已有其他提示，取消
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None

        self._after_id = self._widget.after(
            int(self._delay * 1000),
            self._show_tooltip,
        )

    def _on_leave(self, event=None):
        """鼠标离开：取消定时器并隐藏提示。"""
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide_tooltip()

    def _show_tooltip(self):
        """显示提示浮窗。"""
        if self._tooltip_window is not None:
            return

        self._tooltip_window = ctk.CTkToplevel(self._widget)
        self._tooltip_window.wm_overrideredirect(True)  # 无边框
        self._tooltip_window.attributes("-topmost", True)
        self._tooltip_window.attributes("-alpha", 0.95)

        # 提示内容框
        frame = ctk.CTkFrame(
            self._tooltip_window,
            fg_color="#FFFFF0",      # 浅米黄色背景，与主色调区分
            corner_radius=6,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(
            frame,
            text=self._text,
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT,
            wraplength=self._wrap_length,
            justify="left",
            padx=8,
            pady=6,
        ).pack()

        # 定位：在控件下方显示
        self._position_tooltip()

    def _position_tooltip(self):
        """将提示框定位在控件下方偏右位置。"""
        if not self._tooltip_window:
            return

        try:
            # 获取控件在屏幕上的坐标
            x = self._widget.winfo_rootx()
            y = self._widget.winfo_rooty()
            w = self._widget.winfo_width()
            h = self._widget.winfo_height()

            # 更新窗口几何信息以便获取提示框大小
            self._tooltip_window.update_idletasks()
            tw = self._tooltip_window.winfo_reqwidth()
            th = self._tooltip_window.winfo_reqheight()

            # 默认放在控件下方
            tip_x = x + max(0, (w - tw) // 2)  # 居中对齐
            tip_y = y + h + 5

            # 检查是否超出屏幕底部
            screen_h = self._widget.winfo_screenheight()
            if tip_y + th > screen_h:
                tip_y = y - th - 5  # 放到上方

            # 检查是否超出屏幕右侧
            screen_w = self._widget.winfo_screenwidth()
            if tip_x + tw > screen_w:
                tip_x = screen_w - tw - 10
            if tip_x < 0:
                tip_x = 10

            self._tooltip_window.geometry(f"+{int(tip_x)}+{int(tip_y)}")
        except Exception:
            pass

    def _hide_tooltip(self):
        """隐藏提示浮窗。"""
        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except Exception:
                pass
            self._tooltip_window = None

    def destroy(self):
        """清理资源。"""
        if self._after_id:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._hide_tooltip()

        # 解绑事件
        try:
            self._widget.unbind("<Enter>")
            self._widget.unbind("<Leave>")
            self._widget.unbind("<ButtonPress>")
        except Exception:
            pass
