# CLAUDE.md — 项目工作指引

## 项目概述

这是一个 Windows 桌面游戏辅助工具，功能是：框选屏幕区域 → OCR 识别文字 → 匹配目标 → 自动鼠标点击。

## 标准文件路径速查

| 文件 | 路径 | 说明 |
|------|------|------|
| 产品需求文档 | [docs/requirements.md](docs/requirements.md) | 功能需求和用户场景 |
| 技术规格说明 | [docs/tech-spec.md](docs/tech-spec.md) | 技术选型、依赖、版本要求 |
| UI 设计编码规范 | [docs/design-standards.md](docs/design-standards.md) | 命名规范、UI 配色、代码风格 |
| 分阶段执行计划 | [docs/execution-plan.md](docs/execution-plan.md) | 7 阶段开发路线图 |
| 软件架构说明 | [docs/architecture.md](docs/architecture.md) | 模块划分、数据流、类图 |
| 开发日志目录 | [dev-logs/](dev-logs/) | 按 YYYY-MM-DD.md 格式存放 |

## 开发工作约定

### 每次开发会话开始时
1. 阅读 [docs/execution-plan.md](docs/execution-plan.md) 了解当前阶段和进度
2. 创建当日日志文件 `dev-logs/YYYY-MM-DD.md`（如果不存在）
3. 阅读当日日志，了解上次完成的工作和待办事项

### 每次开发会话结束前
1. 更新 `dev-logs/YYYY-MM-DD.md`，记录：
   - ✅ 完成事项
   - 📋 待办事项
   - ⚠️ 遇到的问题
   - 📝 备注
2. 如果有重要决策变更，同步更新 `docs/` 下对应文档

### 编码规范
- 详见 [docs/design-standards.md](docs/design-standards.md)
- 关键原则：UI 层不写业务逻辑，核心逻辑不直接操作 UI 控件
- 每个模块顶部必须有 docstring
- 关键函数用中文注释说明意图

### 开发原则
- 一次只做一个阶段，当前阶段验证通过后再进入下一阶段
- 先跑通核心链路，再优化体验
- 多测试，保持代码随时可运行

## 当前开发状态

- **当前状态**：全部 7 阶段 ✅ 已完成，后续进行了多轮优化迭代
- **最近改进**：
  1. ✅ 中文简体 OCR 支持（`chi_sim+eng`，tessdata_fast 模型）
  2. ✅ mss 线程安全问题修复（`threading.local()` 延迟创建）
  3. ✅ 监控异常分步捕获 + 去重（5 步独立 try/except，30s 去重窗口）
  4. ✅ 删除按钮 exe 渲染修复（emoji → 纯文本，避免打包后字体缺失）
  5. ✅ 浮动窗模式（监控启动自动最小化，恢复停止自动还原）

## 已知问题 & 打包注意事项

- **exe 打包后特殊字符问题**：PyInstaller 打包的 tkinter 应用无法渲染 emoji 和丁巴特符号（U+2715 等）。所有按钮文字必须使用纯 ASCII 文本或标准 CJK 字符。
- **Tesseract 语言包**：中文识别需要 `chi_sim.traineddata` 放在 Tesseract 的 `tessdata` 目录下。
- **构建命令**：`python -m PyInstaller --onefile --noconsole --name "屏幕识别点击助手" --paths src --hidden-import pytesseract --hidden-import customtkinter src/main.py`（Windows 下在 bash shell 中运行，不能用 build.bat 的 `^` 续行符）
