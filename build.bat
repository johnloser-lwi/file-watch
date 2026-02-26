@echo off
setlocal

set OUTPUT_DIR=bin\win
set ENTRY=src\file_watch\__main__.py
set EXE_NAME=file-watch

echo [build] Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [build] Installing PyInstaller...
    pip install pyinstaller -q
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        exit /b 1
    )
)

echo [build] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist "%EXE_NAME%.spec" del /q "%EXE_NAME%.spec"

echo [build] Building executable...
pyinstaller ^
    --onefile ^
    --name "%EXE_NAME%" ^
    --distpath "%OUTPUT_DIR%" ^
    --workpath build ^
    --specpath build ^
    --clean ^
    --noconfirm ^
    "%ENTRY%"

if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

echo.
echo [build] Done.
echo [build] Executable: %OUTPUT_DIR%\%EXE_NAME%.exe
echo [build] Size:
for %%F in ("%OUTPUT_DIR%\%EXE_NAME%.exe") do echo         %%~zF bytes

endlocal
