#!/usr/bin/env python3
"""Gercek GNS3 projesi icin parola sarmalayicisi (degerleri ekrana yazmaz).

    python gns3_run.py sw  <betik.py> [arg...]     # switch parolalari: lab/gns3_env.txt
    python gns3_run.py rtr <betik.py> [arg...]     # router parolalari: yol haritasi (bootstrap blogu)
Betik ag otomasyon projesinin venv'i ile, NET_CONSOLE_HOST=127.0.0.1 ayarli calisir.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
PY = ROOT / "network-automation-project" / ".venv" / "Scripts" / "python.exe"
SW = ["MRK-CORE1", "MRK-CORE2", "MRK-DAG1", "MRK-DAG2", "MRK-ERS-SAT", "MRK-ERS-PER", "MRK-ERS-YNT",
      "MRK-ERS-SRV", "MRK-ERS-BIS", "FAB-ERS-1"]
RTR = ["SNR-RTR", "ISS-RTR", "FAB-RTR"]


def creds(group):
    if group == "sw":
        e = dict(l.strip().split("=", 1) for l in (LAB / "gns3_env.txt").read_text(encoding="utf-8").splitlines()
                 if "=" in l and not l.startswith("#"))
        return e.get("SWITCH_KULLANICI", "admin"), e["SWITCH_KULLANICI_PAROLASI"], e["SWITCH_ENABLE"]
    doc = (ROOT / "design-project-yol-haritası.md").read_text(encoding="utf-8")
    en = re.search(r"^enable secret (\S+)", doc, re.M).group(1)
    m = re.search(r"^username (\S+) privilege 15 secret (\S+)", doc, re.M)
    return m.group(1), m.group(2), en


def main():
    group, args = sys.argv[1], sys.argv[2:]
    user, pw, en = creds(group)
    env = dict(os.environ, NET_USER=user, NET_PASS=pw, NET_ENABLE=en, NET_CONSOLE_HOST="127.0.0.1")
    env.pop("NET_NO_ENABLE", None)
    args = [a for x in args for a in ((SW if group == "sw" else RTR) if x == "@grup" else [x])]
    sys.exit(subprocess.run([str(PY)] + args, env=env, cwd=str(ROOT / "network-automation-project")).returncode)


if __name__ == "__main__":
    main()
