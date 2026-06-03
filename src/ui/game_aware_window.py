"""
游戏感知窗口 - 支持置顶和在游戏内选择区域

核心功能：
1. 窗口置顶（Always On Top）
2. 全屏半透明选择器（解决退回桌面问题）
3. 全局快捷键支持（无需窗口焦点）
4. 快速区域管理

快捷键：
- Ctrl+Shift+A: 在游戏内选择区域
- Ctrl+Shift+S: 开始监控
- Ctrl+Shift+E: 停止监控
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import time
from PIL import Image, ImageDraw
import mss
import json
import os
from pathlib import Path

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("⚠ 警告: keyboard 库未安装，快捷键功能将不可用")


class GameAwareWindow(ctk.CTk):
    """游戏感知的置顶浮窗"""
    
    def __init__(self, on_start_callback=None, on_stop_callback=None):
        super().__init__()
        
        self.title("屏幕识别点击助手 - 游戏置顶模式")
        self.geometry("500x700+100+100")
        
        # 设置窗口置顶
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.98)
        
        # 回调函数
        self.on_start_callback = on_start_callback
        self.on_stop_callback = on_stop_callback
        
        # 状态
        self.is_selecting_region = False
        self.is_monitoring = False
        self.selected_regions = []
        self.config_file = Path(__file__).parent.parent / "regions_config.json"
        
        # 监控参数
        self.scan_interval_ms = 200
        self.click_mode = 'high_precision'
        
        # UI 初始化
        self._setup_ui()
        self._load_saved_regions()
        self._register_global_hotkeys()
        
        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_ui(self):
        """设置 UI 界面 - Apple 风格"""
        
        # 设置主题
        ctk.set_appearance_mode("dark")
        
        # ==================== 顶部控制栏 ====================
        top_frame = ctk.CTkFrame(self, fg_color="#1D2749", corner_radius=14)
        top_frame.pack(padx=10, pady=10, fill="x")
        
        # 标题
        title_label = ctk.CTkLabel(
            top_frame,
            text="🎮 游戏置顶模式 v2.0",
            font=("SF Pro Display", 16, "bold"),
            text_color="#00D4FF"
        )
        title_label.pack(padx=15, pady=8)
        
        # 快捷键提示
        hotkey_label = ctk.CTkLabel(
            top_frame,
            text="⌨️  Ctrl+Shift+A 选区 | Ctrl+Shift+S 开始 | Ctrl+Shift+E 停止",
            font=("SF Pro Display", 9),
            text_color="#A1A1A6"
        )
        hotkey_label.pack(padx=15, pady=5)
        
        # ==================== 按钮区 ====================
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(padx=10, pady=10, fill="x")
        
        # 选择区域按钮（大按钮）
        self.select_btn = ctk.CTkButton(
            button_frame,
            text="🎯 在游戏内选择区域",
            command=self._start_region_selection,
            width=380,
            height=44,
            corner_radius=12,
            font=("SF Pro Display", 13, "bold"),
            fg_color="#00D4FF",
            hover_color="#00B8E6",
            text_color="#0A0E27"
        )
        self.select_btn.pack(pady=8)
        
        # 控制按钮区
        control_frame = ctk.CTkFrame(button_frame, fg_color="transparent")
        control_frame.pack(fill="x", pady=8)
        
        self.start_btn = ctk.CTkButton(
            control_frame,
            text="▶ 开始",
            command=self._start_monitoring,
            width=170,
            height=40,
            corner_radius=12,
            font=("SF Pro Display", 12, "bold"),
            fg_color="#34C759",
            hover_color="#2EBF52",
            text_color="white"
        )
        self.start_btn.pack(side="left", padx=3)
        
        self.stop_btn = ctk.CTkButton(
            control_frame,
            text="⏹ 停止",
            command=self._stop_monitoring,
            width=170,
            height=40,
            corner_radius=12,
            font=("SF Pro Display", 12, "bold"),
            fg_color="#FF3B30",
            hover_color="#E83935",
            text_color="white"
        )
        self.stop_btn.pack(side="left", padx=3)
        
        # ==================== 区域列表 ====================
        region_label = ctk.CTkLabel(
            self,
            text="已选择的区域",
            font=("SF Pro Display", 12, "bold"),
            text_color="#F5F5F7"
        )
        region_label.pack(anchor="w", padx=15, pady=(12, 5))
        
        self.region_list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="#16213E",
            corner_radius=12,
            border_width=1,
            border_color="#2A3F5F"
        )
        self.region_list_frame.pack(padx=10, pady=5, fill="both", expand=True)
        
        # ==================== 参数设置区 ====================
        param_label = ctk.CTkLabel(
            self,
            text="⚙️ 参数设置",
            font=("SF Pro Display", 12, "bold"),
            text_color="#F5F5F7"
        )
        param_label.pack(anchor="w", padx=15, pady=(12, 5))
        
        param_frame = ctk.CTkFrame(self, fg_color="#1D2749", corner_radius=12)
        param_frame.pack(padx=10, pady=5, fill="x")
        
        # 扫描间隔
        interval_label = ctk.CTkLabel(
            param_frame,
            text="扫描间隔 (ms):",
            text_color="#A1A1A6",
            font=("SF Pro Display", 10)
        )
        interval_label.grid(row=0, column=0, padx=12, pady=10, sticky="w")
        
        self.scan_interval_var = tk.IntVar(value=200)
        scan_slider = ctk.CTkSlider(
            param_frame,
            from_=50,
            to=10000,
            variable=self.scan_interval_var,
            command=self._on_interval_change,
            progress_color="#00D4FF"
        )
        scan_slider.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.scan_interval_label = ctk.CTkLabel(
            param_frame,
            text="200ms",
            text_color="#00D4FF",
            font=("SF Pro Display", 11, "bold"),
            width=60
        )
        self.scan_interval_label.grid(row=0, column=2, padx=12, pady=10)
        
        # 点击模式
        mode_label = ctk.CTkLabel(
            param_frame,
            text="点击模式:",
            text_color="#A1A1A6",
            font=("SF Pro Display", 10)
        )
        mode_label.grid(row=1, column=0, padx=12, pady=10, sticky="w")
        
        self.click_mode_var = tk.StringVar(value="high_precision")
        mode_menu = ctk.CTkOptionMenu(
            param_frame,
            values=["high_precision", "standard", "fast"],
            variable=self.click_mode_var,
            command=self._on_mode_change,
            fg_color="#0A0E27",
            button_color="#00D4FF",
            button_hover_color="#00B8E6"
        )
        mode_menu.grid(row=1, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        
        param_frame.columnconfigure(1, weight=1)
        
        # ==================== 状态栏 ====================
        status_frame = ctk.CTkFrame(self, fg_color="#0A0E27", corner_radius=12)
        status_frame.pack(padx=10, pady=10, fill="x")
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="✓ 就绪",
            font=("SF Pro Display", 11),
            text_color="#34C759"
        )
        self.status_label.pack(padx=12, pady=10)
    
    def _start_region_selection(self):
        """启动游戏内区域选择"""
        if self.is_selecting_region:
            messagebox.showwarning("提示", "正在选择区域，请稍候...")
            return
        
        if self.is_monitoring:
            messagebox.showwarning("提示", "监控进行中，请先停止监控")
            return
        
        self.is_selecting_region = True
        self.status_label.configure(text="⏳ 准备选择区域...", text_color="#FF9500")
        self.update()
        
        # 在新线程中执行选择
        thread = threading.Thread(target=self._region_selector_thread, daemon=True)
        thread.start()
    
    def _region_selector_thread(self):
        """区域选择线程"""
        time.sleep(0.5)  # 稍作延迟，给用户时间准备
        self.withdraw()  # 隐藏主窗口
        self._create_region_selector_window()
    
    def _create_region_selector_window(self):
        """创建全屏半透明选择窗口"""
        
        # 获取屏幕信息
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screen_width = monitor['width']
                screen_height = monitor['height']
        except:
            self.deiconify()
            self.is_selecting_region = False
            return
        
        # 创建全屏窗口
        selector_window = tk.Toplevel(self)
        selector_window.geometry(f"{screen_width}x{screen_height}+0+0")
        selector_window.attributes('-topmost', True)
        selector_window.attributes('-alpha', 0.25)  # 半透明
        selector_window.configure(bg='gray')
        
        # Canvas 用于绘制选择框
        canvas = tk.Canvas(
            selector_window,
            bg='gray',
            highlightthickness=0,
            cursor="crosshair"
        )
        canvas.pack(fill="both", expand=True)
        
        # 选择状态
        selection_state = {
            'start_x': 0,
            'start_y': 0,
            'end_x': 0,
            'end_y': 0,
            'rect': None,
            'text': None
        }
        
        def on_press(event):
            """鼠标按下"""
            selection_state['start_x'] = event.x
            selection_state['start_y'] = event.y
        
        def on_drag(event):
            """鼠标拖拽"""
            if selection_state['rect']:
                canvas.delete(selection_state['rect'])
            if selection_state['text']:
                canvas.delete(selection_state['text'])
            
            selection_state['end_x'] = event.x
            selection_state['end_y'] = event.y
            
            # 绘制选择框（绿色边框）
            selection_state['rect'] = canvas.create_rectangle(
                selection_state['start_x'],
                selection_state['start_y'],
                selection_state['end_x'],
                selection_state['end_y'],
                outline='#00FF00',
                width=4
            )
            
            # 显示尺寸信息
            width = abs(selection_state['end_x'] - selection_state['start_x'])
            height = abs(selection_state['end_y'] - selection_state['start_y'])
            text = f"{width}x{height}"
            selection_state['text'] = canvas.create_text(
                (selection_state['start_x'] + selection_state['end_x']) // 2,
                (selection_state['start_y'] + selection_state['end_y']) // 2,
                text=text,
                fill='#00FF00',
                font=("Arial", 14, "bold")
            )
        
        def on_release(event):
            """鼠标释放 - 确认选择"""
            region = {
                'x1': min(selection_state['start_x'], selection_state['end_x']),
                'y1': min(selection_state['start_y'], selection_state['end_y']),
                'x2': max(selection_state['start_x'], selection_state['end_x']),
                'y2': max(selection_state['start_y'], selection_state['end_y']),
            }
            
            # 验证选择框大小
            width = region['x2'] - region['x1']
            height = region['y2'] - region['y1']
            
            if width > 20 and height > 20:
                self.selected_regions.append(region)
                self._add_region_to_list(region)
                self._save_regions()
                print(f"✓ 选择区域: {region}")
            else:
                print("✗ 选择区域过小，已取消")
            
            # 关闭选择窗口
            selector_window.destroy()
            self.is_selecting_region = False
            
            # 恢复主窗口
            self.deiconify()
            self.lift()
            self.attributes('-topmost', True)
            self.status_label.configure(text="✓ 就绪", text_color="#34C759")
        
        def on_escape(event):
            """按 ESC 取消"""
            selector_window.destroy()
            self.is_selecting_region = False
            self.deiconify()
            self.lift()
            self.attributes('-topmost', True)
            self.status_label.configure(text="✓ 已取消选择", text_color="#A1A1A6")
        
        # 绑定事件
        canvas.bind('<Button-1>', on_press)
        canvas.bind('<B1-Motion>', on_drag)
        canvas.bind('<ButtonRelease-1>', on_release)
        selector_window.bind('<Escape>', on_escape)
        
        # 置顶
        selector_window.lift()
    
    def _add_region_to_list(self, region):
        """将区域添加到列表显示"""
        region_item = ctk.CTkFrame(
            self.region_list_frame,
            fg_color="#0A0E27",
            corner_radius=8,
            border_width=1,
            border_color="#2A3F5F"
        )
        region_item.pack(padx=8, pady=5, fill="x")
        
        # 信息文本
        width = region['x2'] - region['x1']
        height = region['y2'] - region['y1']
        info_text = f"区域 #{len(self.selected_regions)}: ({region['x1']}, {region['y1']}) → ({region['x2']}, {region['y2']}) [{width}x{height}]"
        
        info_label = ctk.CTkLabel(
            region_item,
            text=info_text,
            font=("SF Pro Display", 10),
            text_color="#F5F5F7"
        )
        info_label.pack(padx=10, pady=6, anchor="w")
        
        # 删除按钮
        delete_btn = ctk.CTkButton(
            region_item,
            text="删除",
            width=50,
            height=25,
            font=("SF Pro Display", 9),
            fg_color="#FF3B30",
            hover_color="#E83935",
            command=lambda: self._delete_region(region_item, region)
        )
        delete_btn.pack(padx=10, pady=5, anchor="e")
    
    def _delete_region(self, widget, region):
        """删除区域"""
        widget.destroy()
        if region in self.selected_regions:
            self.selected_regions.remove(region)
            self._save_regions()
    
    def _start_monitoring(self):
        """开始监控"""
        if not self.selected_regions:
            messagebox.showwarning("提示", "请先选择至少一个区域")
            return
        
        if self.is_monitoring:
            messagebox.showinfo("提示", "已在监控中")
            return
        
        self.is_monitoring = True
        self.start_btn.configure(state="disabled")
        self.status_label.configure(text="▶ 监控中...", text_color="#34C759")
        self.update()
        
        if self.on_start_callback:
            self.on_start_callback(
                self.selected_regions,
                self.scan_interval_ms,
                self.click_mode_var.get()
            )
    
    def _stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False
        self.start_btn.configure(state="normal")
        self.status_label.configure(text="⏹ 已停止", text_color="#FF9500")
        
        if self.on_stop_callback:
            self.on_stop_callback()
    
    def _on_interval_change(self, value):
        """扫描间隔变化"""
        self.scan_interval_ms = int(float(value))
        self.scan_interval_label.configure(text=f"{self.scan_interval_ms}ms")
    
    def _on_mode_change(self, value):
        """点击模式变化"""
        self.click_mode = value
    
    def _register_global_hotkeys(self):
        """注册全局快捷键"""
        if not KEYBOARD_AVAILABLE:
            print("⚠ keyboard 库不可用，快捷键功能禁用")
            return
        
        try:
            keyboard.add_hotkey('ctrl+shift+a', self._start_region_selection)
            keyboard.add_hotkey('ctrl+shift+s', self._start_monitoring)
            keyboard.add_hotkey('ctrl+shift+e', self._stop_monitoring)
            print("✓ 全局快捷键已注册")
        except Exception as e:
            print(f"⚠ 快捷键注册失败: {e}")
    
    def _save_regions(self):
        """保存区域配置"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.selected_regions, f, indent=2)
        except Exception as e:
            print(f"✗ 保存区域失败: {e}")
    
    def _load_saved_regions(self):
        """加载保存的区域"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.selected_regions = json.load(f)
                    for region in self.selected_regions:
                        self._add_region_to_list(region)
        except Exception as e:
            print(f"✗ 加载区域失败: {e}")
    
    def _on_closing(self):
        """窗口关闭事件"""
        if self.is_monitoring:
            if messagebox.askokcancel("确认", "监控进行中，确定要关闭吗？"):
                self._stop_monitoring()
                self.destroy()
        else:
            self.destroy()
