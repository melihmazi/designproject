#!/usr/bin/env python3
"""Gercek GNS3 projesinde bir cihazdan show ciktisi alir (parola grubu kendiliginden secilir).

    ..\network-automation-project\.venv\Scripts\python.exe gns3_show.py MRK-DAG1 "show access-lists" "show standby brief"
"""
import os
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parent / "network-automation-project" / "core" / "scripts"))
os.environ["NET_CONSOLE_HOST"] = "127.0.0.1"
os.environ.pop("NET_NO_ENABLE", None)
import deploy
import gns3_run
import validate


def show(name, *cmds):
    user, pw, en = gns3_run.creds("rtr" if name in gns3_run.RTR else "sw")
    os.environ.update(NET_USER=user, NET_PASS=pw, NET_ENABLE=en)
    dev = next(d for d in deploy.load_inventory() if d["name"] == name)
    return validate.collect(dev, list(cmds))


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    for cmd, out in show(sys.argv[1], *sys.argv[2:]).items():
        print(f"----- {sys.argv[1]}# {cmd} -----\n{out}\n")
