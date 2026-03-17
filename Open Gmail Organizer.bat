@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
	py -3 launch_web.py
) else (
	python launch_web.py
)

pause
