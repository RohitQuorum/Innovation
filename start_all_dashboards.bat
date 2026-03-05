@echo off
echo ============================================
echo   Starting All Performance Dashboards
echo ============================================
echo.
echo Starting 3 servers...
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Start all servers in separate minimized windows that stay open
start "Server 1 - QDDEATAPP01" /MIN cmd /k "cd /d "%~dp0" && python perf_server.py"
timeout /t 3 /nobreak >nul
echo [1/3] Started QDDEATAPP01 (Port 8890)

start "Server 2 - QDTQENWEB02" /MIN cmd /k "cd /d "%~dp0" && python perf_server2.py"
timeout /t 3 /nobreak >nul
echo [2/3] Started QDTQENWEB02 (Port 8891)

start "Server 3 - QDTQENMT02" /MIN cmd /k "cd /d "%~dp0" && python perf_server3.py"
timeout /t 3 /nobreak >nul
echo [3/3] Started QDTQENMT02 (Port 8892)

echo.
echo ============================================
echo   All Dashboards Started!
echo ============================================
echo.
echo  Server 1: http://localhost:8890
echo  Server 2: http://localhost:8891
echo  Server 3: http://localhost:8892
echo.
echo  Opening Server Hub...
echo.

REM Wait a bit for servers to start
timeout /t 3 /nobreak >nul

REM Open the hub
start "" "%~dp0hub.html"

echo.
echo Hub opened! Click any server card to view its dashboard.
echo.
echo To stop all servers: Close this window or press Ctrl+C
echo.
pause
