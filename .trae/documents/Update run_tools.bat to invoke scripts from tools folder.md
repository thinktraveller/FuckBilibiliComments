## Objective
Align run_tools.bat to call the three Python tools located in c:\Users\joyjo\Desktop\Done\FuckBilibiliComments\tools instead of the current directory.

## Changes
- Define TOOLS_DIR as the absolute path: `set "TOOLS_DIR=%~dp0tools"`.
- Keep UTF-8 console and Python launcher detection (`py` → fallback `python`).
- Validate the tools directory and each script before invocation; show a clear error when missing.
- Update menu run targets to use `"%TOOLS_DIR%\<script>.py"`.

## Proposed bat content
@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PYEXE=py"
where py >nul 2>&1 || set "PYEXE=python"
set "TOOLS_DIR=%~dp0tools"

if not exist "%TOOLS_DIR%" (
  echo Tools folder not found: "%TOOLS_DIR%"
  pause
  exit /b 1
)

:menu
echo =====================================
echo Select a tool to run:
echo   1) Generate nested comments tail images
echo   2) CSV deduplication tool
echo   3) Fine-grained comment time statistics
echo   0) Exit
echo =====================================
set "choice="
set /p choice=Enter your choice [0-3]: 

if "%choice%"=="1" goto run1
if "%choice%"=="2" goto run2
if "%choice%"=="3" goto run3
if "%choice%"=="0" goto end

echo Invalid selection.
pause
goto menu

:run1
if not exist "%TOOLS_DIR%\楼中楼拖尾文件生成器.py" (
  echo Script not found: "%TOOLS_DIR%\楼中楼拖尾文件生成器.py"
  pause
  goto menu
)
%PYEXE% "%TOOLS_DIR%\楼中楼拖尾文件生成器.py"
echo.
echo Finished tool 1.
pause
goto menu

:run2
if not exist "%TOOLS_DIR%\评论CSV去重工具.py" (
  echo Script not found: "%TOOLS_DIR%\评论CSV去重工具.py"
  pause
  goto menu
)
%PYEXE% "%TOOLS_DIR%\评论CSV去重工具.py"
echo.
echo Finished tool 2.
pause
goto menu

:run3
if not exist "%TOOLS_DIR%\评论时间精细统计工具.py" (
  echo Script not found: "%TOOLS_DIR%\评论时间精细统计工具.py"
  pause
  goto menu
)
%PYEXE% "%TOOLS_DIR%\评论时间精细统计工具.py"
echo.
echo Finished tool 3.
pause
goto menu

:end
endlocal
exit /b 0

## Validation
- Confirm `tools` folder exists and contains three scripts (seen in directory listing).
- Run each menu option to ensure the correct script launches; verify UTF-8 output.
- If any script is missing, the bat shows an error and returns to the menu without crashing.