@echo off
chcp 65001 >nul
title 速卖通广告管理系统 — 开机自启安装
cd /d "%~dp0.."

echo ╔══════════════════════════════════════════════╗
echo ║    速卖通广告管理系统 — 开机自启安装          ║
echo ╚══════════════════════════════════════════════╝
echo.
echo 此脚本将安装为"开机自动启动"任务。
echo 电脑每次开机后，系统会自动在后台启动本应用。
echo.

:: ── 检查 Python ──
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: ── 检查依赖 ──
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖...
    pip install -r requirements.txt
    playwright install chromium
)

:: ── 获取绝对路径 ──
set "ROOT_DIR=%CD%"
set "PYTHON_PATH=python"

:: ── 先停止已有任务 ──
schtasks /query /tn "AdManager" >nul 2>&1
if not errorlevel 1 (
    echo [信息] 检测到已有任务，正在删除旧任务...
    schtasks /end /tn "AdManager" >nul 2>&1
    schtasks /delete /tn "AdManager" /f >nul 2>&1
)

:: ── 创建计划任务（用户登录时启动） ──
schtasks /create /tn "AdManager" ^
    /tr "cmd /c cd /d \"%ROOT_DIR%\" && %PYTHON_PATH% scripts\start.py" ^
    /sc onlogon ^
    /ru "%USERNAME%" ^
    /f ^
    /v1

if errorlevel 1 (
    echo [错误] 安装失败，请以管理员身份运行此脚本。
    echo        右键点击 install-service.bat → 以管理员身份运行
    pause
    exit /b 1
)

echo.
echo [成功] 已安装开机自启任务！
echo.
echo   - 任务名称: AdManager
echo   - 工作目录: %ROOT_DIR%
echo   - 触发时机: 每次登录 Windows 时自动启动
echo.
echo ── 常用操作 ──
echo   启动:    schtasks /run /tn "AdManager"
echo   停止:    python scripts\start.py --stop
echo   查看日志: 打开 logs\app.log
echo   卸载:    schtasks /delete /tn "AdManager" /f
echo.
echo ── 快速启动当前会话 ──
echo   你也可以现在手动启动:
echo   python scripts\start.py
echo.
pause
