"""
Автозапуск сцены RSMA в Unity из Python.

Если сервер RSMA (NetMQ, порт 5555) не отвечает, launch_unity():
1. находит редактор Unity нужной версии (ProjectSettings/ProjectVersion.txt),
2. запускает его с проектом, открывает сцену 1 (Assets/1.unity) и входит в Play
   (Assets/Editor/RSMALauncher.cs, метод RSMALauncher.PlayScene) с ключом -python:
   SwarmDeliveryScene не запускает встроенную миссию и ждет команд Python,
3. ждет, пока сервер в сцене начнет отвечать.

Если сцена уже запущена (сервер отвечает), Unity не трогается.

Путь к редактору можно задать явно: переменная окружения RSMA_UNITY или параметр unity=.
Вместо редактора можно запустить собранный плеер: параметр player= (путь к исполняемому файлу).
"""

import json
import logging
import os
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from RSMA.Client import RSMAClient

log = logging.getLogger("scene.launcher")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENE = "Assets/1.unity"  # сцена 1: доставка груза роем (SwarmDeliveryScene)
# Ключ, по которому SwarmDeliveryScene включает внешнее управление: встроенная миссия
# не запускается, дроны ждут команд Python, HUD показывает MissionStatus
PYTHON_CONTROL_ARG = "-python"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class UnityLaunchError(RuntimeError):
    pass


