#!/usr/bin/env bash
# Запуск БАСозавр из корня проекта: открывает Unity, сцену и сразу Play Mode.
#   ./run.sh                              # Assets/Scenes/SupremeFlat.unity
#   ./run.sh Assets/1.unity               # другая сцена
#   UNITY=/путь/к/Unity ./run.sh          # если Unity установлена не в стандартное место
set -e
cd "$(dirname "$0")"

VERSION=$(sed -n 's/^m_EditorVersion: //p' ProjectSettings/ProjectVersion.txt)
SCENE=${1:-Assets/Scenes/SupremeFlat.unity}

if [ -z "$UNITY" ]; then
    for p in "$HOME/Unity/Hub/Editor/$VERSION/Editor/Unity" \
             "/Applications/Unity/Hub/Editor/$VERSION/Unity.app/Contents/MacOS/Unity" \
             "/opt/unity/Hub/Editor/$VERSION/Editor/Unity"; do
        [ -x "$p" ] && UNITY="$p" && break
    done
fi
if [ -z "$UNITY" ]; then
    echo "Unity $VERSION не найдена. Укажите путь: UNITY=/путь/к/Unity ./run.sh" >&2
    exit 1
fi

echo "Unity: $UNITY"
echo "Сцена: $SCENE"
"$UNITY" -projectPath "$PWD" -executeMethod BasozavrLauncher.Play -scene "$SCENE" &
