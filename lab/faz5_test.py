#!/usr/bin/env python3
"""Faz 5 lab testi: DAG1+DAG2 uzerinde validate.py once yesil, link kapatilinca kirmizi olmali.

Adimlar: lab kur -> deploy 1 2 3 -> validate (saglikli) -> DAG1 Gi0/2 kapat -> validate (uye kaybi)
-> DAG1 Gi0/3 de kapat (Po2 tamamen duser) -> validate (OSPF + HSRP kirmizi) -> portlari ac -> validate (yesil).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
PROJ = LAB.parent / "network-automation-project"
PY = str(PROJ / ".venv" / "Scripts" / "python.exe")
ENVV = {**os.environ, "NET_CONSOLE_HOST": "127.0.0.1", "PYTHONIOENCODING": "utf-8"}
PAIR = ["MRK-DAG1", "MRK-DAG2"]
sys.path.insert(0, str(LAB))


def run(args, cwd, timeout=2400):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=ENVV,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def validate(label, expect_code):
    code, out = run([PY, "core/scripts/validate.py", "--only", *PAIR, "--partial"], PROJ)
    ok = code == expect_code
    print(f"\n######## {label}  (cikis kodu {code}, beklenen {expect_code}) -> {'GECTI' if ok else 'KALDI'}\n{out}", flush=True)
    return ok


def ports(name, intfs, shut):
    """Portu deploy.push ile kapat/ac (konsol durumundan bagimsiz, yeniden denemeli)."""
    lines = []
    for i in intfs:
        lines += [f"interface {i}", "shutdown" if shut else "no shutdown"]
    code = ("import sys; sys.path.insert(0, 'core/scripts'); import deploy; deploy.load_dotenv(); "
            f"dev = next(d for d in deploy.load_inventory() if d['name'] == {name!r}); "
            f"print(deploy.push(dev, {lines!r})[1])")
    rc, out = run([PY, "-c", code], PROJ)
    print(f"{name}: {' + '.join(intfs)} -> {'shutdown' if shut else 'no shutdown'} (kod {rc}) {out.strip()[-60:]}", flush=True)


def main():
    results = []
    if "--reuse" not in sys.argv:
        for n in PAIR:
            run([PY, "lab.py", "reset", n], LAB)
        run([PY, "lab.py", "start", *PAIR], LAB)
        for n in PAIR:
            print(run([PY, "console.py", "bootstrap", n], LAB)[1].strip().splitlines()[-1], flush=True)
        code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--only", *PAIR], PROJ)
        print(out, flush=True)
        print("Yakinsama icin 120 sn bekleniyor...", flush=True)
        time.sleep(120)

    else:
        ports("MRK-DAG1", ["GigabitEthernet0/2", "GigabitEthernet0/3"], False)
        time.sleep(120)

    results.append(validate("1) SAGLIKLI DURUM", 0))
    ports("MRK-DAG1", ["GigabitEthernet0/2"], True)
    time.sleep(45)
    results.append(validate("2) DAG1 Gi0/2 KAPALI (LACP uye kaybi)", 1))
    ports("MRK-DAG1", ["GigabitEthernet0/3"], True)
    time.sleep(60)
    results.append(validate("3) DAG1 Gi0/2 + Gi0/3 KAPALI (Po2 tamamen dustu)", 1))
    ports("MRK-DAG1", ["GigabitEthernet0/2", "GigabitEthernet0/3"], False)
    time.sleep(120)
    results.append(validate("4) PORTLAR ACILDI (iyilesme)", 0))
    print(f"\nSONUC: {sum(results)}/{len(results)} asama beklendigi gibi", flush=True)
    if "--keep" not in sys.argv:
        run([PY, "lab.py", "stop"], LAB)
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
