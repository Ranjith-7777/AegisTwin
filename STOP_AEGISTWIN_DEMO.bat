@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\demo\stop_aegistwin_demo.ps1" %*
exit /b %ERRORLEVEL%
