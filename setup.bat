@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Setting up database...
python scripts/setup_database.py
echo.
echo Setup complete.
pause
