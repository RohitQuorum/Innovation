@echo off
echo ============================================
echo   Performance Dashboard - Server 2
echo ============================================
echo.
echo  Local Access  : http://localhost:8891
echo  Network Access: http://10.11.33.183:8891
echo.
echo  Server: QDTQENWEB02.qdev.net
echo  Press Ctrl+C to stop.
echo.
start http://localhost:8891
python "%~dp0perf_server2.py"
pause
