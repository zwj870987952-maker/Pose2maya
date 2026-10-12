@echo off
chcp 65001 >nul
title Pose2maya - 全自动自检启动中...
echo ========================================================
echo     Pose2maya - SAM 3D Body & MHR 姿态估计工作台
echo     [全自动启动引擎: 依赖自检 + 权重自查 + 自动补全]
echo ========================================================

:: 1. 查找或准备 Python 解释器
set "PYTHON_EXE="

if exist "D:\sam-3d-body\venv\Scripts\python.exe" (
    set "PYTHON_EXE=D:\sam-3d-body\venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    set "SYS_PY="
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "SYS_PY=python"
    ) else (
        where py >nul 2>nul
        if %errorlevel% equ 0 (
            set "SYS_PY=py -3"
        )
    )
    if not "%SYS_PY%"=="" (
        echo [提示] 首次运行，正在为您创建隔离的 Python 虚拟环境 (venv)...
        %SYS_PY% -m venv "%~dp0venv"
        if exist "%~dp0venv\Scripts\python.exe" (
            set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
        ) else (
            set "PYTHON_EXE=%SYS_PY%"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [错误] 未在系统中检测到 Python 3 环境，请先安装 Python 3.10-3.12 并添加到 PATH。
    pause
    exit /b 1
)

:: 2. 执行全自动自检、依赖自动安装、模型自动下载与工作台启动
"%PYTHON_EXE%" "%~dp0start_webui.py"
if %errorlevel% neq 0 (
    echo.
    echo [提示] 服务已停止运行。
    pause
)
