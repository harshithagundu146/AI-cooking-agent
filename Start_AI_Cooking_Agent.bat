@echo off
echo Starting AI Cooking Agent Backend Server...
start cmd /k "cd backend && python app.py"

echo Starting AI Cooking Agent Frontend Server...
start cmd /k "cd frontend && python -m http.server 8000"

echo Opening Application in your default browser...
timeout /t 3 /nobreak > NUL
start http://localhost:8000

echo Application successfully launched!
