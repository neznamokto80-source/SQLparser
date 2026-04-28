@echo off

chcp 65001 >nul

:: === SETTINGS ===

set "APP_NAME=SQLparser"

:: Name of the virtual environment folder (in the project root)

set "VENV_DIR=..\.venv"

:: Flag: delete virtual environment after build (1 - yes, 0 - no)

set "REMOVE_VENV_AFTER=0"

:: Use spec-file (recommended)

set "SPEC_FILE=SQLparser_hook.spec"

:: =================================

title Compiling Py: %APP_NAME%

echo ========================================

echo    Compiling %APP_NAME% (with venv and spec)

echo ========================================

echo.

 

:: 1. Check/create virtual environment if it doesn't exist

echo [1/7] Checking virtual environment...

if not exist "%VENV_DIR%\Scripts\python.exe" (

    echo Creating virtual environment in folder %VENV_DIR%...

    python -m venv "%VENV_DIR%"

    if errorlevel 1 (

        echo [ERROR] Failed to create venv. Ensure Python is installed and accessible.

        pause

        exit /b 1

    )

    echo [OK] Virtual environment created.

) else (

    echo [OK] Virtual environment already exists.

)

 

:: 2. Activate venv and install dependencies

echo [2/7] Activating venv and installing packages...

call "%VENV_DIR%\Scripts\activate.bat"

if errorlevel 1 (

    echo [ERROR] Error activating venv.

    pause

    exit /b 1

)

 

:: 3. Install necessary packages (PyInstaller + script dependencies)

echo Installing/updating packages:

pip install --upgrade pip >nul 2>&1

pip install pyinstaller sqlglot pandas openpyxl PyQt6 pyinstaller-hooks-contrib >nul 2>&1

if errorlevel 1 (

    echo [ERROR] Package installation failed. Check internet connection.

    pause

    exit /b 1

)

 

:: 4. Clean up old builds and temporary files

echo [3/7] Cleaning up previous builds and temporary files...

if exist build rmdir /s /q build

if exist dist rmdir /s /q dist

if exist __pycache__ rmdir /s /q __pycache__

if exist .pytest_cache rmdir /s /q .pytest_cache

 

:: Clean cache in project subfolders

for /d %%d in (..\core\__pycache__ ..\models\__pycache__ ..\ui\__pycache__ ..\tests\__pycache__) do (

    if exist "%%d" rmdir /s /q "%%d"

)

del /q *.log 2>nul

echo [OK] Cleanup complete.

 

:: 5. Check for spec-file and hooks

echo [4/7] Checking spec-file and hooks...

if not exist "%SPEC_FILE%" (

    echo [ERROR] Spec-file "%SPEC_FILE%" not found.

    echo Check if SQLparser_hook.spec exists in the current folder.

    pause

    exit /b 1

)

echo [OK] Spec-file "%SPEC_FILE%" found.

 

:: 6. Compile with PyInstaller using spec-file

echo [5/7] Compiling to EXE (using %SPEC_FILE%)...

pyinstaller --clean --log-level INFO "%SPEC_FILE%"

if errorlevel 1 (

    echo [ERROR] Compilation error! Check logs above.

    pause

    exit /b 1

)

 

:: 7. Check result and copy

echo [6/7] Checking result...

if exist "dist\%APP_NAME%.exe" (

    echo [OK] Compilation successful!

   

    :: Get file size

    for %%A in ("dist\%APP_NAME%.exe") do set size=%%~zA

    set /a sizeMB=%size% / 1048576

    echo File size: %sizeMB% MB

   

    :: Copy to project root folder

    echo [7/7] Copying to project root...

    copy "dist\%APP_NAME%.exe" .. >nul

    if exist "..\%APP_NAME%.exe" (

        echo [OK] File copied to ..\%APP_NAME%.exe

    ) else (

        echo [ERROR] Failed to copy file.

    )

 

    :: Clean up PyInstaller temp files (but not venv)

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

    echo    DONE! File: ..\%APP_NAME%.exe

    echo ========================================

) else (

    echo [ERROR] Compilation error! File %APP_NAME%.exe not found in dist folder.

    echo Check if spec-file and source code exist.

)

 

:: Deactivate venv (optional)

call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul

 

:: Delete venv if flag is set

if "%REMOVE_VENV_AFTER%"=="1" (

    echo Deleting virtual environment...

    rmdir /s /q "%VENV_DIR%"

    echo [OK] Venv deleted.

)

 

echo.

pause