@echo off
echo ============================================
echo   Server Performance Tracker Dashboard
echo ============================================
echo.
echo  - Dashboard  : http://localhost:8890
echo  - Collector   : auto-starts (QDDEATAPP01.qdev.net)
echo  - Press Ctrl+C to stop both.
echo.
start http://localhost:8890
python "%~dp0perf_server.py"
pause
