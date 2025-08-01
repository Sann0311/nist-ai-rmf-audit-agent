@echo off
REM NIST AI RMF Audit Agent Startup Script for Windows

echo 🔍 Starting NIST AI RMF Audit Agent
echo ==================================

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker is not running. Please start Docker first.
    pause
    exit /b 1
)

REM Check if Ollama is accessible
echo 🔍 Checking Ollama availability...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Warning: Ollama not accessible at localhost:11434
    echo    Please ensure Ollama is running with: ollama serve
    echo    And pull the required model: ollama pull llama3.2:3b
    echo.
    echo    Continuing anyway - you can start Ollama later...
) else (
    echo ✅ Ollama is accessible
)

REM Navigate to the correct directory
cd /d "%~dp0\agent_skeleton"

REM Build and start all services
echo.
echo 🚀 Building and starting services...
echo    - Agent Service (Port 8000)
echo    - Backend API (Port 8001)
echo    - Frontend UI (Port 8501)
echo.

docker compose up --build

echo.
echo 🎉 NIST AI RMF Audit Agent is ready!
echo.
echo 📱 Access the application:
echo    Frontend: http://localhost:8501
echo    Backend API: http://localhost:8001
echo    API Docs: http://localhost:8001/docs
echo.
echo 🛑 To stop the services, press Ctrl+C

pause
