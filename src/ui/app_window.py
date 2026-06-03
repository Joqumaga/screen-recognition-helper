"""主应用窗口。

包含区域管理（添加、删除、启用/禁用区域）、
布局分左右两栏：左侧区域列表，右侧后续功能占位。
"""

import json
import queue
import threading
import tkinter.messagebox as mb
import uuid
from pathlib import Path

import customtkinter as ctk

from config import (
    WINDOW_TITLE, WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    COLOR_PRIMARY, COLOR_BG, COLOR_TEXT, COLOR_ACCENT,
    COLOR_TEXT_SECONDARY, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    COLOR_BORDER, COLOR_DISABLED, CONFIG_FILE, TESSERACT_CMD,
    CLICK_AREA_RADIUS, CLICK_DELAY_MS, SCAN_INTERVAL_MS,
)
from ui.region_selector import RegionSelector
from ui.tooltip import Tooltip
from core.screen_capture import ScreenCapture
from core.ocr_engine import OCREngine
from core.matcher import TargetMatcher, MatchResult
from core.clicker import MouseClicker
from core.monitor import MonitorLoop
from ui.log_panel import LogPanel
from ui.floating_window import FloatingIndicator
from utils.image_processor import ImageProcessor


class RegionItem(ctk.CTkFrame):
    """单个监控区域的 UI 卡片。

    显示区域名称、坐标信息，提供启用/禁用开关、专属目标编辑和删除按钮。
    """

    def __init__(
        self,
        master,
        region_data: dict,
        on_delete=None,
        on_toggle=None,
        on_targets_changed=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._region_data = region_data          # 持有区域 dict 引用
        self._region_id = region_data["id"]
        self._on_delete = on_delete
        self._on_toggle = on_toggle
        self._on_targets_changed = on_targets_changed
        self._targets_expanded = False

        # ── 第一行：开关 + 信息 + 展开按钮 + 删除 ──
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", expand=True)

        # 启用/禁用开关
        self._switch_var = ctk.BooleanVar(value=region_data.get("enabled", True))
        switch = ctk.CTkSwitch(
            top_row,
            text="",
            width=40,
            variable=self._switch_var,
            onvalue=True,
            offvalue=False,
            command=self._on_toggle_switch,
        )
        switch.pack(side="left", padx=(10, 5))
        Tooltip(switch, "启用/禁用此监控区域\n禁用后不会对该区域执行识别")

        # 信息区
        info_frame = ctk.CTkFrame(top_row, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=5)

        ctk.CTkLabel(
            info_frame,
            text=region_data.get("name", "未命名"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(anchor="w")

        coords = region_data["coords"]
        ctk.CTkLabel(
            info_frame,
            text=f"📍 ({coords['left']}, {coords['top']})  "
                 f"{coords['width']} × {coords['height']}",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(anchor="w")

        # 专属目标展开/折叠按钮
        self._expand_btn = ctk.CTkButton(
            top_row,
            text=self._target_summary_text(),
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=COLOR_BG,
            text_color=COLOR_ACCENT,
            height=22,
            command=self._toggle_target_panel,
        )
        self._expand_btn.pack(side="right", padx=(5, 0))

        # 删除按钮（纯文本，避免打包 exe 后特殊字符渲染失效）
        btn_delete = ctk.CTkButton(
            top_row,
            text="删除",
            width=60,
            height=28,
            fg_color=COLOR_ERROR,
            hover_color="#C0392B",
            text_color="white",
            font=ctk.CTkFont(size=11),
            command=self._on_delete_click,
        )
        btn_delete.pack(side="right", padx=(0, 10))
        Tooltip(btn_delete, "删除此监控区域\n删除后不可恢复")

        # ── 第二行容器：可折叠的专属目标编辑面板（默认隐藏） ──
        self._target_panel_frame = ctk.CTkFrame(self, fg_color="transparent")

    # ── 第一行回调 ──

    def _on_toggle_switch(self):
        """切换启用/禁用状态，更新卡片边框颜色。"""
        enabled = self._switch_var.get()
        if self._on_toggle:
            self._on_toggle(self._region_id, enabled)
        self.master.configure(
            border_color=COLOR_SUCCESS if enabled else COLOR_DISABLED,
        )

    def _on_delete_click(self):
        """删除确认后删除区域。"""
        name = self._region_data.get("name", "未命名")
        confirm = mb.askyesno(
            "确认删除",
            f"确定要删除「{name}」吗？\n\n删除后不可恢复。",
            icon="warning",
        )
        if confirm and self._on_delete:
            self._on_delete(self._region_id)

    # ── 专属目标折叠面板 ──

    def _target_summary_text(self) -> str:
        """生成展开按钮上的摘要文字。"""
        count = len(self._region_data.get("targets", []))
        if count == 0:
            return "[默认]"
        return f"[{count}个专属]"

    def _toggle_target_panel(self):
        """展开/折叠专属目标编辑面板。"""
        if self._targets_expanded:
            self._target_panel_frame.pack_forget()
            self._targets_expanded = False
        else:
            if not self._target_panel_frame.winfo_children():
                self._build_target_panel()
            self._target_panel_frame.pack(fill="x", padx=5, pady=(4, 6))
            self._targets_expanded = True

    def _build_target_panel(self):
        """构建专属目标编辑面板（输入框 + 添加按钮 + 标签列表）。"""
        inner = ctk.CTkFrame(
            self._target_panel_frame, fg_color=COLOR_BG, corner_radius=6,
        )
        inner.pack(fill="x")

        input_row = ctk.CTkFrame(inner, fg_color="transparent")
        input_row.pack(fill="x", padx=8, pady=(6, 4))

        self._region_target_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="输入此区域的专属目标...",
            font=ctk.CTkFont(size=11),
            height=26,
        )
        self._region_target_entry.pack(side="left", fill="x", expand=True)
        self._region_target_entry.bind(
            "<Return>", lambda e: self._add_region_target(),
        )

        btn = ctk.CTkButton(
            input_row,
            text="添加",
            font=ctk.CTkFont(size=10),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_ACCENT,
            text_color="white",
            height=26,
            width=45,
            command=self._add_region_target,
        )
        btn.pack(side="left", padx=(4, 0))

        self._region_target_tags = ctk.CTkFrame(inner, fg_color="transparent")
        self._region_target_tags.pack(fill="x", padx=8, pady=(0, 6))
        self._refresh_region_target_tags()

    def _add_region_target(self):
        """向此区域添加一个专属目标文字。"""
        text = self._region_target_entry.get().strip()
        if not text:
            return
        targets = self._region_data.setdefault("targets", [])
        if text in targets:
            return
        targets.append(text)
        self._region_target_entry.delete(0, "end")
        self._refresh_region_target_tags()
        self._expand_btn.configure(text=self._target_summary_text())
        if self._on_targets_changed:
            self._on_targets_changed(self._region_id)

    def _remove_region_target(self, text: str):
        """从此区域的专属目标列表中移除一个文字。"""
        targets = self._region_data.get("targets", [])
        if text in targets:
            targets.remove(text)
        self._refresh_region_target_tags()
        self._expand_btn.configure(text=self._target_summary_text())
        if self._on_targets_changed:
            self._on_targets_changed(self._region_id)

    def _refresh_region_target_tags(self):
        """刷新专属目标标签列表。"""
        for w in self._region_target_tags.winfo_children():
            w.destroy()
        targets = self._region_data.get("targets", [])
        if not targets:
            ctk.CTkLabel(
                self._region_target_tags,
                text="无专属目标（将使用右侧默认目标列表）",
                font=ctk.CTkFont(size=9),
                text_color=COLOR_TEXT_SECONDARY,
            ).pack(anchor="w")
            return
        for t in targets:
            tag = ctk.CTkFrame(
                self._region_target_tags,
                fg_color=COLOR_ACCENT,
                corner_radius=10,
                height=22,
            )
            tag.pack(side="left", padx=2, pady=2)
            ctk.CTkLabel(
                tag,
                text=f" {t} ",
                font=ctk.CTkFont(size=10),
                text_color="white",
            ).pack(side="left", padx=(6, 2))
            btn = ctk.CTkButton(
                tag,
                text="×",
                width=16,
                height=16,
                fg_color="transparent",
                hover_color=COLOR_ERROR,
                text_color="white",
                font=ctk.CTkFont(size=10),
                command=lambda txt=t: self._remove_region_target(txt),
            )
            btn.pack(side="left", padx=(0, 4))


class AppWindow(ctk.CTk):
    """游戏辅助主窗口。

    包含：
    - 顶部标题栏
    - 左侧区域管理面板（区域列表 + 添加按钮）
    - 右侧功能面板（占位，后续阶段实现）
    - 底部状态栏
    """

    def __init__(self):
        super().__init__()

        # ── 窗口设置 ──
        self.title(WINDOW_TITLE)
        self.geometry(f"{WINDOW_DEFAULT_WIDTH}x{WINDOW_DEFAULT_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._center_window()

        # ── 数据 ──
        self._regions: list[dict] = []
        self._region_items: dict[str, RegionItem] = {}
        self._region_item_frames: dict[str, ctk.CTkFrame] = {}
        self._targets: list[str] = []         # 用户输入的目标文字列表
        self._clicker = MouseClicker(
            delay_ms=CLICK_DELAY_MS,
            area_radius=CLICK_AREA_RADIUS,
        )
        self._log_queue: queue.Queue = queue.Queue()
        self._monitor: MonitorLoop | None = None
        self._is_monitoring = False
        self._log_poll_id: str | None = None
        self._selector = RegionSelector()
        self._screen_cap = ScreenCapture()
        self._ocr_engine = OCREngine()

        # ── 置顶 & 浮动窗 ──
        self._always_on_top_var = ctk.BooleanVar(value=False)
        self._floating_window: FloatingIndicator | None = None
        self._match_total = 0        # 累计匹配次数
        self._is_floating = False    # 当前是否处于浮动窗模式

        # ── 构建界面 ──
        self._build_ui()

        # ── 注册关闭事件 ──
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # ── 绑定最小化/恢复事件（用于浮动窗） ──
        self.bind("<Unmap>", self._on_window_unmap)
        self.bind("<Map>",     self._on_window_map)

        # ── 启动检查 ──
        self._check_environment()

        # ── 加载已保存的区域 ──
        self._load_regions()

    # ────────────────────── 窗口与布局 ──────────────────────

    def _center_window(self):
        """将窗口显示在屏幕中央。"""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - WINDOW_DEFAULT_WIDTH) // 2
        y = (sh - WINDOW_DEFAULT_HEIGHT) // 2
        self.geometry(f"+{x}+{y}")

    def _check_environment(self):
        """启动时检查运行环境是否完整（Tesseract 等关键依赖）。"""
        import pytesseract
        try:
            pytesseract.get_tesseract_version()  # 验证版本
            self._tesseract_ok = True
        except Exception:
            self._tesseract_ok = False
            mb.showwarning(
                "Tesseract 未检测到",
                "未找到 Tesseract OCR 引擎，OCR 识别功能将不可用。\n\n"
                "请确认 Tesseract 已安装在：\n"
                f"{TESSERACT_CMD}\n\n"
                "安装后请重启本软件。",
            )

    def _build_ui(self):
        """构建完整界面（标题栏 → 控制栏 → 主体 → 日志 → 状态栏）。"""
        # ── 标题栏 ──
        title_bar = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, corner_radius=0)
        title_bar.pack(fill="x")

        ctk.CTkLabel(
            title_bar,
            text=WINDOW_TITLE,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).pack(pady=(10, 0))

        ctk.CTkLabel(
            title_bar,
            text="框选屏幕区域 → 自动识别文字 → 智能点击",
            font=ctk.CTkFont(size=11),
            text_color="white",
        ).pack(pady=(2, 10))

        # ── 控制栏（开始/停止 + 扫描间隔） ──
        self._build_control_bar()

        # ── 分隔线 ──
        ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, height=1).pack(fill="x", padx=15, pady=0)

        # ── 主体（左右分栏） ──
        main_frame = ctk.CTkFrame(self, fg_color=COLOR_BG)
        main_frame.pack(fill="both", expand=True, padx=15, pady=(6, 0))

        main_frame.grid_columnconfigure(0, weight=2)  # 左侧：区域管理
        main_frame.grid_columnconfigure(1, weight=3)  # 右侧：OCR+目标+点击
        main_frame.grid_rowconfigure(0, weight=1)

        # 左侧面板
        left_panel = ctk.CTkFrame(main_frame, fg_color="white", corner_radius=10)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self._build_region_panel(left_panel)

        # 右侧面板
        right_panel = ctk.CTkFrame(main_frame, fg_color="white", corner_radius=10)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._build_right_panel(right_panel)

        # ── 日志面板 ──
        log_frame = ctk.CTkFrame(
            self,
            fg_color="white",
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        log_frame.pack(fill="x", padx=15, pady=(8, 0))
        self._log_panel = LogPanel(log_frame, fg_color="transparent")
        self._log_panel.pack(fill="both", expand=True)

        # ── 状态栏 ──
        self._status_label = ctk.CTkLabel(
            self,
            text="状态：就绪  |  区域：0 个",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._status_label.pack(side="bottom", fill="x", padx=15, pady=(0, 8))

    # ────────────────────── 左侧：区域管理 ──────────────────────

    def _build_region_panel(self, parent):
        """左侧面板：区域管理。"""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            header,
            text="📋 监控区域",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="拖拽框选要监控的屏幕区域",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left", padx=(10, 0))

        # 添加区域按钮
        btn_add = ctk.CTkButton(
            parent,
            text="+ 添加区域",
            font=ctk.CTkFont(size=13),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_ACCENT,
            text_color="white",
            height=36,
            command=self._on_add_region,
        )
        btn_add.pack(fill="x", padx=15, pady=(5, 10))
        Tooltip(btn_add, "拖拽框选屏幕上的监控区域\n按住鼠标左键拖动 → 松开确认\n按 ESC 取消")

        # 区域列表（可滚动）
        self._region_scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
        )
        self._region_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ────────────────────── 右侧面板（上半：OCR / 下半：目标+点击） ──────────────────────

    def _build_right_panel(self, parent):
        """右侧面板：上半 OCR 预览 + 下半目标设置与点击配置。"""
        # 使用 grid 分成上下两半
        parent.grid_rowconfigure(0, weight=3)   # 上半：OCR（更多空间）
        parent.grid_rowconfigure(1, weight=2)   # 下半：目标+点击
        parent.grid_columnconfigure(0, weight=1)

        # ── 上半：OCR 识别预览 ──
        ocr_frame = ctk.CTkFrame(parent, fg_color="transparent")
        ocr_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        self._build_ocr_section(ocr_frame)

        # ── 下半：目标 + 点击配置 ──
        bottom_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        bottom_frame.grid(row=1, column=0, sticky="nsew", pady=(3, 0))
        self._build_target_section(bottom_frame)

    # ────────────────────── 上半：OCR 部分 ──────────────────────

    def _build_ocr_section(self, parent):
        """识别预览区域：区域选择 + 测试按钮 + 结果列表。"""
        # 标题
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(
            header,
            text="🔍 识别预览",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="选择区域 → 测试识别效果",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left", padx=(8, 0))

        # 控制行：下拉 + 按钮
        control_frame = ctk.CTkFrame(parent, fg_color="transparent")
        control_frame.pack(fill="x", padx=10, pady=(0, 6))

        self._ocr_region_var = ctk.StringVar(value="")
        self._ocr_region_menu = ctk.CTkOptionMenu(
            control_frame,
            variable=self._ocr_region_var,
            values=["请先添加区域"],
            width=160,
            fg_color=COLOR_BG,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_ACCENT,
            text_color=COLOR_TEXT,
            dropdown_fg_color="white",
            dropdown_text_color=COLOR_TEXT,
            command=self._on_ocr_region_selected,  # 选中区域自动触发识别
        )
        self._ocr_region_menu.pack(side="left")
        self._auto_ocr_armed = False  # 初始加载时不触发，用户首次手动选择后启用

        btn_test = ctk.CTkButton(
            control_frame,
            text="测试识别",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_ACCENT,
            hover_color="#3A6F9E",
            text_color="white",
            height=30,
            command=self._on_test_ocr,
        )
        btn_test.pack(side="left", padx=(6, 0))
        Tooltip(btn_test, "对当前选中的区域\n执行一次截图 + OCR 识别测试")

        btn_clear = ctk.CTkButton(
            control_frame,
            text="清空",
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=COLOR_BG,
            text_color=COLOR_TEXT_SECONDARY,
            height=26,
            width=40,
            command=self._clear_ocr_results,
        )
        btn_clear.pack(side="left", padx=(4, 0))
        Tooltip(btn_clear, "清空识别结果列表")

        # ── 识别结果列表（可滚动） ──
        self._ocr_result_frame = ctk.CTkScrollableFrame(
            parent,
            fg_color=COLOR_BG,
            corner_radius=6,
        )
        self._ocr_result_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        # 初始空状态
        self._show_ocr_empty_hint()

    def _show_ocr_empty_hint(self):
        """显示空状态提示。"""
        self._ocr_empty_label = ctk.CTkLabel(
            self._ocr_result_frame,
            text="✨\n\n选择左侧已添加的区域\n点击「测试识别」查看效果",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._ocr_empty_label.pack(expand=True, pady=30)

    def _refresh_region_menu(self):
        """刷新右侧区域选择下拉框。"""
        enabled_regions = [r for r in self._regions if r.get("enabled", True)]
        if not enabled_regions:
            self._ocr_region_menu.configure(values=["暂无可用区域"])
            self._ocr_region_var.set("暂无可用区域")
            return

        names = [f"{r['name']}  ({r['coords']['width']}×{r['coords']['height']})"
                 for r in enabled_regions]
        self._ocr_region_menu.configure(values=names)
        self._auto_ocr_locked = True  # 锁住避免 set() 触发的 command 回调误触发自动 OCR
        self._ocr_region_var.set(names[0])
        self.after(300, self._unlock_auto_ocr)  # 延迟解锁，允许后续手动选择触发

    def _unlock_auto_ocr(self):
        """解锁自动 OCR 触发（_refresh_region_menu 的延迟回调）。"""
        self._auto_ocr_locked = False

    # ────────────────────── OCR 测试 ──────────────────────

    def _on_ocr_region_selected(self, _choice: str):
        """下拉菜单选中区域时自动触发 OCR 识别。"""
        if getattr(self, '_auto_ocr_locked', False):
            return  # 程序化设置值时跳过
        self.after(150, self._on_test_ocr)  # 延迟等 UI 更新

    def _on_test_ocr(self):
        """在后台线程中执行截图+预处理+OCR 识别。"""
        selected_name = self._ocr_region_var.get()
        if not selected_name or "暂无" in selected_name or "请先" in selected_name:
            self._update_status_text("请先添加并选择一个区域")
            self._log_panel.add_entry(
                __import__('time').strftime("%H:%M:%S"),
                "⚠️ 测试识别失败：未选择有效区域",
                "warning",
            )
            return

        region_name = selected_name.split("  (")[0]
        region = None
        for r in self._regions:
            if r["name"] == region_name and r.get("enabled", True):
                region = r
                break

        if not region:
            self._update_status_text("所选区域未启用或不存在")
            self._log_panel.add_entry(
                __import__('time').strftime("%H:%M:%S"),
                f"⚠️ 测试识别失败：区域「{region_name}」未启用或不存在",
                "warning",
            )
            return

        if not getattr(self, '_tesseract_ok', True):
            mb.showerror("OCR 不可用", "Tesseract OCR 引擎未安装或路径不正确，无法执行识别。")
            return

        self._update_status_text(f"正在识别 {region['name']}...")
        self._log_panel.add_entry(
            __import__('time').strftime("%H:%M:%S"),
            f"🔍 开始测试识别 [{region['name']}]...",
            "info",
        )
        threading.Thread(
            target=self._run_ocr_test,
            args=(region,),
            daemon=True,
        ).start()

    def _run_ocr_test(self, region: dict):
        """在后台线程中执行识别。"""
        try:
            img_bgra = self._screen_cap.capture(region["coords"])
            processed = ImageProcessor.preprocess(img_bgra)
            results = self._ocr_engine.recognize(processed)
            # 收集所有需要匹配的目标：全局目标 + 区域专属目标
            test_targets = list(self._targets)
            region_targets = region.get("targets", [])
            for t in region_targets:
                if t not in test_targets:
                    test_targets.append(t)
            matches = TargetMatcher.match(results, test_targets, mode="fuzzy") if test_targets else []
            self.after(0, self._display_ocr_results, results, matches, region["name"])
            # 同时写入日志面板，让用户能看到
            self.after(0, self._log_ocr_test_result, results, matches, region["name"])
        except Exception as e:
            err_msg = str(e)
            err_detail = ""
            import traceback
            err_detail = traceback.format_exc()
            # 友好化常见错误
            if "tesseract" in err_msg.lower() or "pytesseract" in err_msg.lower():
                friendly = "OCR 识别失败：Tesseract 引擎未正确配置，请检查安装路径"
            elif "mss" in err_msg.lower() or "screen" in err_msg.lower():
                friendly = "截图失败：无法访问屏幕，请检查权限设置"
            else:
                friendly = f"识别过程出错：{err_msg}"
            self.after(0, self._show_ocr_error, friendly, err_detail)

    def _log_ocr_test_result(self, results: list, matches: list, region_name: str):
        """将 OCR 测试结果写入日志面板。"""
        import time as _time
        count = len(results)
        match_count = len(matches)
        if count == 0:
            self._log_panel.add_entry(
                _time.strftime("%H:%M:%S"),
                f"🔍 [{region_name}] 测试识别完成，未识别到文字（确认区域内有英文字符）",
                "info",
            )
        else:
            self._log_panel.add_entry(
                _time.strftime("%H:%M:%S"),
                f"🔍 [{region_name}] 测试识别完成：{count} 项文字"
                + (f"，匹配 {match_count} 项" if matches else ""),
                "info",
            )
            for r in results[:10]:  # 最多展示 10 项
                self._log_panel.add_entry(
                    _time.strftime("%H:%M:%S"),
                    f"  📝 [{r.confidence}%] {r.text}",
                    "info",
                )

    def _show_ocr_error(self, friendly: str, detail: str = ""):
        """显示 OCR 测试错误：弹窗 + 状态栏 + 日志。"""
        import time as _time
        self._update_status_text(friendly)
        self._log_panel.add_entry(
            _time.strftime("%H:%M:%S"),
            f"❌ {friendly}",
            "error",
        )
        mb.showerror("OCR 识别失败", friendly)

    def _display_ocr_results(self, results: list, matches: list, region_name: str):
        """展示识别结果并高亮匹配到的目标。"""
        self._clear_ocr_results()

        # 构建匹配查找表：OCR text → MatchResult
        matched_texts = {m.ocr_result.text: m for m in matches}

        count = len(results)
        match_count = len(matches)
        header_text = (
            f"📄 {region_name} 识别结果（{count} 项）"
            + (f"  🎯 匹配 {match_count} 项" if matches else "")
        )
        ctk.CTkLabel(
            self._ocr_result_frame,
            text=header_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 4))

        if not results:
            ctk.CTkLabel(
                self._ocr_result_frame,
                text="未识别到文字\n\n提示：确认该区域包含英文字符",
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_SECONDARY,
            ).pack(expand=True, pady=20)
            self._update_status_text(f"{region_name}: 未识别到文字")
            return

        # 逐条显示
        for r in results:
            is_match = r.text in matched_texts
            bg_color = "#E8F8E8" if is_match else "white"  # 匹配项用浅绿色背景
            item = ctk.CTkFrame(
                self._ocr_result_frame,
                fg_color=bg_color,
                corner_radius=6,
                border_width=1,
                border_color=COLOR_SUCCESS if is_match else COLOR_BORDER,
            )
            item.pack(fill="x", padx=10, pady=2)

            line1 = ctk.CTkFrame(item, fg_color="transparent")
            line1.pack(fill="x", padx=10, pady=(5, 0))

            # 文字内容
            ctk.CTkLabel(
                line1,
                text=f"📝 {r.text}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COLOR_TEXT,
            ).pack(side="left")

            # 匹配徽标 / 可信度
            if is_match:
                ctk.CTkLabel(
                    line1,
                    text=f"🎯 已匹配  {r.confidence}%",
                    font=ctk.CTkFont(size=10),
                    text_color=COLOR_SUCCESS,
                ).pack(side="right", padx=(0, 5))
            else:
                conf_color = COLOR_SUCCESS if r.confidence >= 80 else (
                    COLOR_WARNING if r.confidence >= 60 else COLOR_ERROR
                )
                ctk.CTkLabel(
                    line1,
                    text=f"{r.confidence}%",
                    font=ctk.CTkFont(size=10),
                    text_color=conf_color,
                ).pack(side="right")

            # 坐标
            ctk.CTkLabel(
                item,
                text=f"({r.bbox['left']}, {r.bbox['top']})  {r.bbox['width']}×{r.bbox['height']}",
                font=ctk.CTkFont(size=9),
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 5))

        status = f"{region_name}: 识别到 {count} 项"
        if matches:
            status += f"，匹配 {match_count} 项 🎯"
        else:
            status += f"（未匹配目标）"
        self._update_status_text(status)

    def _clear_ocr_results(self):
        """清空识别结果，显示空状态提示。"""
        for widget in self._ocr_result_frame.winfo_children():
            widget.destroy()
        self._show_ocr_empty_hint()

    def _update_status_text(self, text: str):
        """更新底部状态栏文字。"""
        self._status_label.configure(text=f"状态：{text}")

    # ────────────────────── 下半：目标 + 点击配置 ──────────────────────

    def _build_target_section(self, parent):
        """底部面板：目标文字输入 + 点击参数配置。"""
        # ── 🎯 默认目标 ──
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            header,
            text="🎯 默认目标",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="未设专属目标的区域使用此列表",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left", padx=(8, 0))

        # 输入行：文本框 + 添加按钮
        input_frame = ctk.CTkFrame(parent, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=(0, 6))

        self._target_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="输入目标文字后点击添加...",
            font=ctk.CTkFont(size=12),
            height=32,
        )
        self._target_entry.pack(side="left", fill="x", expand=True)
        Tooltip(self._target_entry, "输入要自动点击的文字\n支持英文字母、数字、符号\n按回车键快速添加")
        # 绑定回车键
        self._target_entry.bind("<Return>", lambda e: self._on_add_target())

        btn_add_target = ctk.CTkButton(
            input_frame,
            text="添加",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_ACCENT,
            text_color="white",
            height=32,
            width=60,
            command=self._on_add_target,
        )
        btn_add_target.pack(side="left", padx=(6, 0))
        Tooltip(btn_add_target, "将输入的文字添加到目标列表\n监控时会自动匹配这些文字并点击")

        # 目标列表（标签流式布局）
        self._target_list_frame = ctk.CTkFrame(
            parent,
            fg_color=COLOR_BG,
            corner_radius=6,
            height=30,
        )
        self._target_list_frame.pack(fill="x", padx=10, pady=(0, 8))
        self._render_target_list()

        # ── 分隔线 ──
        ctk.CTkFrame(parent, fg_color=COLOR_BORDER, height=1).pack(
            fill="x", padx=15, pady=4,
        )

        # ── ⚙️ 点击设置 ──
        cfg_header = ctk.CTkFrame(parent, fg_color="transparent")
        cfg_header.pack(fill="x", padx=10, pady=(4, 4))
        ctk.CTkLabel(
            cfg_header,
            text="⚙️ 点击设置",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        # 点击范围滑块
        radius_frame = ctk.CTkFrame(parent, fg_color="transparent")
        radius_frame.pack(fill="x", padx=15, pady=(4, 2))
        ctk.CTkLabel(
            radius_frame,
            text="点击范围：",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT,
            width=70,
            anchor="w",
        ).pack(side="left")

        self._radius_var = ctk.IntVar(value=CLICK_AREA_RADIUS)
        radius_slider = ctk.CTkSlider(
            radius_frame,
            from_=0,
            to=20,
            number_of_steps=20,
            variable=self._radius_var,
            command=self._on_radius_change,
            width=120,
        )
        radius_slider.pack(side="left", padx=(5, 8))
        Tooltip(radius_slider, "点击位置的随机偏移范围\n0px = 精确点击文字中心\n值越大，点击位置越分散")

        self._radius_label = ctk.CTkLabel(
            radius_frame,
            text=f"{CLICK_AREA_RADIUS} px",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_ACCENT,
            width=40,
        )
        self._radius_label.pack(side="left")

        ctk.CTkLabel(
            radius_frame,
            text="0=精确点击",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left", padx=(5, 0))

        # 点击延时滑块
        delay_frame = ctk.CTkFrame(parent, fg_color="transparent")
        delay_frame.pack(fill="x", padx=15, pady=(2, 10))
        ctk.CTkLabel(
            delay_frame,
            text="点击延时：",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT,
            width=70,
            anchor="w",
        ).pack(side="left")

        self._delay_var = ctk.IntVar(value=CLICK_DELAY_MS)
        delay_slider = ctk.CTkSlider(
            delay_frame,
            from_=0,
            to=500,
            number_of_steps=50,
            variable=self._delay_var,
            command=self._on_delay_change,
            width=120,
        )
        delay_slider.pack(side="left", padx=(5, 8))
        Tooltip(delay_slider, "鼠标移动到点击位置后的延迟\n更长的延迟能应对网络变化\n建议：50-200ms")

        self._delay_label = ctk.CTkLabel(
            delay_frame,
            text=f"{CLICK_DELAY_MS} ms",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_ACCENT,
            width=50,
        )
        self._delay_label.pack(side="left")

    # ────────────────────── 目标管理 ──────────────────────

    def _on_add_target(self):
        """从输入框添加一个目标文字。"""
        text = self._target_entry.get().strip()
        if not text:
            return
        if text in self._targets:
            self._update_status_text(f"目标「{text}」已存在")
            return

        self._targets.append(text)
        self._target_entry.delete(0, "end")
        self._render_target_list()
        self._update_status()
        self._update_status_text(f"已添加目标「{text}」")

    def _remove_target(self, target_text: str):
        """删除一个目标文字。"""
        if target_text in self._targets:
            self._targets.remove(target_text)
            self._render_target_list()
            self._update_status()
            self._update_status_text(f"已移除目标「{target_text}」")

    def _render_target_list(self):
        """刷新目标文字标签列表。"""
        for widget in self._target_list_frame.winfo_children():
            widget.destroy()

        if not self._targets:
            ctk.CTkLabel(
                self._target_list_frame,
                text="尚未添加目标文字，添加后将在此显示",
                font=ctk.CTkFont(size=10),
                text_color=COLOR_TEXT_SECONDARY,
            ).pack(pady=6)
            return

        # 水平流式排列目标标签
        targets_frame = ctk.CTkFrame(self._target_list_frame, fg_color="transparent")
        targets_frame.pack(fill="x", padx=4, pady=4)

        row_frame = targets_frame
        row_width = 0

        for target in self._targets:
            # 每个目标 = 一个标签卡片
            tag = ctk.CTkFrame(
                row_frame,
                fg_color=COLOR_PRIMARY,
                corner_radius=12,
                height=28,
            )
            tag.pack(side="left", padx=2, pady=2)

            ctk.CTkLabel(
                tag,
                text=f"  {target}  ",
                font=ctk.CTkFont(size=11),
                text_color="white",
            ).pack(side="left", padx=(8, 2))

            btn_del = ctk.CTkButton(
                tag,
                text="×",
                width=20,
                height=20,
                fg_color="transparent",
                hover_color=COLOR_ACCENT,
                text_color="white",
                font=ctk.CTkFont(size=10),
                command=lambda t=target: self._remove_target(t),
            )
            btn_del.pack(side="left", padx=(0, 6))

    # ────────────────────── 点击参数回调 ──────────────────────

    def _on_radius_change(self, value):
        """点击范围滑块回调。"""
        radius = int(value)
        self._radius_label.configure(text=f"{radius} px")
        self._clicker.area_radius = radius

    def _on_delay_change(self, value):
        """点击延时滑块回调。"""
        delay = int(value)
        self._delay_label.configure(text=f"{delay} ms")
        self._clicker.delay_ms = delay

    # ────────────────────── 监控控制 ──────────────────────

    def _build_control_bar(self):
        """控制栏：开始/停止按钮 + 扫描间隔滑块。"""
        bar = ctk.CTkFrame(
            self,
            fg_color="white",
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        bar.pack(fill="x", padx=15, pady=(6, 4))

        # ── 开始/停止按钮 ──
        self._btn_start = ctk.CTkButton(
            bar,
            text="▶  开始监控",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_SUCCESS,
            hover_color="#219A52",
            text_color="white",
            height=34,
            width=130,
            command=self._toggle_monitoring,
        )
        self._btn_start.pack(side="left", padx=(12, 15))
        self._start_btn_tooltip = Tooltip(
            self._btn_start,
            "开始循环监控所有启用的区域\n自动截图 → OCR → 匹配 → 点击\n需要先添加区域和目标文字",
        )

        # ── 分隔线 ──
        ctk.CTkFrame(bar, fg_color=COLOR_BORDER, width=1, height=24).pack(
            side="left", padx=(0, 12),
        )

        # ── 扫描间隔 ──
        ctk.CTkLabel(
            bar,
            text="扫描间隔",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        self._scan_interval_var = ctk.IntVar(value=SCAN_INTERVAL_MS)
        scan_slider = ctk.CTkSlider(
            bar,
            from_=50,
            to=2000,
            number_of_steps=39,
            variable=self._scan_interval_var,
            command=self._on_scan_interval_change,
            width=120,
        )
        scan_slider.pack(side="left", padx=(8, 6))
        Tooltip(scan_slider, "每次扫描之间的间隔时间\n值越小响应越快，但 CPU 占用越高\n建议：200-500ms")

        self._scan_interval_label = ctk.CTkLabel(
            bar,
            text=f"{SCAN_INTERVAL_MS} ms",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_ACCENT,
            width=50,
        )
        self._scan_interval_label.pack(side="left")

        # ── 监控状态指示 ──
        self._monitor_status_label = ctk.CTkLabel(
            bar,
            text="⏹  已停止",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SECONDARY,
        )
        self._monitor_status_label.pack(side="right", padx=(0, 15))
        Tooltip(self._monitor_status_label, "当前监控运行状态\n绿色 = 运行中，灰色 = 已停止")

        # ── 置顶开关 ──
        self._always_on_top_switch = ctk.CTkSwitch(
            bar,
            text="🔝 置顶",
            font=ctk.CTkFont(size=10),
            variable=self._always_on_top_var,
            onvalue=True,
            offvalue=False,
            command=self._on_toggle_always_on_top,
            width=36,
        )
        self._always_on_top_switch.pack(side="right", padx=(5, 15))
        Tooltip(self._always_on_top_switch, "窗口始终显示在最前\n方便在游戏窗口上方操作")

    def _on_scan_interval_change(self, value):
        """扫描间隔滑块回调。"""
        interval = int(value)
        self._scan_interval_label.configure(text=f"{interval} ms")
        if self._monitor:
            self._monitor.scan_interval_ms = interval

    # ── 置顶切换 ──

    def _on_toggle_always_on_top(self):
        """切换窗口置顶状态。"""
        value = self._always_on_top_var.get()
        self.attributes("-topmost", value)
        self._save_regions()

    # ── 最小化 → 浮动窗 ──

    def _on_window_unmap(self, event=None):
        """检测窗口最小化（Unmap），切换为浮动窗模式。"""
        if event and event.widget != self:
            return
        if self._is_floating:
            return
        # 检查是否真正最小化（而非 withdraw）
        self.update_idletasks()
        if self.state() == "iconic":
            self._is_floating = True
            self.after(100, self._enter_floating_mode)

    def _on_window_map(self, event=None):
        """检测窗口恢复（Map），退出浮动窗模式。"""
        if event and event.widget != self:
            return
        if not self._is_floating:
            return
        self._is_floating = False
        self.after(50, self._exit_floating_mode)

    def _enter_floating_mode(self):
        """最小化到任务栏 → 改为显示浮动窗。"""
        self.withdraw()  # 从任务栏隐藏
        self._show_floating_window()

    def _exit_floating_mode(self):
        """恢复主窗口 → 关闭浮动窗。"""
        self._hide_floating_window()

    def _show_floating_window(self):
        """创建并显示浮动指示窗。"""
        if self._floating_window is not None:
            return
        self._floating_window = FloatingIndicator(
            on_restore=self._restore_from_floating,
            on_stop=self._stop_from_floating,
            on_exit=self._exit_from_floating,
        )
        self._floating_window.update_monitoring_status(self._is_monitoring)
        self._floating_window.update_match_count(self._match_total)

    def _hide_floating_window(self):
        """隐藏并销毁浮动指示窗。"""
        if self._floating_window is not None:
            try:
                self._floating_window.destroy()
            except Exception:
                pass
            self._floating_window = None

    def _restore_from_floating(self):
        """从浮动窗恢复主窗口。"""
        self._is_floating = False
        self.deiconify()
        self.lift()
        self.focus_set()

    def _stop_from_floating(self):
        """从浮动窗停止监控。"""
        if self._is_monitoring:
            self._stop_monitoring()
        if self._floating_window:
            self._floating_window.update_monitoring_status(False)

    def _exit_from_floating(self):
        """从浮动窗退出应用。"""
        self._on_closing()

    def _toggle_monitoring(self):
        """切换监控运行状态。"""
        if self._is_monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _refresh_start_button_state(self):
        """根据当前区域和目标数量，更新开始按钮的可用状态。"""
        if self._is_monitoring:
            return  # 运行中不调整
        enabled = [r for r in self._regions if r.get("enabled", True)]
        has_regions = bool(enabled)
        # 检查是否有可用目标：全局目标非空 OR 至少一个启用区域有专属目标
        has_any_targets = bool(self._targets) or any(
            r.get("targets") for r in enabled
        )
        can_start = has_regions and has_any_targets

        if can_start:
            self._btn_start.configure(
                state="normal",
                fg_color=COLOR_SUCCESS,
                hover_color="#219A52",
            )
            self._start_btn_tooltip._text = (
                "开始循环监控所有启用的区域\n"
                "自动截图 → OCR → 匹配 → 点击"
            )
        else:
            self._btn_start.configure(
                state="disabled",
                fg_color=COLOR_DISABLED,
            )
            reasons = []
            if not has_regions:
                reasons.append("无监控区域")
            if not has_any_targets:
                reasons.append("无目标文字")
            self._start_btn_tooltip._text = (
                f"当前不可用：{'，'.join(reasons)}\n"
                "请先在左侧添加区域，在右侧添加目标文字"
            )

    def _start_monitoring(self):
        """启动监控循环。"""
        import time as _time

        # 检查 Tesseract OCR 是否可用
        if not getattr(self, '_tesseract_ok', True):
            mb.showerror(
                "OCR 不可用",
                "Tesseract OCR 引擎未安装或路径不正确，无法执行识别。\n\n"
                "请在以下位置安装 Tesseract 5.x：\n"
                f"{TESSERACT_CMD}\n\n"
                "安装完成后重启本软件。",
            )
            return

        # 检查必要条件
        enabled = [r for r in self._regions if r.get("enabled", True)]
        if not enabled:
            self._update_status_text("⚠️ 请先添加监控区域：点击左侧「添加区域」框选屏幕区域")
            return
        has_any_targets = bool(self._targets) or any(
            r.get("targets") for r in enabled
        )
        if not has_any_targets:
            self._update_status_text("⚠️ 请先添加目标文字：在右侧输入要自动点击的文字")
            return

        # 创建监控循环（复用或新建）
        if self._monitor is None:
            self._monitor = MonitorLoop(
                regions=self._regions,
                targets=self._targets,
                log_queue=self._log_queue,
                ocr_engine=self._ocr_engine,
                screen_cap=self._screen_cap,
                clicker=self._clicker,
                scan_interval_ms=self._scan_interval_var.get(),
                tesseract_ok=self._tesseract_ok,
            )

        self._monitor.start()
        self._is_monitoring = True
        self._match_total = 0  # 重置匹配计数

        # 更新 UI
        self._btn_start.configure(
            text="■  停止监控",
            fg_color=COLOR_ERROR,
            hover_color="#C0392B",
        )
        self._monitor_status_label.configure(
            text="▶  运行中",
            text_color=COLOR_SUCCESS,
        )

        # 更新浮动窗
        if self._floating_window is not None:
            self._floating_window.update_monitoring_status(True)
            self._floating_window.update_match_count(0)

        # 启动日志轮询
        self._start_log_polling()
        self._update_status_text("监控已启动")

        # 输出醒目的启动信息到日志面板
        self._log_panel.add_entry(
            _time.strftime("%H:%M:%S"),
            f"▶ 监控已启动 — 区域 {len(enabled)} 个，"
            f"目标 {len(self._targets)} 个（含专属目标）",
            "info",
        )

        # 自动最小化到悬浮窗，避免遮挡被监控的屏幕内容
        self.after(300, self._auto_minimize_for_monitoring)

    def _stop_monitoring(self):
        """停止监控循环。"""
        if self._monitor:
            self._monitor.stop()
        self._is_monitoring = False

        # 更新 UI
        self._btn_start.configure(
            text="▶  开始监控",
            fg_color=COLOR_SUCCESS,
            hover_color="#219A52",
        )
        self._monitor_status_label.configure(
            text="⏹  已停止",
            text_color=COLOR_TEXT_SECONDARY,
        )

        # 更新浮动窗
        if self._floating_window is not None:
            self._floating_window.update_monitoring_status(False)

        # 停止日志轮询
        self._stop_log_polling()
        self._update_status()
        self._update_status_text("监控已停止，可修改配置后重新开始")

        # 如果之前自动最小化了，恢复窗口
        self._auto_restore_from_monitoring()

    # ── 自动最小化/恢复（确保不遮挡监控画面） ──

    def _auto_minimize_for_monitoring(self):
        """监控启动后自动最小化到悬浮窗，避免遮挡屏幕内容。"""
        if not self._is_monitoring:
            return
        # 如果当前不是浮动状态，最小化
        if not self._is_floating and self.state() != "iconic":
            self.iconify()  # 触发 <Unmap> → _enter_floating_mode

    def _auto_restore_from_monitoring(self):
        """监控停止后自动从悬浮窗恢复主窗口。"""
        if self._is_floating:
            self._is_floating = False
            self.deiconify()
            self.lift()
            self.focus_set()
            self._hide_floating_window()

    # ────────────────────── 日志轮询 ──────────────────────

    def _start_log_polling(self):
        """启动定时器，周期性从队列读取日志并显示。"""
        self._poll_log_queue()

    def _stop_log_polling(self):
        """停止日志轮询。"""
        if self._log_poll_id:
            self.after_cancel(self._log_poll_id)
            self._log_poll_id = None

    def _poll_log_queue(self):
        """从日志队列取出所有消息并显示（由 after 定时器驱动）。"""
        if not self._is_monitoring:
            return

        # 取出队列中所有待处理日志
        processed = 0
        while True:
            try:
                entry = self._log_queue.get_nowait()
                self._log_panel.add_entry(
                    entry["time"],
                    entry["message"],
                    entry["level"],
                )
                # 累计 match/click 次数（用于浮动窗显示）
                if entry["level"] in ("match", "click"):
                    self._match_total += 1
                processed += 1
            except queue.Empty:
                break

        # 更新浮动窗匹配计数
        if self._floating_window is not None and processed > 0:
            self._floating_window.update_match_count(self._match_total)

        # 如果有新日志，更新状态栏
        if processed > 0:
            self._status_label.configure(
                text=f"● 监控运行中  |  区域：{len([r for r in self._regions if r.get('enabled', True)])} 个"
                     f"  |  目标：{len(self._targets)} 个"
            )

        # 继续轮询（每 200ms）
        self._log_poll_id = self.after(200, self._poll_log_queue)

    # ── 窗口关闭事件 ──

    def _on_closing(self):
        """关闭窗口前停止监控，清理资源。"""
        if self._is_monitoring:
            self._stop_monitoring()
        # 清理浮动窗
        self._hide_floating_window()
        # 清理 Tooltip 资源
        if hasattr(self, '_start_btn_tooltip'):
            self._start_btn_tooltip.destroy()
        self.destroy()

    # ────────────────────── 区域管理操作 ──────────────────────

    def _on_add_region(self):
        """打开区域选择器，框选一个区域并添加到列表中。"""
        result = self._selector.select(self)
        if result is None:
            return

        left, top, width, height = result

        region_id = str(uuid.uuid4())[:8]
        count = len(self._regions) + 1
        region = {
            "id": region_id,
            "name": f"区域 {count}",
            "coords": {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            },
            "enabled": True,
            "targets": [],   # 每区域独立目标列表
        }

        self._regions.append(region)
        self._add_region_ui(region)
        self._save_regions()
        self._update_status()
        self._refresh_region_menu()

    def _add_region_ui(self, region: dict):
        """在区域列表中添加一个卡片。"""
        enabled = region.get("enabled", True)
        frame = ctk.CTkFrame(
            self._region_scroll,
            fg_color=COLOR_BG,
            corner_radius=8,
            border_width=2,
            border_color=COLOR_SUCCESS if enabled else COLOR_DISABLED,
        )
        frame.pack(fill="x", padx=3, pady=3)

        item = RegionItem(
            frame,
            region_data=region,
            on_delete=self._on_delete_region,
            on_toggle=self._on_toggle_region,
            on_targets_changed=self._on_region_targets_changed,
            fg_color="transparent",
        )
        item.pack(fill="both", expand=True)

        self._region_items[region["id"]] = item
        self._region_item_frames[region["id"]] = frame

    def _on_delete_region(self, region_id: str):
        """删除指定区域。"""
        self._regions = [r for r in self._regions if r["id"] != region_id]

        if region_id in self._region_item_frames:
            self._region_item_frames[region_id].destroy()
            del self._region_item_frames[region_id]
        if region_id in self._region_items:
            del self._region_items[region_id]

        self._save_regions()
        self._update_status()

    def _on_toggle_region(self, region_id: str, enabled: bool):
        """启用或禁用一个区域。"""
        for r in self._regions:
            if r["id"] == region_id:
                r["enabled"] = enabled
                break
        self._save_regions()
        self._update_status()
        self._refresh_region_menu()

    def _on_region_targets_changed(self, region_id: str):
        """区域专属目标变更时自动保存配置。"""
        self._save_regions()
        self._update_status()

    def _update_status(self):
        """刷新底部状态栏（监控状态 + 区域数 + 目标数），同时更新按钮状态。"""
        total = len(self._regions)
        enabled = sum(1 for r in self._regions if r.get("enabled", True))
        target_count = len(self._targets)
        monitor_state = "● 运行中" if self._is_monitoring else "○ 已停止"

        if self._is_monitoring:
            status_text = (
                f"状态：{monitor_state}  |  区域：{total} 个（启用 {enabled} 个）"
                f"  |  目标：{target_count} 个"
            )
        else:
            # 就绪状态：显示引导提示
            hints = []
            if not enabled:
                hints.append("💡 点击「添加区域」框选屏幕区域")
            if not target_count:
                hints.append("💡 输入目标文字并点击「添加」")
            if hints:
                status_text = "  |  ".join(hints)
            else:
                status_text = (
                    f"状态：{monitor_state}  |  区域：{total} 个（启用 {enabled} 个）"
                    f"  |  目标：{target_count} 个"
                )

        self._status_label.configure(text=status_text)
        self._refresh_start_button_state()

    # ────────────────────── 配置持久化 ──────────────────────

    def _config_path(self) -> Path:
        """获取配置文件路径（项目根目录）。"""
        return Path(__file__).resolve().parent.parent / CONFIG_FILE

    def _save_regions(self):
        """将区域配置 + 目标列表 + 扫描间隔 + 置顶偏好写入 JSON 文件。"""
        data = {
            "regions": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "coords": r["coords"],
                    "enabled": r.get("enabled", True),
                    "targets": r.get("targets", []),
                }
                for r in self._regions
            ],
            "targets": list(self._targets),
            "scan_interval_ms": self._scan_interval_var.get(),
            "always_on_top": self._always_on_top_var.get() if hasattr(self, '_always_on_top_var') else False,
        }
        try:
            self._config_path().write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[保存配置失败] {e}")

    def _load_regions(self):
        """从 JSON 文件加载区域配置、目标列表、扫描间隔和置顶偏好。"""
        path = self._config_path()
        if not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                return  # 空文件，忽略
            data = json.loads(raw)
            for r in data.get("regions", []):
                # 校验必要字段，跳过损坏项
                if "id" not in r or "coords" not in r:
                    continue
                # 向后兼容：旧配置无 targets 字段
                if "targets" not in r:
                    r["targets"] = []
                self._regions.append(r)
                self._add_region_ui(r)
            # 加载目标列表
            saved_targets = data.get("targets", [])
            if saved_targets:
                self._targets = list(saved_targets)
                self._render_target_list()
            # 加载扫描间隔
            saved_interval = data.get("scan_interval_ms")
            if saved_interval:
                self._scan_interval_var.set(saved_interval)
                self._scan_interval_label.configure(text=f"{saved_interval} ms")
            # 加载置顶偏好
            always_on_top = data.get("always_on_top", False)
            if always_on_top and hasattr(self, '_always_on_top_var'):
                self._always_on_top_var.set(True)
                self.attributes("-topmost", True)
            self._update_status()
        except json.JSONDecodeError:
            # 配置文件损坏：备份后重置
            try:
                backup = path.with_suffix(".json.bak")
                path.rename(backup)
            except Exception:
                pass
            mb.showwarning(
                "配置文件已重置",
                "config.json 配置文件已损坏，已自动备份并重置为默认值。",
            )
        except Exception as e:
            print(f"[加载配置失败] {e}")
