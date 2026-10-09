"""Python/run.py: mission parameters from flags, scene 1 started in RSMA."""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from RSMA.MockServer import MockServer
from RSMA.Types.Vector3 import Vector3
from RSMA.uDTP.Topics import MissionStatus, Pose
from scene.launcher import launch_unity

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run  # noqa: E402  (Python/run.py)


def test_flags_map_to_unity_fields(tmp_path):
    cfg_file = tmp_path / "m.json"
    cfg_file.write_text(json.dumps({"delivery": {"cruiseSpeed": 3, "hoverTime": 9}, "environment": {"windSpeed": 1}}))
    args = run.parse_args(["--config", str(cfg_file), "--speed", "6", "--height", "15", "--delivery", "60", "30",
                           "--no-loop", "--drones", "4", "--payload-mass", "15", "--wind-dir", "1", "0"])
    config = run.build_config(args)
    assert config["delivery"] == {"cruiseSpeed": 6.0, "hoverTime": 9, "cruiseHeight": 15.0, "loop": False,
                                  "deliveryPosition": {"x": 60.0, "y": 0.0, "z": 30.0}}
    assert config["environment"] == {"windSpeed": 1, "numDrones": 4, "payloadMass": 15.0,
                                     "windDirection": {"x": 1.0, "y": 0.0, "z": 0.0}}


def test_no_flags_give_empty_config():
    assert run.build_config(run.parse_args([])) == {}


def test_running_unity_gets_config_and_scene_1(capsys):
    """Unity plays another scene (e.g. SupremeFlat): run.py sets the parameters and loads scene 1."""
    with MockServer(port=0, host="127.0.0.1") as server:
        server.active_scene, server.external_control = "Assets/Scenes/SupremeFlat.unity", False
        assert run.main(["--port", str(server.port), "--host", "127.0.0.1", "--speed", "6", "--no-monitor"]) == 0
        assert server.active_scene == "Assets/1.unity"
        assert server.external_control is False  # built-in mission flies
        assert server.mission_config["delivery"]["cruiseSpeed"] == 6.0


def test_scene_1_is_restarted_with_new_parameters():
    with MockServer(port=0, host="127.0.0.1") as server:
        server.external_control = False
        launch_unity(host="127.0.0.1", port=server.port, python_control=False,
                     mission_config={"delivery": {"cruiseHeight": 20}})
        assert server.restart_count == 1
        assert server.mission_config["delivery"] == {"cruiseHeight": 20, "externalControl": False}


def test_open_editor_gets_a_play_request(tmp_path):
    """Unity is open but not playing: the request file makes the editor open scene 1 and press Play."""
    (tmp_path / "Temp").mkdir()
    (tmp_path / "Temp" / "UnityLockfile").write_text("")
    request = tmp_path / "Temp" / "rsma_play_request.json"
    server = MockServer(port=0, host="127.0.0.1")
    port, seen = server.port, {}

    def editor():  # what RSMALauncher.WatchRequests does
        while not request.exists():
            time.sleep(0.05)
        data = json.loads(request.read_text())
        request.unlink()
        seen.update(data)
        server.mission_config = json.loads(data["config"])
        server.active_scene = data["scene"]
        server.external_control = server.mission_config["delivery"]["externalControl"]
        server.start()

    threading.Thread(target=editor, daemon=True).start()
    try:
        launch_unity(host="127.0.0.1", port=port, project=tmp_path, python_control=False,
                     mission_config={"environment": {"payloadMass": 20}})
        assert seen["scene"] == "Assets/1.unity"
        assert json.loads(seen["config"]) == {"environment": {"payloadMass": 20}, "delivery": {"externalControl": False}}
        assert not request.exists()
    finally:
        server.stop()


def test_monitor_prints_progress(capsys):
    with MockServer(port=0, host="127.0.0.1") as server:
        server.broker.publish_obj("MissionStatus", MissionStatus(timestamp=1, phase="Перелёт", distanceToFinish=12.5))
        server.broker.publish_obj("PayloadPose", Pose(position=Vector3(100, 12, 70), timestamp=1))
        run.monitor("127.0.0.1", server.port, duration=1.5)
    out = capsys.readouterr().out
    assert "Перелёт" in out and "до площадки   12.5 м" in out and "груз ( 100.0,  12.0,   70.0)" in out


@pytest.mark.parametrize("python_control", [False, True])
def test_launch_passes_config_and_mode(tmp_path, monkeypatch, python_control):
    from test_launcher import FAKE, free_port

    exe = tmp_path / "Unity"
    exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n')
    exe.chmod(0o755)
    args_file = tmp_path / "args.txt"
    monkeypatch.setenv("FAKE_UNITY_ARGS", str(args_file))
    port = free_port()
    unity = launch_unity(host="127.0.0.1", port=port, unity=exe, project=tmp_path, timeout=30,
                         python_control=python_control, mission_config={"delivery": {"cruiseSpeed": 5}})
    try:
        args = args_file.read_text().splitlines()
        assert ("-python" in args) == python_control
        config = json.loads(Path(str(args_file) + ".config").read_text())
        assert config == {"delivery": {"cruiseSpeed": 5, "externalControl": python_control}}
    finally:
        unity.stop()


def _fake_exe(path: Path, args_file: Path) -> Path:
    from test_launcher import FAKE

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n')
    path.chmod(0o755)
    return path


