@echo off
REM FailState Backend Startup Script for Windows

echo 🚀 Starting FailState Backend...

REM Check if virtual environment exists
if not exist "venv\" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo 📥 Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  Warning: .env file not found!
    echo 📝 Please copy .env.example to .env and configure it:
    echo    copy .env.example .env
    echo.
    set /p continue="Do you want to create .env now? (y/n) "
    if /i "%continue%"=="y" (
        copy .env.example .env
        echo ✅ Created .env file. Please edit it with your credentials.
        pause
        exit /b 0
    ) else (
        echo ❌ Cannot start without .env file. Exiting.
        pause
        exit /b 1
    )
)

REM Start the server
echo ✨ Starting FastAPI server...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

