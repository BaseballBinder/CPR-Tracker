@echo off
echo Starting CPR Tracking System...
echo.

call .venv\Scripts\activate
uvicorn app.main:app --reload

pause
