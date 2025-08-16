@echo off
REM This script starts the backend server

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Start the Flask server
python server.py