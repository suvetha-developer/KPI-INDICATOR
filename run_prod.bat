@echo off
echo Starting KPI Dashboard in PRODUCTION mode...
echo Opening dashboard at http://localhost:8080
start http://localhost:8080
echo Press Ctrl+C to stop the server.
python -m waitress --port=8080 dashboard:app
pause
