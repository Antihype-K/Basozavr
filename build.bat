@echo off
rem Сборка SwarmDelivery под Windows из корня проекта (Unity в batchmode, без открытия редактора).
rem   build.bat                          -> Builds\SwarmDeliveryWin\SwarmDelivery.exe
rem   set UNITY=D:\Unity\Editor\Unity.exe  (если Unity установлена не в стандартное место)
rem Перед сборкой закройте этот проект в редакторе Unity.
chcp 65001 >nul
cd /d "%~dp0"

for /f "tokens=2" %%v in ('findstr /b "m_EditorVersion:" ProjectSettings\ProjectVersion.txt') do set VERSION=%%v
if "%UNITY%"=="" set UNITY=C:\Program Files\Unity\Hub\Editor\%VERSION%\Editor\Unity.exe

if not exist "%UNITY%" (
    echo Unity %VERSION% не найдена. Укажите путь: set UNITY=C:\путь\Unity.exe
    exit /b 1
)

if not exist Logs mkdir Logs
echo Сборка через %UNITY%, лог: Logs\build.log
"%UNITY%" -batchmode -quit -projectPath "%CD%" -executeMethod SwarmDeliveryBuild.BuildWindows -logFile Logs\build.log
if errorlevel 1 (
    echo Сборка не удалась, см. Logs\build.log
    exit /b 1
)

echo Готово. Запуск: Builds\SwarmDeliveryWin\SwarmDelivery.exe
