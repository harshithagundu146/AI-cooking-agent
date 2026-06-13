@echo off
echo Starting AI Cooking Agent...
echo.

cd /d "%~dp0"

start cmd /k "cd backend && python app.py"

echo Waiting for backend to start...
timeout /t 3 >nul

echo Opening frontend in your browser...
start http://localhost:5000

echo.
echo The AI Cooking Agent is now running!
echo Do not close the black terminal window while using the app.
