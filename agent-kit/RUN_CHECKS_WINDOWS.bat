@echo off
setlocal
call "%~dp0RUN_CHECKS_WINDOWS.cmd" %*
exit /b %ERRORLEVEL%