def test_built_rsma_is_preferred_over_editor(tmp_path, monkeypatch):
    """With a build present the editor is not started: only scene 1 exists in it."""
    from test_launcher import free_port

    args_file = tmp_path / "args.txt"
    monkeypatch.setenv("FAKE_UNITY_ARGS", str(args_file))
    editor = _fake_exe(tmp_path / "editor" / "Unity", tmp_path / "unused")
    monkeypatch.setenv("RSMA_UNITY", str(editor))
    project = tmp_path / "project"
    _fake_exe(project / "Builds" / "SwarmDelivery" / "SwarmDelivery.x86_64", args_file)
    port = free_port()
    unity = launch_unity(host="127.0.0.1", port=port, project=project, timeout=30, python_control=False,
                         mission_config={"delivery": {"cruiseSpeed": 7}})
    try:
        args = args_file.read_text().splitlines()
        assert "-executeMethod" not in args and "-screen-fullscreen" in args
        assert json.loads(Path(str(args_file) + ".config").read_text())["delivery"]["cruiseSpeed"] == 7
    finally:
        unity.stop()


def test_build_player_runs_unity_batchmode(tmp_path, monkeypatch):
    from scene.launcher import build_player

    editor = tmp_path / "Unity"
    editor.write_text('#!/bin/sh\n'
                      'while [ $# -gt 0 ]; do [ "$1" = "-projectPath" ] && P="$2"; shift; done\n'
                      'mkdir -p "$P/Builds/SwarmDelivery" && echo built > "$P/Builds/SwarmDelivery/SwarmDelivery.x86_64"\n')
    editor.chmod(0o755)
    project = tmp_path / "project"
    project.mkdir()
    player = build_player(project=project, unity=editor)
    assert player == project / "Builds" / "SwarmDelivery" / "SwarmDelivery.x86_64"
    assert player.stat().st_mode & 0o111


def test_build_refuses_while_editor_is_open(tmp_path):
    from scene.launcher import UnityLaunchError, build_player

    (tmp_path / "Temp").mkdir()
    (tmp_path / "Temp" / "UnityLockfile").write_text("")
    with pytest.raises(UnityLaunchError, match="закройте проект"):
        build_player(project=tmp_path, unity="/bin/true")


def test_stale_build_is_detected(tmp_path):
    import os

    from scene.launcher import build_is_stale

    player = tmp_path / "Builds" / "SwarmDelivery" / "SwarmDelivery.x86_64"
    player.parent.mkdir(parents=True)
    player.write_text("")
    script = tmp_path / "Assets" / "Scripts" / "X.cs"
    script.parent.mkdir(parents=True)
    script.write_text("")
    os.utime(player, (1000, 1000))
    assert build_is_stale(player, tmp_path)
    os.utime(player, (time.time() + 10, time.time() + 10))
    assert not build_is_stale(player, tmp_path)


def test_build_windows_and_package(tmp_path):
    """--build windows: Unity batchmode with BuildWindows, then a zip that runs on a PC without Unity."""
    import zipfile

    from scene.launcher import build_player, package_windows

    repo = Path(__file__).resolve().parents[2]
    project = tmp_path / "project"
    (project / "Python").mkdir(parents=True)
    import shutil

    shutil.copytree(repo / "Python" / "Source", project / "Python" / "Source",
                    ignore=shutil.ignore_patterns("__pycache__", "logs"))
    for rel in ("Python/run.py", "Python/requirements.txt", "rsma.bat", "ЗАПУСК.txt"):
        shutil.copy(repo / rel, project / rel)
    editor = tmp_path / "Unity"
    editor.write_text('#!/bin/sh\n'
                      'while [ $# -gt 0 ]; do [ "$1" = "-projectPath" ] && P="$2"; '
                      '[ "$1" = "-executeMethod" ] && M="$2"; shift; done\n'
                      '[ "$M" = "SwarmDeliveryBuild.BuildWindows" ] || exit 3\n'
                      'mkdir -p "$P/Builds/SwarmDeliveryWin/SwarmDelivery_Data" && echo exe > "$P/Builds/SwarmDeliveryWin/SwarmDelivery.exe"\n'
                      'echo data > "$P/Builds/SwarmDeliveryWin/SwarmDelivery_Data/level0"\n')
    editor.chmod(0o755)

    exe = build_player(project=project, unity=editor, target="windows")
    assert exe == project / "Builds" / "SwarmDeliveryWin" / "SwarmDelivery.exe"

    archive = package_windows(project)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert "SwarmDelivery/Builds/SwarmDeliveryWin/SwarmDelivery.exe" in names
        assert "SwarmDelivery/Builds/SwarmDeliveryWin/SwarmDelivery_Data/level0" in names
        assert "SwarmDelivery/Python/run.py" in names and "SwarmDelivery/Python/Source/scene/launcher.py" in names
        assert not any("__pycache__" in n for n in names)
        bat = zf.read("SwarmDelivery/rsma.bat")
        assert b"\r\n" in bat and b"\n" not in bat.replace(b"\r\n", b"")  # CRLF only
        assert "SwarmDelivery/ЗАПУСК.txt" in names

    # Unpacked on "Windows": run.py finds the build next to it (PROJECT_ROOT is the archive root)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(tmp_path / "unpacked")
    from scene.launcher import BUILD_TARGETS

    root = tmp_path / "unpacked" / "SwarmDelivery"
    assert (root / BUILD_TARGETS["windows"][1]).exists()
    assert (root / "Python" / "Source" / "scene" / "launcher.py").resolve().parents[3] == root.resolve()


def test_cross_build_hint_when_module_missing(tmp_path):
    from scene.launcher import UnityLaunchError, build_player

    editor = tmp_path / "Unity"
    editor.write_text('#!/bin/sh\nexit 1\n')
    editor.chmod(0o755)
    (tmp_path / "p").mkdir()
    with pytest.raises(UnityLaunchError, match="Windows Build Support"):
        build_player(project=tmp_path / "p", unity=editor, target="windows")