@dataclass
class UnityInstance:
    """Запущенная (или уже работавшая) Unity."""

    process: subprocess.Popen | None = None
    log_path: Path | None = None

    @property
    def launched_by_us(self) -> bool:
        return self.process is not None

    def stop(self, timeout: float = 20.0) -> None:
        """Закрывает Unity, если ее запустил этот скрипт."""
        if self.process is None or self.process.poll() is not None:
            return
        log.info("Закрываю Unity (pid %d)", self.process.pid)
        self.process.terminate()
        try:
            self.process.wait(timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()


def server_alive(host: str = "localhost", port: int = 5555, timeout_ms: int = 300) -> bool:
    """True, если сервер RSMA в сцене отвечает."""
    with RSMAClient(host=host, port=port, timeout=timeout_ms, retries=0) as client:
        return client.ping()


def scene_info(host: str = "localhost", port: int = 5555, timeout_ms: int = 1000) -> dict | None:
    """
    Какая сцена открыта в Unity и включено ли управление из Python:
    {"scene": "Assets/1.unity", "externalControl": True}. None — сервер старый и команду не знает.
    """
    with RSMAClient(host=host, port=port, timeout=timeout_ms, retries=0) as client:
        reply = client.send_command("GetSceneInfo")
    try:
        info = json.loads(reply)
    except ValueError:
        return None
    return info if isinstance(info, dict) and info.get("status") == "ok" else None


def ensure_scene_loaded(scene: str = DEFAULT_SCENE, host: str = "localhost", port: int = 5555,
                        python_control: bool | None = None, timeout: float = 120.0,
                        force_reload: bool = False, settle_time: float = 5.0) -> None:
    """
    Проверяет, что в Unity открыта нужная сцена в режиме управления из Python; если нет —
    переключает ее (команда LoadScene) и ждет загрузки. Бросает UnityLaunchError по таймауту.
    """
    if python_control is None:
        python_control = scene == DEFAULT_SCENE  # режим -python есть у SwarmDeliveryScene сцены 1
    if scene != DEFAULT_SCENE:
        python_control = False  # в других сценах режима внешнего управления нет

    def ready(info: dict) -> bool:
        return info.get("scene") == scene and bool(info.get("externalControl")) == bool(python_control)

    info = scene_info(host, port)
    # Сразу после старта сцена может еще не сообщить себя или свой режим: даем ей несколько секунд
    settle_until = time.monotonic() + settle_time
    while info is not None and not ready(info) and not force_reload and time.monotonic() < settle_until:
        time.sleep(0.5)
        info = scene_info(host, port)
    if info is None:
        log.warning("Unity не сообщает открытую сцену (старая версия скриптов). Проверьте сами, что открыта %s"
                    "%s", scene, " с включенным externalControl у SwarmDeliveryScene" if python_control else "")
        return
    mode = "управление из Python" if python_control else "встроенная миссия"
    if ready(info) and not force_reload:
        log.info("В Unity открыта %s (%s)", scene, mode)
        return

    if ready(info):
        log.info("Перезапускаю %s с новыми параметрами", scene)
    else:
        log.warning("В Unity открыта %s (управление из Python: %s) — переключаю на %s (%s)",
                    info.get("scene") or "?", "да" if info.get("externalControl") else "нет", scene, mode)
    with RSMAClient(host=host, port=port, timeout=2000, retries=0) as client:
        reply = client.send_command(f"LoadScene:{scene}" + ("|python" if python_control else ""))
    if not reply.startswith("OK"):
        raise UnityLaunchError(f"Не удалось переключить сцену: {reply}")

    deadline = time.monotonic() + timeout
    time.sleep(1.0)  # дать сцене начать перезагрузку, чтобы не принять старое состояние за новое
    while time.monotonic() < deadline:
        time.sleep(0.5)
        info = scene_info(host, port, timeout_ms=500)
        if info is not None and ready(info):
            log.info("Сцена %s загружена", scene)
            return
    raise UnityLaunchError(f"Сцена {scene} не загрузилась за {timeout:.0f} с (сейчас: {info}). "
                           f"Она должна быть в File → Build Settings")


def project_unity_version(project: Path | None = None) -> str | None:
    project = project if project is not None else PROJECT_ROOT
    version_file = Path(project) / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.exists():
        return None
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("m_EditorVersion:"):
            return line.split(":", 1)[1].strip()
    return None


def _hub_dirs() -> list[Path]:
    """Папки, куда Unity Hub ставит редакторы."""
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        dirs = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Unity" / "Hub" / "Editor"]
        config = Path(os.environ.get("APPDATA", home)) / "UnityHub" / "secondaryInstallPath.json"
    elif system == "Darwin":
        dirs = [Path("/Applications/Unity/Hub/Editor")]
        config = home / "Library" / "Application Support" / "UnityHub" / "secondaryInstallPath.json"
    else:
        dirs = [home / "Unity" / "Hub" / "Editor"]
        config = home / ".config" / "UnityHub" / "secondaryInstallPath.json"
    try:
        custom = json.loads(config.read_text(encoding="utf-8"))
        if isinstance(custom, str) and custom:
            dirs.insert(0, Path(custom))
    except (OSError, ValueError):
        pass
    return dirs


def _editor_executable(version_dir: Path) -> Path:
    system = platform.system()
    if system == "Windows":
        return version_dir / "Editor" / "Unity.exe"
    if system == "Darwin":
        return version_dir / "Unity.app" / "Contents" / "MacOS" / "Unity"
    return version_dir / "Editor" / "Unity"


def installed_editors() -> dict[str, Path]:
    """Версии Unity, установленные через Unity Hub: {версия: путь к исполняемому файлу}."""
    found = {}
    for hub_dir in _hub_dirs():
        if not hub_dir.is_dir():
            continue
        for version_dir in hub_dir.iterdir():
            exe = _editor_executable(version_dir)
            if exe.exists():
                found.setdefault(version_dir.name, exe)
    return found


def find_unity_editor(version: str | None = None, project: Path | None = None) -> Path | None:
    """Путь к редактору Unity: RSMA_UNITY или Unity Hub с версией проекта."""
    project = project if project is not None else PROJECT_ROOT
    from_env = os.environ.get("RSMA_UNITY")
    if from_env:
        return Path(from_env)
    version = version or project_unity_version(project)
    return installed_editors().get(version) if version else None


def find_built_player(project: Path | None = None) -> Path | None:
    """Собранная игра сцены 1 (build.sh / build.bat / меню RSMA → Build SwarmDelivery)."""
    project = project if project is not None else PROJECT_ROOT
    for rel in ("Builds/SwarmDelivery/SwarmDelivery.x86_64", "Builds/SwarmDeliveryWin/SwarmDelivery.exe",
                "Builds/SwarmDelivery/SwarmDelivery.app/Contents/MacOS/SwarmDelivery"):
        path = Path(project) / rel
        if path.exists():
            return path
    return None


def build_is_stale(player: Path, project: Path | None = None) -> bool:
    """Скрипты проекта менялись после сборки (нужно пересобрать: python run.py --build)."""
    project = Path(project) if project is not None else PROJECT_ROOT
    built = player.stat().st_mtime
    scripts = project / "Assets" / "Scripts"
    return any(f.stat().st_mtime > built for f in scripts.rglob("*.cs")) if scripts.is_dir() else False


def build_player(project: Path | None = None, unity: str | Path | None = None, timeout: float = 1800.0) -> Path:
    """
    Собирает RSMA-приложение сцены 1 (как build.sh / build.bat): Unity в batchmode без окна.
    Проект при этом не должен быть открыт в редакторе.
    """
    project = Path(project) if project is not None else PROJECT_ROOT
    if editor_is_open(project):
        raise UnityLaunchError("Для сборки закройте проект в редакторе Unity и повторите")
    editor = Path(unity) if unity else find_unity_editor(project=project)
    if editor is None or not editor.exists():
        raise UnityLaunchError(f"Для сборки нужен редактор Unity {project_unity_version(project)}: "
                               f"установите его через Unity Hub или укажите путь --unity / RSMA_UNITY")
    method = "SwarmDeliveryBuild.BuildWindows" if platform.system() == "Windows" else "SwarmDeliveryBuild.BuildLinux"
    log_path = project / "Logs" / "build.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Собираю RSMA-приложение сцены 1 (Unity в фоне, несколько минут). Лог: %s", log_path)
    result = subprocess.run([str(editor), "-batchmode", "-quit", "-projectPath", str(project),
                             "-executeMethod", method, "-logFile", str(log_path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    player = find_built_player(project)
    if result.returncode != 0 or player is None:
        raise UnityLaunchError(f"Сборка не удалась (код {result.returncode}). Лог: {log_path}\n{_log_tail(log_path)}")
    if platform.system() != "Windows":
        player.chmod(player.stat().st_mode | 0o111)
    log.info("Готово: %s", player)
    return player


def _log_tail(path: Path | None, lines: int = 15) -> str:
    if path is None or not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(text[-lines:])


def editor_is_open(project: Path | None = None) -> bool:
    """Проект открыт в редакторе Unity (пока редактор работает, в Temp/ лежит UnityLockfile)."""
    project = Path(project) if project is not None else PROJECT_ROOT
    return (project / "Temp" / "UnityLockfile").exists()


def _effective_config(scene: str, python_control: bool, mission_config: dict | None) -> dict:
    """Параметры миссии + режим управления (SwarmDeliveryScene.externalControl) для сцены 1."""
    config = json.loads(json.dumps(mission_config or {}))
    if scene == DEFAULT_SCENE:
        config.setdefault("delivery", {})["externalControl"] = python_control
    return config


def _wait_for_server(host: str, port: int, timeout: float, process: subprocess.Popen | None = None,
                     log_path: Path | None = None, waiting_for: str = "Unity") -> None:
    start = time.monotonic()
    last_report = start
    while not server_alive(host, port, timeout_ms=500):
        if process is not None and process.poll() is not None:
            tail = _log_tail(log_path)
            hint = ""
            if "another Unity instance" in tail or "already open" in tail:
                hint = "\nПроект уже открыт в другой Unity: откройте там сцену и нажмите Play."
            raise UnityLaunchError(f"Unity завершилась с кодом {process.returncode}.{hint}\n"
                                   f"Лог: {log_path}\n{tail}")
        now = time.monotonic()
        if now - start > timeout:
            raise UnityLaunchError(f"{waiting_for}: сервер RSMA не ответил за {timeout:.0f} с."
                                   + (f" Лог: {log_path}\n{_log_tail(log_path)}" if log_path else ""))
        if now - last_report >= 15:
            log.info("%s... %.0f с", waiting_for, now - start)
            last_report = now
        time.sleep(1.0)
    log.info("Сервер RSMA отвечает на %s:%d (%.0f с)", host, port, time.monotonic() - start)


def launch_unity(scene: str = DEFAULT_SCENE, host: str = "localhost", port: int = 5555,
                 unity: str | Path | None = None, player: str | Path | None = None,
                 project: Path | None = None, timeout: float = 900.0,
                 log_path: Path | None = None, python_control: bool = True,
                 mission_config: dict | None = None, prefer_player: bool = True) -> UnityInstance:
    """
    Приводит Unity к нужному состоянию: открыта сцена scene, нажат Play, сервер RSMA отвечает.

    python_control=True  — сцена 1 ждет команд Python (SwarmDeliveryScene.externalControl);
    python_control=False — сцена 1 выполняет встроенную миссию.
    mission_config — параметры миссии ({"delivery": {...}, "environment": {...}}, см. MissionConfig.cs).

    Порядок:
    * RSMA уже работает (сборка или редактор в Play, любая сцена) — параметры и сцена меняются командами NetMQ;
    * есть собранное RSMA-приложение (Builds/SwarmDelivery, python run.py --build) и prefer_player —
      запускается оно: только сцена 1, старт за секунды, редактор не нужен;
    * редактор открыт, но не в Play — запрос редактору через Temp/rsma_play_request.json;
    * иначе запускается редактор Unity со сценой.

    Возвращает UnityInstance (process=None, если Unity уже работала).
    Бросает UnityLaunchError с подсказкой, что делать.
    """
    config = _effective_config(scene, python_control, mission_config)
    config_json = json.dumps(config, ensure_ascii=False)
    project = Path(project) if project is not None else PROJECT_ROOT

    # 1. Unity уже в Play
    if server_alive(host, port):
        log.info("Unity уже запущена (%s:%d)", host, port)
        if mission_config is not None or config:
            with RSMAClient(host=host, port=port, timeout=2000, retries=0) as client:
                reply = client.send_command(f"SetMissionConfig:{config_json}")
            if not reply.startswith("OK"):
                raise UnityLaunchError(
                    "Unity в режиме Play, но скрипты в ней старые и не принимают параметры. "
                    "Остановите Play, дождитесь перекомпиляции скриптов (после git pull) и запустите снова.")
        ensure_scene_loaded(scene, host, port, python_control=python_control if scene == DEFAULT_SCENE else None,
                            force_reload=mission_config is not None)
        return UnityInstance()

    if host not in LOCAL_HOSTS:
        raise UnityLaunchError(f"RSMA на {host}:{port} не отвечает. Запустить Unity на другой машине "
                               "из скрипта нельзя: откройте сцену там и нажмите Play")

    # 2. Собранное RSMA-приложение сцены 1
    if player is None and unity is None and prefer_player and scene == DEFAULT_SCENE:
        player = find_built_player(project)
        if player is not None and build_is_stale(player, project):
            log.warning("Сборка %s старше скриптов проекта — пересоберите: python run.py --build", player)

    # 3. Редактор открыт, но не в Play: просим его открыть сцену и нажать Play
    if player is None and unity is None and editor_is_open(project):
        request = project / "Temp" / "rsma_play_request.json"
        request.write_text(json.dumps({"scene": scene, "config": config_json}, ensure_ascii=False), encoding="utf-8")
        log.info("Unity открыта: прошу редактор открыть %s и нажать Play", scene)
        try:
            _wait_for_server(host, port, timeout=180.0, waiting_for="Жду, пока редактор запустит сцену")
        except UnityLaunchError:
            request.unlink(missing_ok=True)
            raise UnityLaunchError(
                f"Unity открыта, но не запустила сцену. Если скрипты еще компилируются — подождите и повторите; "
                f"иначе откройте {scene} и нажмите Play вручную (или закройте Unity: скрипт запустит ее сам)") from None
        ensure_scene_loaded(scene, host, port, python_control=python_control if scene == DEFAULT_SCENE else None)
        return UnityInstance()

    # 4. Запуск сборки или редактора
    log_path = Path(log_path) if log_path else project / "Logs" / "rsma_python_launch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    extra_args = [PYTHON_CONTROL_ARG] if python_control else []

    if player is not None:
        cmd = [str(player), *extra_args, "-screen-fullscreen", "0", "-screen-width", "1600",
               "-screen-height", "900", "-logFile", str(log_path)]
        what = f"RSMA {player}"
    else:
        editor = Path(unity) if unity else find_unity_editor(project=project)
        if (editor is None or not editor.exists()) and unity is None and find_built_player(project) is not None:
            player = find_built_player(project)
            log.info("Редактор Unity не найден, запускаю собранную сцену %s", player)
            return launch_unity(scene=scene, host=host, port=port, player=player, project=project,
                                timeout=timeout, log_path=log_path, python_control=python_control,
                                mission_config=mission_config)
        if editor is None or not editor.exists():
            version = project_unity_version(project)
            installed = ", ".join(sorted(installed_editors())) or "нет"
            raise UnityLaunchError(
                f"Не найден редактор Unity {version} (установлены: {installed}).\n"
                f"Установите {version} через Unity Hub или укажите путь: "
                f"export RSMA_UNITY=/путь/к/Editor/Unity (или параметр --unity), "
                f"либо соберите сцену: ./build.sh (Windows: build.bat)")
        cmd = [str(editor), "-projectPath", str(project),
               "-executeMethod", "RSMALauncher.PlayScene", "-rsmaScene", scene,
               *extra_args, "-logFile", str(log_path)]
        what = f"Unity {editor}"

    env = os.environ.copy()
    env["RSMA_PORT"] = str(port)  # RSMASwarmEnvironment / ServerApp поднимут сервер на этом порту
    env["RSMA_MISSION_CONFIG"] = config_json  # MissionConfig.cs применит параметры при старте сцены
    log.info("Запускаю %s, сцена %s", what, scene)
    process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               cwd=str(project))
    _wait_for_server(host, port, timeout, process, log_path,
                     waiting_for="Unity загружается (первый запуск импортирует ассеты — это может занять минуты)")
    ensure_scene_loaded(scene, host, port, python_control=python_control if scene == DEFAULT_SCENE else None)
    return UnityInstance(process=process, log_path=log_path)
