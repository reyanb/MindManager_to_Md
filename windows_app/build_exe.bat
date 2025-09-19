@echo off
SETLOCAL
REM Build a Windows executable for the Mindmap → Markdown app using PyInstaller

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

cd /d "%PROJECT_ROOT%" || goto :error

python "%SCRIPT_DIR%build_exe.py" %*
if errorlevel 1 goto :error

echo.
echo Build complete: windows_app\dist\MindmapToMarkdown\MindmapToMarkdown.exe
ENDLOCAL
exit /b 0

:error
echo.
echo PyInstaller build failed.
ENDLOCAL
exit /b 1
