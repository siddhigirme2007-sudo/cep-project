@echo off
echo =========================================
echo       Starting MediExplain AI...
echo =========================================
echo.
echo 1. Starting the Python Backend Server...
start "MediExplain Backend" cmd /c "python app.py"

echo 2. Waiting for the server to load...
timeout /t 3 /nobreak > NUL

echo 3. Opening the Frontend in your web browser...
start http://127.0.0.1:5000

echo.
echo The application is now running! 
echo Keep the black "MediExplain Backend" window open while you use the app.
echo You can close this window now.
pause
