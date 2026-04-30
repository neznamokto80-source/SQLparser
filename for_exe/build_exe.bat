@echo off
chcp 65001 >nul

:: === SETTINGS ===
set "APP_NAME=SQLparser"
set "VENV_DIR=..\.venv"
set "REMOVE_VENV_AFTER=0"
set "SPEC_FILE=SQLparser_hook.spec"

title Compiling %APP_NAME%
echo ========================================
echo    Compiling %APP_NAME%
echo ========================================
echo.

:: 1. Check / create virtual environment
echo [1/6] Checking virtual environment...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment in %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: 2. Activate venv and install dependencies
echo [2/6] Activating venv and installing packages...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Activation failed.
    pause
    exit /b 1
)

echo Installing required packages...
pip install --upgrade pip >nul
pip install pyinstaller sqlglot pandas openpyxl PyQt6 pyinstaller-hooks-contrib >nul
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause
    exit /b 1
)

:: 3. Clean old builds
echo [3/6] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
if exist .pytest_cache rmdir /s /q .pytest_cache
for /d %%d in (..\core\__pycache__ ..\models\__pycache__ ..\ui\__pycache__ ..\tests\__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)
del /q *.log 2>nul
echo [OK] Cleanup complete.

:: 4. Check spec-file
echo [4/6] Checking spec-file...
if not exist "%SPEC_FILE%" (
    echo [ERROR] Spec-file "%SPEC_FILE%" not found.
    pause
    exit /b 1
)
echo [OK] Spec-file found.

:: 5. Compile with PyInstaller
echo [5/6] Compiling to EXE...
pyinstaller --clean --log-level INFO "%SPEC_FILE%"
if errorlevel 1 (
    echo [ERROR] Compilation failed.
    pause
    exit /b 1
)

:: 6. Copy result and final cleanup
echo [6/6] Processing build result...

set "EXE_SOURCE="
if exist "dist\%APP_NAME%.exe" (
    set "EXE_SOURCE=dist\%APP_NAME%.exe"
) else if exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    set "EXE_SOURCE=dist\%APP_NAME%\%APP_NAME%.exe"
)

if not defined EXE_SOURCE (
    echo [ERROR] Cannot find compiled %APP_NAME%.exe in dist.
    echo Check build logs.
    pause
    exit /b 1
)

for %%A in ("%EXE_SOURCE%") do set size=%%~zA
set /a sizeMB=%size% / 1048576
echo File size: %sizeMB% MB

copy "%EXE_SOURCE%" .. >nul
if errorlevel 1 (
    echo [ERROR] Failed to copy EXE to project root.
) else (
    echo [OK] File copied to ..\%APP_NAME%.exe
)

:: Cleanup temporary PyInstaller folders
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
if exist .pytest_cache rmdir /s /q .pytest_cache
for /d %%d in (..\core\__pycache__ ..\models\__pycache__ ..\ui\__pycache__ ..\tests\__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)
del /q *.log 2>nul

echo.
echo ========================================
echo    SUCCESS! ..\%APP_NAME%.exe is ready
echo ========================================

:: Deactivate venv
call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul

:: Optionally remove venv
if "%REMOVE_VENV_AFTER%"=="1" (
    echo Deleting virtual environment...
    rmdir /s /q "%VENV_DIR%"
    echo [OK] Venv deleted.
)

echo.
pause