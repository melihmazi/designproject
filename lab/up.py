#!/usr/bin/env python3
"""13 IOS dugumunu sifirlar, baslatir ve paralel bootstrap eder (SSH anahtari dahil).   python up.py [ISIM ...]"""
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lab import NODES

LAB = Path(__file__).resolve().parent
PY = str(LAB.parent / "network-automation-project" / ".venv" / "Scripts" / "python.exe")
names = sys.argv[1:] or list(NODES)
t0 = time.monotonic()
for n in names:
    subprocess.run([PY, "lab.py", "reset", n], cwd=LAB, capture_output=True)
print(subprocess.run([PY, "lab.py", "start", *names], cwd=LAB, capture_output=True, text=True).stdout)


def boot(n):
    p = subprocess.run([PY, "console.py", "bootstrap", n, "--ssh"], cwd=LAB, capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


with ThreadPoolExecutor(len(names)) as ex:
    for line in ex.map(boot, names):
        print(line, flush=True)
print(f"toplam {time.monotonic() - t0:.0f} sn")
