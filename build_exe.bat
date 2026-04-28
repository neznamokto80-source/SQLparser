@echo off
chcp 65001 >nul

REM ============================================
REM CONFIGURATION - Укажите имя основного Python файла
REM ============================================
set "MAIN_PY_FILE=app.py"
set "OUTPUT_EXE_NAME=SQLMetadataParser.exe"

REM ============================================
echo.
echo ============================================
echo Building SQL Metadata Parser to EXE file
echo ============================================
echo Main Python file: %MAIN_PY_FILE%
echo Output EXE name:  %OUTPUT_EXE_NAME%
echo ============================================
echo.

REM Check if main file exists
if not exist "%MAIN_PY_FILE%" (
    echo ERROR: File "%MAIN_PY_FILE%" not found!
    echo Please check the MAIN_PY_FILE variable at the beginning of this script.
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...
python -c "import sqlglot" >nul 2>&1 && echo   [OK] sqlglot || echo   [FAIL] sqlglot
python -c "import pandas" >nul 2>&1 && echo   [OK] pandas || echo   [FAIL] pandas
python -c "import openpyxl" >nul 2>&1 && echo   [OK] openpyxl || echo   [FAIL] openpyxl
python -c "import networkx" >nul 2>&1 && echo   [OK] networkx || echo   [FAIL] networkx
python -c "import matplotlib" >nul 2>&1 && echo   [OK] matplotlib || echo   [FAIL] matplotlib
python -c "import PyQt6" >nul 2>&1 && echo   [OK] PyQt6 || echo   [FAIL] PyQt6

echo.
echo [2/3] Building EXE file...
echo This may take several minutes...

REM PyInstaller build command
python -m pyinstaller --onefile ^
  --windowed ^
  --name "%OUTPUT_EXE_NAME%" ^
  --clean ^
  --noconfirm ^
  --distpath "dist" ^
  --workpath "build_temp" ^
  --hidden-import sqlglot ^
  --hidden-import pandas ^
  --hidden-import pandas._libs.tslibs.np_datetime ^
  --hidden-import pandas._libs.tslibs.nattype ^
  --hidden-import pandas._libs.tslibs.base ^
  --hidden-import openpyxl ^
  --hidden-import networkx ^
  --hidden-import matplotlib ^
  --hidden-import matplotlib.backends.backend_qtagg ^
  --hidden-import PyQt6 ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtGui ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import numpy ^
  --hidden-import sys ^
  --hidden-import os ^
  --hidden-import importlib ^
  --hidden-import importlib.util ^
  --hidden-import subprocess ^
  --hidden-import site ^
  --hidden-import re ^
  --hidden-import json ^
  --hidden-import typing ^
  --hidden-import collections ^
  --hidden-import itertools ^
  --hidden-import datetime ^
  --hidden-import pathlib ^
  --hidden-import io ^
  --hidden-import warnings ^
  --hidden-import traceback ^
  "%MAIN_PY_FILE%"

echo.
echo [3/3] Checking result...
if exist "dist\%OUTPUT_EXE_NAME%" (
    echo [SUCCESS] BUILD COMPLETED SUCCESSFULLY!
    echo.
    echo Result: dist\%OUTPUT_EXE_NAME%
    echo.
    
    REM Create README file
    echo Creating README.txt...
    (
        echo SQL Metadata Parser v4.0
        echo.
        echo INSTRUCTIONS:
        echo.
        echo 1. Run %OUTPUT_EXE_NAME%
        echo 2. Load SQL files or paste SQL queries
        echo 3. Analyze column dependencies and lineage
        echo 4. Export results to Excel
        echo.
        echo System requirements:
        echo - Windows 7/8/10/11
        echo - 2 GB RAM
        echo - 100 MB free space
        echo.
        echo Note: Antivirus may request permission on first run.
    ) > "dist\README.txt"
    
    echo [OK] README.txt created in dist folder
) else (
    echo [ERROR] EXE file not created!
    echo Check PyInstaller output for errors.
)

echo.
echo Cleaning temporary files...
if exist "build_temp" rmdir /s /q "build_temp" 2>nul
if exist "build" rmdir /s /q "build" 2>nul
if exist "%OUTPUT_EXE_NAME%.spec" del "%OUTPUT_EXE_NAME%.spec" 2>nul
if exist "__pycache__" rmdir /s /q "__pycache__" 2>nul
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
if exist "*.log" del "*.log" 2>nul

echo.
echo ============================================
echo Process completed. Press any key to exit...
pause >nul