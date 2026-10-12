@echo off
chcp 65001 >nul
title Pose2maya - 模型权重一键下载
echo ========================================================
echo     Pose2maya - 自动下载 SAM 3D Body 与 MHR 权重
echo ========================================================

if exist "D:\sam-3d-body\venv\Scripts\python.exe" (
    set "PYTHON_EXE=D:\sam-3d-body\venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%~dp0download_models.py"
pause
