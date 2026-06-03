"""监控主循环模块。

在后台线程中持续执行完整的识别-匹配-点击链路：

    截图 → 预处理 → OCR → 匹配 → 点击 → 日志

通过 queue.Queue 将日志消息异步发送到 UI 线程，
不阻塞主界面交互。

每个处理步骤都有独立的异常捕获，错误日志包含步骤名和完整 traceback。
"""

from __future__ import annotations

import queue
import threading
import time
import traceback as _traceback

from config import SCAN_INTERVAL_MS
from core.screen_capture import ScreenCapture
from core.ocr_engine import OCREngine
from core.matcher import TargetMatcher
from core.clicker import MouseClicker
from utils.image_processor import ImageProcessor


class MonitorLoop:
    """监控主循环。

    对每个启用的监控区域执行：截图 → OCR → 匹配 → 点击，
    循环持续直到调用 stop()。

    用法:
        monitor = MonitorLoop(regions_ref, targets_ref, log_queue)
        monitor.start()           # 启动后台线程
        monitor.stop()            # 请求停止
        monitor.scan_interval_ms = 300  # 动态调节扫描间隔
    """

    def __init__(
        self,
        regions: list[dict],
        targets: list[str],
        log_queue: queue.Queue,
        ocr_engine: OCREngine | None = None,
        screen_cap: ScreenCapture | None = None,
        clicker: MouseClicker | None = None,
        scan_interval_ms: int = SCAN_INTERVAL_MS,
        tesseract_ok: bool = True,
    ):
        """
        Args:
            regions: 区域列表引用（外部持有，每次 tick 快照）
            targets: 目标文字列表引用
            log_queue: 日志消息队列（UI 线程从中读取）
            ocr_engine: OCR 引擎（不传则自动创建）
            screen_cap: 截图器
            clicker: 鼠标点击器
            scan_interval_ms: 扫描间隔（毫秒）
            tesseract_ok: Tesseract OCR 是否可用
        """
        self._regions = regions
        self._targets = targets
        self._log_queue = log_queue
        self._ocr = ocr_engine or OCREngine()
        self._screen_cap = screen_cap or ScreenCapture()
        self._clicker = clicker or MouseClicker()
        self._matcher = TargetMatcher()
        self._interval = scan_interval_ms
        self._running = False
        self._thread: threading.Thread | None = None
        self._tesseract_ok = tesseract_ok

        # ── 状态追踪（用于产生状态变化日志，避免刷屏） ──
        self._scan_round = 0                         # 累计扫描轮次
        self._last_ocr_state: dict[str, str] = {}    # region_id -> "empty"|"found"
        self._last_match_count: dict[str, int] = {}  # region_id -> 上次匹配数
        self._heartbeat_interval = 10                # 每 N 轮输出一次心跳

        # ── 异常去重 ──
        self._last_error_time: dict[str, float] = {}  # "region_id|step" -> timestamp
        self._dedup_seconds = 30                       # 同一区域同一步骤 30 秒内只报一次

    # ── 属性 ──────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """监控是否正在运行。"""
        return self._running

    @property
    def scan_interval_ms(self) -> int:
        return self._interval

    @scan_interval_ms.setter
    def scan_interval_ms(self, value: int):
        """设置扫描间隔（50-5000ms）。"""
        self._interval = max(50, min(5000, value))

    # ── 生命周期 ──────────────────────────────────

    def start(self):
        """启动监控循环（启动后台线程）。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._log("监控已启动", "info")

    def stop(self):
        """请求停止监控循环。"""
        self._running = False
        self._last_ocr_state.clear()
        self._last_match_count.clear()
        self._scan_round = 0
        self._log("监控已停止", "info")

    # ── 日志 ───────────────────────────────────────

    def _log(self, message: str, level: str = "info"):
        """向日志队列推送一条消息（非阻塞）。"""
        try:
            self._log_queue.put_nowait({
                "time": time.strftime("%H:%M:%S"),
                "message": message,
                "level": level,
            })
        except queue.Full:
            pass

    # ── 主循环 ────────────────────────────────────

    def _run(self):
        """后台线程主循环。"""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                tb = _traceback.format_exc()
                # 只取最后几行作为简短描述，避免刷屏
                short = tb.strip().split('\n')[-1] if tb else str(e)
                self._log(f"主循环异常，已自动恢复: {short}", "error")
            time.sleep(self._interval / 1000.0)

    def _tick(self):
        """一次完整的扫描周期：遍历所有启用的区域。"""
        # 快照当前状态（避免线程安全问题）
        active = [r for r in self._regions if r.get("enabled", True)]

        if not active:
            time.sleep(0.5)
            return

        for region in active:
            if not self._running:
                break

            # 按区域解析目标：优先使用区域专属目标，否则使用全局目标
            region_targets = region.get("targets")
            if region_targets:
                targets = list(region_targets)
            else:
                targets = list(self._targets)

            if not targets:
                # 该区域无可用目标（无专属目标且无全局目标），跳过
                continue

            try:
                self._process_region(region, targets)
            except Exception as e:
                tb = _traceback.format_exc()
                short = tb.strip().split('\n')[-1] if tb else str(e)
                # 兜底捕获（分步异常已经在 _process_region 内部处理）
                self._log(
                    f"[{region.get('name', '?')}] 未捕获异常: {short}",
                    "error",
                )

        # 心跳汇总
        self._scan_round += 1
        if self._scan_round % self._heartbeat_interval == 0:
            self._emit_heartbeat(active)

    def _emit_heartbeat(self, active_regions: list[dict]):
        """每 N 轮输出一次扫描活动汇总，让用户感知监控正在运行。"""
        parts = []
        for r in active_regions:
            name = r.get("name", "?")
            state = self._last_ocr_state.get(r["id"], "empty")
            mc = self._last_match_count.get(r["id"], 0)
            if state == "empty":
                parts.append(f"{name}: 无文字")
            elif mc > 0:
                parts.append(f"{name}: 匹配{mc}次")
            else:
                parts.append(f"{name}: 未匹配")
        self._log(
            f"第{self._scan_round}轮扫描 | {' · '.join(parts)}",
            "info",
        )

    # ── 异常去重 ───────────────────────────────────

    def _should_log_error(self, region: dict, step: str) -> bool:
        """检查该区域的某步骤异常是否需要记录（去重）。"""
        key = f"{region['id']}|{step}"
        now = time.time()
        last = self._last_error_time.get(key, 0.0)
        if now - last < self._dedup_seconds:
            return False
        self._last_error_time[key] = now
        return True

    # ── 主处理逻辑 ──────────────────────────────────

    def _process_region(self, region: dict, targets: list):
        """对单个区域执行截图 → OCR → 匹配 → 点击（分步异常捕获）。"""
        name = region.get("name", "?")
        rid = region["id"]
        coords = region["coords"]

        # ── 步骤 1：截图 ──
        try:
            img_bgra = self._screen_cap.capture(coords)
        except Exception as e:
            if self._should_log_error(region, "screenshot"):
                tb = _traceback.format_exc()
                self._log(f"[{name}] 截图失败: {e}", "error")
            return

        # ── 步骤 2：预处理 ──
        try:
            processed = ImageProcessor.preprocess(img_bgra)
        except Exception as e:
            if self._should_log_error(region, "preprocess"):
                tb = _traceback.format_exc()
                self._log(f"[{name}] 图像预处理失败: {e}", "error")
            return

        # ── 步骤 3：OCR 识别 ──
        try:
            results = self._ocr.recognize(processed)
        except Exception as e:
            if self._should_log_error(region, "ocr"):
                tb = _traceback.format_exc()
                self._log(f"[{name}] OCR 识别失败: {e}", "error")
            return
        old_ocr_state = self._last_ocr_state.get(rid)

        if not results:
            # 仅在状态变化时输出（found -> empty），避免刷屏
            if old_ocr_state != "empty":
                self._log(f"[{name}] 未识别到文字", "info")
                self._last_ocr_state[rid] = "empty"
                self._last_match_count[rid] = 0
            return

        # OCR 有结果 → 更新状态
        if old_ocr_state != "found":
            self._log(f"[{name}] 识别到 {len(results)} 项文字", "info")
            self._last_ocr_state[rid] = "found"

        # ── 步骤 4：匹配目标（使用包含匹配，更适用于游戏界面文字）─
        try:
            matches = self._matcher.match(results, targets, mode="fuzzy")
        except Exception as e:
            if self._should_log_error(region, "match"):
                tb = _traceback.format_exc()
                self._log(f"[{name}] 目标匹配失败: {e}", "error")
            return
        old_match_count = self._last_match_count.get(rid, -1)
        new_match_count = len(matches)
        self._last_match_count[rid] = new_match_count

        if not matches:
            # 仅在匹配数变化时输出
            if old_match_count != 0:
                self._log(f"[{name}] 未匹配到目标文字", "info")
            return

        # 匹配到目标
        if old_match_count != new_match_count:
            self._log(
                f"[{name}] 匹配到 {new_match_count} 个目标",
                "match",
            )

        # ── 步骤 5：对每个匹配结果执行点击 ──
        for m in matches:
            if not self._running:
                break

            screen_x = coords["left"] + m.center[0]
            screen_y = coords["top"] + m.center[1]

            try:
                self._clicker.click_at(screen_x, screen_y)
                self._log(
                    f"[{name}] 点击「{m.target}」"
                    f"  ({screen_x}, {screen_y})",
                    "click",
                )
            except Exception as e:
                if self._should_log_error(region, "click"):
                    self._log(f"[{name}] 点击失败 ({screen_x},{screen_y}): {e}", "error")
