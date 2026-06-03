"""全局配置常量。

集中管理所有可调参数，避免魔法数字散布在各模块中。
"""

# ── 扫描配置 ──────────────────────────────────
SCAN_INTERVAL_MS = 200          # 扫描间隔（毫秒）
CLICK_DELAY_MS = 50             # 移动后到点击的延迟
CLICK_AREA_RADIUS = 5           # 点击区域默认半径（像素）

# ── OCR 配置 ──────────────────────────────────
OCR_CONFIDENCE_MIN = 30         # OCR 最低可信度（0-100，游戏艺术字体可信度偏低）
IMAGE_SCALE_FACTOR = 2.0        # OCR 前图像放大倍数
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Tesseract 可执行文件路径
OCR_LANG = "chi_sim+eng"        # 识别语言（中文简体 + 英文）

# ── UI 配置 ───────────────────────────────────
WINDOW_TITLE = "屏幕识别点击助手"
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 600
WINDOW_DEFAULT_WIDTH = 900
WINDOW_DEFAULT_HEIGHT = 650

# UI 配色（淡蓝主题）
COLOR_PRIMARY = "#87CEEB"       # 主色 天蓝
COLOR_BG = "#F0F8FF"            # 背景 爱丽丝蓝
COLOR_ACCENT = "#4682B4"        # 强调 钢蓝
COLOR_TEXT = "#2C3E50"          # 主文字 深石板
COLOR_TEXT_SECONDARY = "#7F8C8D"  # 次要文字 灰
COLOR_SUCCESS = "#27AE60"       # 成功 绿
COLOR_WARNING = "#E67E22"       # 警告 橙
COLOR_ERROR = "#E74C3C"         # 错误 红
COLOR_BORDER = "#BDC3C7"        # 边框 浅灰
COLOR_DISABLED = "#D5D8DC"      # 禁用 雾灰

# ── 日志配置 ──────────────────────────────────
MAX_LOG_ENTRIES = 500           # 日志面板最大行数

# ── 文件路径 ──────────────────────────────────
CONFIG_FILE = "config.json"     # 区域和目标配置保存路径
