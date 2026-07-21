@echo off
cd /d "%~dp0"
start "AI Travel Backend" cmd /k run-backend.bat
start "AI Travel Frontend" cmd /k run-frontend.bat
echo Frontend: http://127.0.0.1:5173/
echo Backend:  http://127.0.0.1:8000/health
pause
