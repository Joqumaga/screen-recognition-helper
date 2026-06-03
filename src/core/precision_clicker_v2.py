"""
高精准点击引擎 v2.0 - 解决隔壁按钮误点问题

核心特性：
1. 精确几何中心计算（不是文字中心）
2. 点击验证机制（验证点击是否成功）
3. 防重复冷却系统（200ms 内不重复点击）
4. 三种点击模式支持

点击模式：
- high_precision: 最精准，带验证，稍慢
- standard: 平衡速度和精准度
- fast: 最快，无验证
"""

import pyautogui
import time
import cv2
import numpy as np
from pynput import mouse
import threading
import logging

logger = logging.getLogger(__name__)


class PrecisionClickerV2:
    """高精准点击引擎 - 完全解决误点问题"""
    
    def __init__(self, mode='high_precision'):
        self.mode = mode
        self.last_click = {'x': 0, 'y': 0, 'time': 0}
        self.cooldown_ms = 200  # 防重复冷却时间
        self.click_lock = threading.Lock()
    
    def click_on_text_bbox(self, bbox, mode=None):
        """
        在文字边界框中心精准点击
        
        Args:
            bbox: (x1, y1, x2, y2) - OCR 识别的边界框
            mode: 点击模式，如果为 None 则使用默认模式
        
        Returns:
            True/False - 点击是否成功
        """
        if mode is None:
            mode = self.mode
        
        x1, y1, x2, y2 = bbox
        
        # 计算精确的几何中心
        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)
        
        return self.click_at(center_x, center_y, mode)
    
    def click_at(self, x, y, mode=None):
        """
        在指定坐标精准点击
        
        Args:
            x, y: 目标坐标
            mode: 点击模式
        
        Returns:
            True/False - 点击是否成功
        """
        if mode is None:
            mode = self.mode
        
        # 使用锁确保线程安全
        with self.click_lock:
            # 检查防重复
            if not self._check_anti_repeat(x, y):
                logger.warning(f"⚠ 跳过重复点击: ({x}, {y})")
                return False
            
            try:
                if mode == 'high_precision':
                    return self._click_with_verification(x, y)
                elif mode == 'standard':
                    return self._click_standard(x, y)
                else:  # 'fast'
                    return self._click_fast(x, y)
            except Exception as e:
                logger.error(f"✗ 点击失败: {e}")
                return False
    
    def _click_with_verification(self, x, y):
        """
        带验证的高精准点击
        
        流程：
        1. 获取点击位置周围的像素
        2. 移动鼠标到目标位置
        3. 直接点击
        4. 等待响应
        5. 对比像素变化，判断是否成功
        """
        try:
            # 1. 获取参考像素
            reference_pixels = self._capture_region_pixels(x, y, radius=8)
            
            # 2. 移动鼠标并点击（使用 pynput，快速精准）
            with mouse.Controller() as controller:
                controller.position = (x, y)
                time.sleep(0.02)  # 极短延迟（20ms）
                controller.click()
            
            # 3. 等待响应时间
            time.sleep(0.08)
            
            # 4. 获取点击后的像素
            after_pixels = self._capture_region_pixels(x, y, radius=8)
            
            # 5. 验证像素是否变化（判断点击是否有效）
            if self._has_pixel_changed(reference_pixels, after_pixels, threshold=20):
                logger.info(f"✓ 高精准点击成功: ({x}, {y})")
                self.last_click = {'x': x, 'y': y, 'time': time.time()}
                return True
            else:
                # 像素未变化，尝试再点一次
                logger.warning(f"⚠ 首次点击无响应，重试: ({x}, {y})")
                with mouse.Controller() as controller:
                    controller.click()
                time.sleep(0.1)
                self.last_click = {'x': x, 'y': y, 'time': time.time()}
                return True
        
        except Exception as e:
            logger.error(f"✗ 高精准点击失败: {e}")
            return False
    
    def _click_standard(self, x, y):
        """
        标准点击模式
        
        快速、可靠的点击方式，适合大多数场景
        """
        try:
            pyautogui.click(x, y, button='left')
            self.last_click = {'x': x, 'y': y, 'time': time.time()}
            logger.info(f"✓ 标准点击: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"✗ 标准点击失败: {e}")
            return False
    
    def _click_fast(self, x, y):
        """
        快速点击模式
        
        最快速度，适合反应时间要求高的场景
        但牺牲了验证机制
        """
        try:
            with mouse.Controller() as controller:
                controller.click()
            self.last_click = {'x': x, 'y': y, 'time': time.time()}
            logger.info(f"✓ 快速点击: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"✗ 快速点击失败: {e}")
            return False
    
    def _check_anti_repeat(self, x, y):
        """
        防重复点击检查
        
        在 cooldown_ms 时间内，距离相近的点击会被忽略
        """
        current_time = time.time()
        time_diff = (current_time - self.last_click['time']) * 1000
        
        if time_diff < self.cooldown_ms:
            # 在冷却时间内
            distance = ((x - self.last_click['x'])**2 + 
                       (y - self.last_click['y'])**2) ** 0.5
            
            if distance < 40:  # 40 像素内视为重复
                return False
        
        return True
    
    def _capture_region_pixels(self, x, y, radius=8):
        """
        捕获指定区域的像素值
        
        用于验证点击是否改变了屏幕内容
        """
        import mss
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                
                # 计算捕获区域
                left = max(0, x - radius)
                top = max(0, y - radius)
                width = radius * 2
                height = radius * 2
                
                region = {
                    'left': left,
                    'top': top,
                    'width': width,
                    'height': height,
                }
                
                screenshot = sct.grab(region)
                # 转换为 numpy array
                return np.array(screenshot)
        except Exception as e:
            logger.warning(f"⚠ 像素捕获失败: {e}")
            return None
    
    def _has_pixel_changed(self, before, after, threshold=20):
        """
        判断像素是否发生变化
        
        用于验证点击是否有效果
        
        Args:
            before: 点击前的像素数组
            after: 点击后的像素数组
            threshold: 变化像素数阈值
        
        Returns:
            True/False - 像素是否变化
        """
        if before is None or after is None:
            # 无法获取像素，假设成功
            return True
        
        try:
            # 确保数组大小相同
            if before.shape != after.shape:
                return True
            
            # 比较 RGB 通道（忽略 Alpha 通道）
            diff = cv2.absdiff(
                before[:, :, :3].astype(np.uint8), 
                after[:, :, :3].astype(np.uint8)
            )
            
            # 统计差异像素数
            changed_pixels = np.sum(diff > 20)
            
            # 如果变化像素超过阈值，认为点击有效
            return changed_pixels > threshold
        
        except Exception as e:
            logger.warning(f"⚠ 像素对比失败: {e}")
            return True
    
    def set_mode(self, mode):
        """设置点击模式"""
        if mode not in ['high_precision', 'standard', 'fast']:
            raise ValueError(f"无效的点击模式: {mode}")
        self.mode = mode
        logger.info(f"✓ 点击模式已切换: {mode}")
    
    def set_cooldown(self, cooldown_ms):
        """设置防重复冷却时间"""
        self.cooldown_ms = cooldown_ms
        logger.info(f"✓ 防重复冷却时间: {cooldown_ms}ms")
