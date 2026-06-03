"""运行日志面板。

显示带时间戳的监控运行日志，按级别使用不同颜色区分，
到达上限后自动淘汰最旧条目，新条目自动滚动到底部。
"""

from __future__ import annotations

import customtkinter as ctk

from config import (
    COLOR_TEXT, COLOR_TEXT_SECONDARY,
    COLOR_SUCCESS, COLOR_ACCENT, COLOR_WARNING, COLOR_ERROR,
    COLOR_BG,
    MAX_LOG_ENTRIES,
)

# 日志级别 → 文字颜色
_LOG_COLORS = {
    "info": COLOR_TEXT_SECONDARY,
    "match": COLOR_SUCCESS,
    "click": COLOR_ACCENT,
    "error": COLOR_ERROR,
}


class LogPanel(ctk.CTkFrame):
    """运行日志显示面板。

    用法:
        panel = LogPanel(parent)
        panel.add_entry("12:00:00", "监控已启动", "info")
        panel.clear()
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._max_entries = MAX_LOG_ENTRIES
        self._entries: list[ctk.CTkFrame] = []

        # ── 标题栏 ──
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            header,
            text="📋 运行日志",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="显示每次扫描结果",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left", padx=(8, 0))

        btn_clear = ctk.CTkButton(
            header,
            text="清空",
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=COLOR_BG,
            text_color=COLOR_TEXT_SECONDARY,
            height=24,
            width=50,
            command=self.clear,
        )
        btn_clear.pack(side="right")

        # ── 日志滚动区域 ──
        self._scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLOR_BG,
            corner_radius=4,
            height=130,
        )
        self._scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # 空状态
        self._empty_label = ctk.CTkLabel(
            self._scroll_frame,
            text="暂无日志，点击「开始监控」后自动显示",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._empty_label.pack(expand=True, pady=20)

    # ── 公开方法 ──────────────────────────────────

    def add_entry(self, time_str: str, message: str, level: str = "info"):
        """添加一条日志条目。

        Args:
            time_str: 格式化的时间字符串（如 "12:00:00"）
            message: 日志内容
            level: 级别 — info / match / click / error
        """
        # 移除空状态提示（仅首次）
        if self._empty_label is not None:
            self._empty_label.destroy()
            self._empty_label = None

        # 创建日志行
        entry = ctk.CTkFrame(
            self._scroll_frame,
            fg_color="transparent",
        )
        entry.pack(fill="x", padx=5, pady=1)

        color = _LOG_COLORS.get(level, COLOR_TEXT_SECONDARY)

        # 时间戳
        ctk.CTkLabel(
            entry,
            text=f"[{time_str}]",
            font=ctk.CTkFont(size=10, family="Consolas"),
            text_color=COLOR_TEXT_SECONDARY,
            width=72,
            anchor="w",
        ).pack(side="left")

        # 消息内容
        ctk.CTkLabel(
            entry,
            text=message,
            font=ctk.CTkFont(size=10),
            text_color=color,
            anchor="w",
        ).pack(side="left", padx=(5, 0))

        self._entries.append(entry)

        # 超出上限，淘汰最旧
        while len(self._entries) > self._max_entries:
            old = self._entries.pop(0)
            old.destroy()

        # 滚动到底部
        self._scroll_to_bottom()

    def clear(self):
        """清空所有日志。"""
        for entry in self._entries:
            entry.destroy()
        self._entries.clear()

        # 恢复空状态
        if self._empty_label is None:
            self._empty_label = ctk.CTkLabel(
                self._scroll_frame,
                text="暂无日志",
                font=ctk.CTkFont(size=10),
                text_color=COLOR_TEXT_SECONDARY,
            )
            self._empty_label.pack(expand=True, pady=20)

    # ── 内部 ──────────────────────────────────────

    def _scroll_to_bottom(self):
        """滚动到日志列表底部。"""
        try:
            self._scroll_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass
