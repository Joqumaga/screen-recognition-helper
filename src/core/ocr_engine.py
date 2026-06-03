"""OCR 识别引擎。

基于 Tesseract (pytesseract) 实现文字识别，
支持返回结构化结果（文字内容 + 坐标 + 可信度）。
"""

from __future__ import annotations

import pytesseract
from PIL import Image

from config import TESSERACT_CMD, OCR_CONFIDENCE_MIN, OCR_LANG

# 全局配置 Tesseract 路径
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


class OCRResult:
    """单条 OCR 识别结果。"""

    def __init__(self, text: str, bbox: dict, confidence: int):
        self.text = text
        self.bbox = bbox          # {"left": x, "top": y, "width": w, "height": h}
        self.confidence = confidence

    def center(self) -> tuple[int, int]:
        """获取文字区域的中心点坐标（相对于截图区域的偏移）。"""
        return (
            self.bbox["left"] + self.bbox["width"] // 2,
            self.bbox["top"] + self.bbox["height"] // 2,
        )

    def __repr__(self) -> str:
        return f"OCRResult(text='{self.text}', conf={self.confidence})"


class OCREngine:
    """OCR 识别引擎。

    用法:
        engine = OCREngine()
        results = engine.recognize(pil_image)
        for r in results:
            print(r.text, r.center())
    """

    def __init__(self, conf_min: int = OCR_CONFIDENCE_MIN):
        self._conf_min = conf_min

    def recognize(self, image: Image.Image) -> list[OCRResult]:
        """识别图片中的文字。

        Args:
            image: PIL Image（建议先经 ImageProcessor 预处理）。

        Returns:
            OCRResult 列表，每个包含 text、bbox、confidence。
        """
        data = pytesseract.image_to_data(
            image,
            lang=OCR_LANG,
            output_type=pytesseract.Output.DICT,
            config="--psm 6 --oem 3",  # PSM 6=统一文本块, OEM 3=LSTM+Legacy
        )

        results: list[OCRResult] = []
        n = len(data["text"])

        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue

            try:
                conf = int(data["conf"][i])
            except (ValueError, TypeError):
                conf = 0

            if conf < self._conf_min:
                continue

            results.append(OCRResult(
                text=text,
                bbox={
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                },
                confidence=conf,
            ))

        # 按可信度降序排列
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def recognize_simple(self, image: Image.Image) -> str:
        """简单识别，只返回纯文本字符串（不带坐标）。"""
        return pytesseract.image_to_string(
            image,
            lang=OCR_LANG,
            config="--psm 6 --oem 3",
        ).strip()
