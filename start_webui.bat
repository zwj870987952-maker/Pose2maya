@echo off
chcp 65001 >nul
title Pose2maya - SAM 3D Body & MHR 工作台
echo ========================================================
echo     Pose2maya - 启动 3D 骨架姿态估计 WebUI 工作台
echo ========================================================

if exist "D:\sam-3d-body\venv\Scripts\python.exe" (
    set "PYTHON_EXE=D:\sam-3d-body\venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%~dp0start_webui.py"
pause
