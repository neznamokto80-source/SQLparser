@echo off
chcp 65001 >nul

:: === НАСТРОЙКИ ===
set "APP_NAME=SQLparser"
:: Имя папки виртуального окружения (в корне проекта)
set "VENV_DIR=..\.venv"
:: Флаг: удалить виртуальное окружение после сборки (1 - да, 0 - нет)
set "REMOVE_VENV_AFTER=0"
:: Использовать spec-файл (рекомендуется)
set "SPEC_FILE=SQLparser_hook.spec"
:: =================================

title Компиляция Py: %APP_NAME%

echo ========================================
echo    Компиляция %APP_NAME% (с venv и spec)
echo ========================================
echo.

:: 1. Создание виртуального окружения, если его нет
echo [1/7] Проверка виртуального окружения...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Создаю виртуальное окружение в папке %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [❌] Не удалось создать venv. Убедитесь, что Python установлен и доступен.
        pause
        exit /b 1
    )
    echo [✅] Виртуальное окружение создано.
) else (
    echo [✅] Виртуальное окружение уже существует.
)

:: 2. Активация venv и установка зависимостей
echo [2/7] Активация venv и установка пакетов...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [❌] Ошибка активации venv.
    pause
    exit /b 1
)

:: 3. Установка необходимых пакетов (PyInstaller + зависимости скрипта)
echo Устанавливаю/обновляю пакеты:
pip install --upgrade pip
pip install pyinstaller sqlglot pandas openpyxl PyQt6 pyinstaller-hooks-contrib

:: 4. Очистка старых сборок и временных файлов
echo [3/7] Очистка предыдущих сборок и временных файлов...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
if exist .pytest_cache rmdir /s /q .pytest_cache
for /d %%d in (..\core\__pycache__ ..\models\__pycache__ ..\ui\__pycache__ ..\tests\__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)
del /q *.log 2>nul
echo [✅] Готово

:: 5. Проверка наличия spec-файла и хуков
echo [4/7] Проверка spec-файла и хуков...
if not exist "%SPEC_FILE%" (
    echo [❌] Spec-файл "%SPEC_FILE%" не найден. Создайте его или используйте стандартную сборку.
    pause
    exit /b 1
)
echo [✅] Spec-файл "%SPEC_FILE%" найден.

:: 6. Компиляция с помощью PyInstaller через spec-файл
echo [5/7] Компиляция в EXE (используется %SPEC_FILE%)...
pyinstaller --clean --log-level INFO "%SPEC_FILE%"
if errorlevel 1 (
    echo [❌] Ошибка компиляции! Проверьте логи.
    pause
    exit /b 1
)

:: 7. Проверка результата и копирование
echo [6/7] Проверка результата...
if exist "dist\%APP_NAME%.exe" (
    echo [✅] Компиляция успешна!

    :: Получение размера файла
    for %%A in ("dist\%APP_NAME%.exe") do set size=%%~zA
    set /a sizeMB=%size% / 1048576
    echo Размер файла: %sizeMB% МБ

    :: Копирование в папку с исходником (корень проекта)
    echo [7/7] Копирование в корень проекта...
    copy "dist\%APP_NAME%.exe" .. >nul
    echo [✅] Готово

    :: Очистка временных файлов PyInstaller (но не venv)
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
    echo    ГОТОВО! Файл: ..\%APP_NAME%.exe
    echo ========================================
) else (
    echo [❌] Ошибка компиляции! Файл %APP_NAME%.exe не найден.
    echo Проверьте, существует ли spec-файл и исходный код.
)

:: Деактивация venv (необязательно)
call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul

:: Удаление venv, если установлен флаг
if "%REMOVE_VENV_AFTER%"=="1" (
    echo Удаляю виртуальное окружение...
    rmdir /s /q "%VENV_DIR%"
    echo [✅] Venv удалён.
)

echo.
pause