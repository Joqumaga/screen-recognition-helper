"""目标文字匹配模块。

在 OCR 识别结果中查找指定的目标文字，
返回匹配到的位置和可信度信息。

支持两种匹配模式：
- 精确匹配：OCR 文字必须与目标文字完全相同
- 包含匹配：OCR 文字中包含目标文字即算匹配
"""

from __future__ import annotations

from core.ocr_engine import OCRResult

# 匹配模式常量
MATCH_EXACT = "exact"   # 精确匹配
MATCH_FUZZY = "fuzzy"   # 包含匹配


class MatchResult:
    """单条匹配结果。"""

    def __init__(
        self,
        target: str,
        ocr_result: OCRResult,
        region_name: str = "",
    ):
        self.target = target            # 匹配到的目标文字
        self.ocr_result = ocr_result    # 对应的 OCR 识别结果
        self.region_name = region_name  # 来源区域名称

    @property
    def center(self) -> tuple[int, int]:
        """获取匹配文字的中心点坐标（相对于截图区域的偏移）。"""
        return self.ocr_result.center()

    @property
    def confidence(self) -> int:
        return self.ocr_result.confidence

    def __repr__(self) -> str:
        return (
            f"MatchResult(target='{self.target}', "
            f"text='{self.ocr_result.text}', "
            f"conf={self.ocr_result.confidence})"
        )


class TargetMatcher:
    """目标匹配器。

    用法:
        matcher = TargetMatcher()
        matches = matcher.match(ocr_results, ["HP", "MP"])
        for m in matches:
            print(m.center, m.confidence)
    """

    @staticmethod
    def match(
        ocr_results: list[OCRResult],
        targets: list[str],
        mode: str = MATCH_EXACT,
    ) -> list[MatchResult]:
        """在 OCR 结果中查找目标文字。

        Args:
            ocr_results: OCR 识别结果列表。
            targets: 要匹配的目标文字列表（不区分大小写）。
            mode: 匹配模式，MATCH_EXACT 或 MATCH_FUZZY。

        Returns:
            MatchResult 列表，优先返回可信度高的匹配。
        """
        if not ocr_results or not targets:
            return []

        # 统一为小写做不区分大小写匹配
        targets_lower = [t.lower() for t in targets]

        matched: list[MatchResult] = []
        seen_targets: set[str] = set()  # 已匹配到的目标（去重）

        for result in ocr_results:
            text_lower = result.text.lower()

            for target, target_lower in zip(targets, targets_lower):
                # 去重：每个目标只匹配一次（取可信度最高的那个）
                if target in seen_targets:
                    continue

                if mode == MATCH_EXACT:
                    if text_lower == target_lower:
                        matched.append(MatchResult(
                            target=target,
                            ocr_result=result,
                        ))
                        seen_targets.add(target)
                        break  # 一个 OCR 结果只匹配一条目标
                else:  # MATCH_FUZZY
                    if target_lower in text_lower:
                        matched.append(MatchResult(
                            target=target,
                            ocr_result=result,
                        ))
                        seen_targets.add(target)
                        break

        # 按可信度降序排列
        matched.sort(key=lambda m: m.confidence, reverse=True)
        return matched
