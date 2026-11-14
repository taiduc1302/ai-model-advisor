@echo off
setlocal
pushd "%~dp0" || exit /b 2
where py >nul 2>nul
if not errorlevel 1 (
    py -3 tools\run_local.py %*
) else (
    python tools\run_local.py %*
)
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
