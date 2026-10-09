#!/usr/bin/env bash
# Запуск миссии доставки груза роем в RSMA. Работает из любой папки:
#   /путь/к/проекту/rsma.sh                        миссия с параметрами сцены
#   /путь/к/проекту/rsma.sh --speed 6 --height 15  с параметрами (все: rsma.sh --help)
#   /путь/к/проекту/rsma.sh --build                собрать RSMA-приложение (нужна Unity, один раз)
#   /путь/к/проекту/rsma.sh --build windows        собрать под Windows и упаковать архив
# При первом запуске создает окружение Python (Python/.venv) и ставит зависимости.
set -e
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV="$ROOT/Python/.venv"
PY="$VENV/bin/python"

if [ ! -f "$VENV/rsma_ok" ]; then
    echo "Первый запуск: готовлю Python-окружение в $VENV ..."
    if [ ! -x "$PY" ]; then
        python3 -m venv "$VENV" || {
            echo "Не удалось создать окружение. Установите: sudo apt install python3-venv python3-full" >&2
            exit 1
        }
    fi
    "$PY" -m pip install --disable-pip-version-check -q -r "$ROOT/Python/requirements.txt"
    touch "$VENV/rsma_ok"
fi

exec "$PY" "$ROOT/Python/run.py" "$@"
