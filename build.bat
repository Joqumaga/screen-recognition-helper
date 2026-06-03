@echo off
chcp 65001 >nul
title 打包 屏幕识别点击助手

echo ============================================
echo  屏幕识别点击助手 — PyInstaller 打包
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 检查 PyInstaller
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [安装] PyInstaller 未安装，正在安装...
    pip install pyinstaller
)

echo [1/3] 清理旧的打包文件...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
del /f /q "屏幕识别点击助手.spec" 2>nul

echo [2/3] 正在打包（需要 2-5 分钟，请耐心等待）...
python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name "屏幕识别点击助手" ^
    --paths src ^
    --collect-all numpy ^
    --collect-all cv2 ^
    --collect-all PIL ^
    --collect-all mss ^
    --hidden-import pytesseract ^
    --hidden-import pyautogui ^
    --hidden-import customtkinter ^
    src/main.py

if %errorlevel% neq 0 (
    echo [错误] 打包失败，请检查上方错误信息。
    pause
    exit /b 1
)

echo [3/3] 打包完成！
echo.
echo ============================================
echo  输出文件：dist\屏幕识别点击助手.exe
for %%i in ("dist\屏幕识别点击助手.exe") do echo  大小：%%~zi 字节 (%%~zi / 1048576 MB)
echo ============================================
echo.
echo 注意事项：
echo  1. 运行 exe 前需要先安装 Tesseract OCR
echo  2. 安装命令：winget install "UB-Mannheim.TesseractOCR"
echo  3. 或从 https://github.com/UB-Mannheim/tesseract/wiki 下载
echo.
echo  按任意键退出...
pause >nul
