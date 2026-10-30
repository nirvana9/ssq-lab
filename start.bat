@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo [1/3] 创建 Python 虚拟环境...
  py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
)
echo [2/3] 安装或检查依赖...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (echo 依赖安装失败。请检查 Python 和网络。& pause & exit /b 1)
echo [3/3] 启动 SSQ Lab...
echo 浏览器打开：http://127.0.0.1:8765
start "" http://127.0.0.1:8765
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
pause
