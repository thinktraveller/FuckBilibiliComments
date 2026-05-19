@echo off
chcp 65001 > nul
echo ============================================================
echo  BilibiliCommentCrawler ^| PyInstaller onedir build
echo ============================================================
echo.

:: 清理旧产物
if exist dist\BilibiliCommentCrawler (
    echo [1/4] 清理旧构建产物...
    rmdir /s /q dist\BilibiliCommentCrawler
)
if exist build\BilibiliCommentCrawler (
    rmdir /s /q build\BilibiliCommentCrawler
)

echo [2/4] 运行 PyInstaller...
pyinstaller BilibiliCommentCrawler.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller 构建失败，请检查上方错误信息。
    pause
    exit /b 1
)

echo.
echo [3/4] 打包为 ZIP（用于 GitHub Release）...
set ZIP_NAME=BilibiliCommentCrawler-win64.zip
if exist %ZIP_NAME% del %ZIP_NAME%
powershell -Command "Compress-Archive -Path 'dist\BilibiliCommentCrawler' -DestinationPath '%ZIP_NAME%' -Force"
if errorlevel 1 (
    echo [WARN] ZIP 打包失败，但 dist\ 下的文件夹可直接使用。
) else (
    echo        生成: %ZIP_NAME%
)

echo.
echo [4/4] 完成！
echo.
echo   可执行文件：dist\BilibiliCommentCrawler\BilibiliCommentCrawler.exe
echo   发布压缩包：%ZIP_NAME%
echo.
echo   运行测试：双击 dist\BilibiliCommentCrawler\BilibiliCommentCrawler.exe
echo.
pause
