@echo off
rem Запуск миссии доставки груза роем в RSMA. Работает из любой папки:
rem   C:\путь\к\проекту\rsma.bat                       двойной щелчок или из любой консоли
rem   C:\путь\к\проекту\rsma.bat --speed 6 --height 15  с параметрами (все: rsma.bat --help)
rem   C:\путь\к\проекту\rsma.bat --build               собрать RSMA-приложение (нужна Unity, один раз)
rem При первом запуске создает окружение Python (Python\.venv) и ставит зависимости.
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "VENV=%ROOT%Python\.venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%VENV%\rsma_ok" (
    echo Первый запуск: готовлю Python-окружение в %VENV% ...
    if not exist "%PY%" (
        py -3 -m venv "%VENV%" 2>nul || python -m venv "%VENV%"
    )
    if not exist "%PY%" (
        echo Не найден Python 3.10+. Установите его с https://www.python.org/downloads/
        echo и при установке отметьте "Add python.exe to PATH". Затем запустите rsma.bat снова.
        if "%~1"=="" pause
        exit /b 1
    )
    "%PY%" -m pip install --disable-pip-version-check -q -r "%ROOT%Python\requirements.txt"
    if errorlevel 1 (
        echo Не удалось установить зависимости Python, см. сообщения выше.
        if "%~1"=="" pause
        exit /b 1
    )
    echo ok> "%VENV%\rsma_ok"
)

"%PY%" "%ROOT%Python\run.py" %*
set "CODE=%ERRORLEVEL%"
rem Запуск двойным щелчком: не закрывать окно сразу
if "%~1"=="" pause
exit /b %CODE%
