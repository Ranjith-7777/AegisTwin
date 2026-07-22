@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\demo\start_aegistwin_demo.ps1" %*
exit /b %ERRORLEVEL%
