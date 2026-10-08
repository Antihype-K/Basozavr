"""
Stand-in for the Unity editor in launcher tests: records its arguments, then serves
the offline swarm scene over the RSMA NetMQ protocol on $RSMA_PORT, like ServerApp would.

FAKE_UNITY_MODE=fail makes it write a log and exit, like Unity refusing an open project.
"""

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Source"))

from RSMA.MockServer import MockServer  # noqa: E402
from sim.scene_sim import OfflineScene  # noqa: E402

args = sys.argv[1:]
Path(os.environ["FAKE_UNITY_ARGS"]).write_text("\n".join(args), encoding="utf-8")
log_file = Path(args[args.index("-logFile") + 1])

if os.environ.get("FAKE_UNITY_MODE") == "fail":
    log_file.write_text("Aborting: It looks like another Unity instance is running with this project open.\n")
    sys.exit(1)

time.sleep(1.0)  # "loading the editor"
server = MockServer(port=int(os.environ["RSMA_PORT"]), host="127.0.0.1")
scene = OfflineScene(server.broker)
server.start()

stop = threading.Event()
while not stop.wait(0.01):
    scene.step()
