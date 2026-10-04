@echo off
rem Запуск БАСозавр из корня проекта: открывает Unity, сцену и сразу Play Mode.
rem   run.bat                      - Assets/Scenes/SupremeFlat.unity
rem   run.bat Assets/1.unity       - другая сцена
rem   set UNITY=C:\путь\Unity.exe  - если Unity установлена не в стандартное место
chcp 65001 >nul
cd /d "%~dp0"

for /f "tokens=2" %%v in ('findstr /b "m_EditorVersion:" ProjectSettings\ProjectVersion.txt') do set VERSION=%%v
set SCENE=%~1
if "%SCENE%"=="" set SCENE=Assets/Scenes/SupremeFlat.unity
if "%UNITY%"=="" set UNITY=C:\Program Files\Unity\Hub\Editor\%VERSION%\Editor\Unity.exe

if not exist "%UNITY%" (
    echo Unity %VERSION% не найдена. Укажите путь: set UNITY=C:\путь\Unity.exe
    exit /b 1
)

echo Unity: %UNITY%
echo Сцена: %SCENE%
start "" "%UNITY%" -projectPath "%CD%" -executeMethod BasozavrLauncher.Play -scene "%SCENE%"
