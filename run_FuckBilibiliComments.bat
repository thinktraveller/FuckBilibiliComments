@echo off
REM Launch FuckBilibiliComments.py with UTF-8 console
chcp 65001 >nul
cd /d "%~dp0"
python FuckBilibiliComments.py
pause