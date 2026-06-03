"""图像预处理工具。

对屏幕截图进行灰度化、二值化、缩放放大、降噪等处理，
提高 Tesseract OCR 的识别准确率。
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


class ImageProcessor:
    """图像预处理管线。

    用法:
        processed = ImageProcessor.preprocess(bgra_array, scale_factor=2.0)
        # processed 是可以直接送入 pytesseract 的 PIL Image
    """

    @staticmethod
    def preprocess(
        image: np.ndarray,
        scale_factor: float = 2.0,
    ) -> Image.Image:
        """完整预处理管线：灰度 → 放大 → 二值化 → 降噪。

        Args:
            image: BGRA 格式的 numpy 数组（来自 ScreenCapture.capture）。
            scale_factor: 放大倍数（>1 可提高小文字的识别率）。

        Returns:
            处理后的 PIL Image（模式 "L"，灰度图），可直接送入 pytesseract。
        """
        # 1. BGRA → 灰度
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)

        # 2. 放大（提高小文字的识别率）
        if scale_factor != 1.0:
            h, w = gray.shape
            gray = cv2.resize(
                gray,
                (int(w * scale_factor), int(h * scale_factor)),
                interpolation=cv2.INTER_CUBIC,
            )

        # 3. 自适应二值化（比全局阈值更好地处理光照不均）
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=2,
        )

        # 4. 降噪（去除孤立噪点）
        denoised = cv2.medianBlur(binary, 3)

        return Image.fromarray(denoised, mode="L")

    @staticmethod
    def preprocess_fast(image: np.ndarray) -> Image.Image:
        """轻量预处理（速度优先，用于高频轮询场景）。

        仅做灰度 + OTSU 二值化，不做缩放。
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(binary, mode="L")
