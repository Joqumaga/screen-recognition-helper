"""迷你浮动指示窗。

当主窗口最小化时显示，提供监控状态一览和快速操作。
支持鼠标拖拽移动，始终置顶显示。
"""

from __future__ import annotations

import customtkinter as ctk

from config import (
    COLOR_PRIMARY, COLOR_BG, COLOR_TEXT, COLOR_TEXT_SECONDARY,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_DISABLED,
)


class FloatingIndicator(ctk.CTkToplevel):
    """迷你浮动指示窗。

    显示：状态指示点 + 匹配计数 + 恢复/停止/退出按钮。
    无标题栏，可用鼠标拖拽移动。

    Args:
        on_restore: 恢复主窗口回调
        on_stop: 停止监控回调
        on_exit: 退出应用回调
    """

    def __init__(self, on_restore=None, on_stop=None, on_exit=None):
        super().__init__()
        self._on_restore = on_restore
        self._on_stop = on_stop
        self._on_exit = on_exit

        # ── 窗口设置 ──
        self.overrideredirect(True)           # 无标题栏
        self.attributes("-topmost", True)     # 始终置顶
        self.configure(fg_color=COLOR_BG)

        self._win_w = 230
        self._win_h = 65
        self.geometry(f"{self._win_w}x{self._win_h}")

        # 圆角外观：用内部 Frame 模拟圆角卡片
        self._outer = ctk.CTkFrame(
            self,
            fg_color="white",
            corner_radius=12,
            border_width=1,
            border_color=COLOR_PRIMARY,
        )
        self._outer.pack(fill="both", expand=True, padx=2, pady=2)

        self._build_ui()

        # ── 拖拽支持 ──
        self._drag_x = 0
        self._drag_y = 0
        self._outer.bind("<Button-1>", self._on_drag_start)
        self._outer.bind("<B1-Motion>", self._on_drag_motion)
        for child in self._outer.winfo_children():
            child.bind("<Button-1>", self._on_drag_start)
            child.bind("<B1-Motion>", self._on_drag_motion)

        # 窗口位置：屏幕右下角
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{sw - self._win_w - 30}+{sh - self._win_h - 60}")

        self._monitoring = False
        self._match_count = 0

    def _build_ui(self):
        """构建浮动窗口 UI。"""
        # ── 顶行：状态指示 + 匹配计数 + 恢复按钮 ──
        top_row = ctk.CTkFrame(self._outer, fg_color="transparent")
        top_row.pack(fill="x", padx=8, pady=(6, 0))

        # 状态圆点
        self._status_dot = ctk.CTkLabel(
            top_row,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color=COLOR_DISABLED,
            width=18,
        )
        self._status_dot.pack(side="left")

        self._status_label = ctk.CTkLabel(
            top_row,
            text="已停止",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT,
        )
        self._status_label.pack(side="left", padx=(2, 15))

        self._match_label = ctk.CTkLabel(
            top_row,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._match_label.pack(side="left", padx=(0, 10))

        # 恢复按钮
        btn_restore = ctk.CTkButton(
            top_row,
            text="⬆ 恢复",
            font=ctk.CTkFont(size=10),
            fg_color=COLOR_PRIMARY,
            hover_color="#5BA3D9",
            text_color="white",
            height=22,
            width=55,
            command=self._on_restore_cmd,
        )
        btn_restore.pack(side="right")

        # ── 底行：停止 + 退出按钮 ──
        bot_row = ctk.CTkFrame(self._outer, fg_color="transparent")
        bot_row.pack(fill="x", padx=8, pady=(4, 6))

        self._btn_stop = ctk.CTkButton(
            bot_row,
            text="■ 停止",
            font=ctk.CTkFont(size=10),
            fg_color=COLOR_ERROR,
            hover_color="#C0392B",
            text_color="white",
            height=22,
            width=55,
            command=self._on_stop_cmd,
        )
        self._btn_stop.pack(side="left")

        btn_exit = ctk.CTkButton(
            bot_row,
            text="✕ 退出",
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color="#FADBD8",
            text_color=COLOR_ERROR,
            height=22,
            width=55,
            command=self._on_exit_cmd,
        )
        btn_exit.pack(side="right")

    # ── 拖拽逻辑 ──

    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag_motion(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    # ── 公开方法 ──

    def update_monitoring_status(self, active: bool):
        """更新监控运行状态显示。"""
        self._monitoring = active
        if active:
            self._status_dot.configure(text_color=COLOR_SUCCESS)
            self._status_label.configure(text="运行中", text_color=COLOR_SUCCESS)
            self._btn_stop.configure(state="normal")
        else:
            self._status_dot.configure(text_color=COLOR_DISABLED)
            self._status_label.configure(text="已停止", text_color=COLOR_TEXT)
            self._match_label.configure(text="")
            self._btn_stop.configure(state="disabled")

    def update_match_count(self, count: int):
        """更新匹配计数显示。"""
        self._match_count = count
        if self._monitoring and count > 0:
            self._match_label.configure(text=f"匹配 {count} 次")
        elif self._monitoring:
            self._match_label.configure(text="")

    # ── 回调 ──

    def _on_restore_cmd(self):
        if self._on_restore:
            self._on_restore()

    def _on_stop_cmd(self):
        if self._on_stop:
            self._on_stop()

    def _on_exit_cmd(self):
        if self._on_exit:
            self._on_exit()
