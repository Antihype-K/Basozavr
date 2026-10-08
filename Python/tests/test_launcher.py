import platform
import stat
import sys
from pathlib import Path

import pytest

from RSMA.MockServer import MockServer
from scene import Simulation, UnityLaunchError, launch_unity
from scene.launcher import find_unity_editor, server_alive

pytestmark = pytest.mark.skipif(platform.system() == "Windows", reason="fake editor is a shell script")

FAKE = Path(__file__).resolve().parent / "fake_unity.py"


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def fake_unity(tmp_path, monkeypatch):
    exe = tmp_path / "Unity"
    exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    args_file = tmp_path / "args.txt"
    monkeypatch.setenv("FAKE_UNITY_ARGS", str(args_file))
    return exe, args_file


def test_launch_opens_scene_and_waits_for_server(fake_unity, tmp_path):
    exe, args_file = fake_unity
    port = free_port()
    unity = launch_unity(port=port, host="127.0.0.1", unity=exe, project=tmp_path, timeout=30)
    try:
        assert unity.launched_by_us
        assert server_alive("127.0.0.1", port)
        args = args_file.read_text().splitlines()
        assert args[args.index("-executeMethod") + 1] == "RSMALauncher.PlayScene"
        assert args[args.index("-rsmaScene") + 1] == "Assets/Scenes/SupremeFlat.unity"
        assert args[args.index("-projectPath") + 1] == str(tmp_path)

        with Simulation(host="127.0.0.1", port=port) as sim:
            assert sim.wait_for_scene(timeout=10)
            assert sim.find_drones() == [1, 2, 3, 4, 5, 6]
            assert sim.payload_pose() is not None
    finally:
        unity.stop()
    assert unity.process.poll() is not None


def test_running_scene_is_reused(tmp_path):
    with MockServer(port=0, host="127.0.0.1") as server:
        unity = launch_unity(port=server.port, host="127.0.0.1", unity=tmp_path / "no-such-unity", project=tmp_path)
        assert not unity.launched_by_us


def test_editor_exit_is_reported(fake_unity, tmp_path, monkeypatch):
    exe, _ = fake_unity
    monkeypatch.setenv("FAKE_UNITY_MODE", "fail")
    with pytest.raises(UnityLaunchError, match="уже открыт"):
        launch_unity(port=free_port(), host="127.0.0.1", unity=exe, project=tmp_path, timeout=30)


def test_missing_editor_explains_what_to_do(tmp_path, monkeypatch):
    monkeypatch.delenv("RSMA_UNITY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "ProjectSettings").mkdir()
    (tmp_path / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3.16f1\n")
    with pytest.raises(UnityLaunchError, match="6000.3.16f1.*RSMA_UNITY"):
        launch_unity(port=free_port(), host="127.0.0.1", project=tmp_path, timeout=5)


@pytest.mark.skipif(platform.system() != "Linux", reason="Unity Hub layout differs per OS")
def test_editor_found_in_unity_hub(tmp_path, monkeypatch):
    monkeypatch.delenv("RSMA_UNITY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    exe = tmp_path / "Unity" / "Hub" / "Editor" / "6000.3.16f1" / "Editor" / "Unity"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    project = tmp_path / "project"
    (project / "ProjectSettings").mkdir(parents=True)
    (project / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3.16f1\n")
    assert find_unity_editor(project=project) == exe
    monkeypatch.setenv("RSMA_UNITY", "/opt/custom/Unity")
    assert find_unity_editor(project=project) == Path("/opt/custom/Unity")


def test_remote_host_is_not_launched(tmp_path):
    with pytest.raises(UnityLaunchError, match="другой машине"):
        launch_unity(host="192.0.2.1", port=5555, project=tmp_path)


def test_connect_launches_scene(fake_unity, tmp_path, monkeypatch):
    exe, _ = fake_unity
    port = free_port()
    monkeypatch.setattr("scene.launcher.PROJECT_ROOT", tmp_path)
    from scene import connect

    sim = connect(["--host", "127.0.0.1", "--port", str(port), "--unity", str(exe), "--close-unity"])
    try:
        assert sim.unity is not None and sim.unity.launched_by_us
        assert len(sim.find_drones()) == 6
    finally:
        sim.close()
    assert sim.unity.process.poll() is not None
    assert sim.unity.log_path == tmp_path / "Logs" / "rsma_python_launch.log"
