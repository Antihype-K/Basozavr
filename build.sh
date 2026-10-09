#!/usr/bin/env bash
# Сборка SwarmDelivery из корня проекта (Unity в batchmode, без открытия редактора).
#   ./build.sh                          -> Builds/SwarmDelivery/SwarmDelivery.x86_64
#   UNITY=/путь/к/Unity ./build.sh      # если Unity установлена не в стандартное место
# Перед сборкой закройте этот проект в редакторе Unity.
# Нужен модуль Unity Hub "Linux Build Support (Mono)".
set -e
cd "$(dirname "$0")"

VERSION=$(sed -n 's/^m_EditorVersion: //p' ProjectSettings/ProjectVersion.txt)

if [ -z "$UNITY" ]; then
    for p in "$HOME/Unity/Hub/Editor/$VERSION/Editor/Unity" \
             "/opt/unity/Hub/Editor/$VERSION/Editor/Unity"; do
        [ -x "$p" ] && UNITY="$p" && break
    done
fi
if [ -z "$UNITY" ]; then
    echo "Unity $VERSION не найдена. Укажите путь: UNITY=/путь/к/Unity ./build.sh" >&2
    exit 1
fi

mkdir -p Logs
echo "Сборка через $UNITY, лог: Logs/build.log"
"$UNITY" -batchmode -quit -projectPath "$PWD" -executeMethod SwarmDeliveryBuild.BuildLinux -logFile Logs/build.log \
    || { echo "Сборка не удалась, см. Logs/build.log" >&2; exit 1; }

chmod +x Builds/SwarmDelivery/SwarmDelivery.x86_64
echo "Готово. Запуск: ./Builds/SwarmDelivery/SwarmDelivery.x86_64"
