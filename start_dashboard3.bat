@echo off
echo ============================================
echo   Performance Dashboard - Server 3
echo ============================================
echo.
echo  Local Access  : http://localhost:8892
echo  Network Access: http://10.11.33.183:8892
echo.
echo  Server: QDTQENMT02.qdev.net
echo  Press Ctrl+C to stop.
echo.
start http://localhost:8892
python "%~dp0perf_server3.py"
pause
