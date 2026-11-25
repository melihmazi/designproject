#!/usr/bin/env python3
"""MRK-DAG1 + MRK-DAG2 birbirine kablolu (L07/L08, Po2 L2 trunk) calistirilir; protokoller gercekten sinanir.

Sinananlar: LACP Po2 (SU), Vlan254 uzerinden OSPF komsulugu, HSRP rolleri (DAG1: 10/30/50/90, DAG2: 20/40/60),
STP kokleri, ve DAG1 durdurulunca HSRP'nin DAG2'ye gecisi (yol haritasi F4 senaryosu).

    python pair_test.py
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
OUT = LAB / "logs" / "pair_test.txt"


def run(args, cwd, timeout=2400):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=ENVV,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def show(name, cmd):
    for _ in range(3):
        time.sleep(4)
        _, out = run([PY, "console.py", "show", name, cmd], LAB, 300)
        if out.count("\n") > 2:
            break
    text = f"\n===== {name}# {cmd} =====\n{out}"
    with OUT.open("a", encoding="utf-8") as f:
        f.write(text)
    return out


def main():
    OUT.write_text("", encoding="utf-8")
    checks = []

    def check(label, ok):
        checks.append((label, ok))
        print(("GECTI  " if ok else "KALDI  ") + label, flush=True)

    for n in PAIR:
        run([PY, "lab.py", "reset", n], LAB)
    run([PY, "lab.py", "start", *PAIR], LAB)
    for n in PAIR:
        code, out = run([PY, "console.py", "bootstrap", n], LAB)
        print(out.strip().splitlines()[-1], flush=True)
    t0 = time.monotonic()
    code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--only", *PAIR], PROJ)
    print(out, flush=True)
    check(f"deploy 1 2 3 iki cihazda hatasiz (cikis kodu {code}, {time.monotonic() - t0:.0f} sn)", code == 0)

    print("Protokollerin yakinsamasi icin 120 sn bekleniyor...", flush=True)
    time.sleep(120)

    ec = show("MRK-DAG1", "show etherchannel summary")
    check("DAG1 Po2 (SU) ve iki uye (P)", "Po2(SU)" in ec and ec.count("(P)") >= 2)
    ospf = show("MRK-DAG1", "show ip ospf neighbor")
    check("DAG1 OSPF komsusu 172.20.20.4 FULL (Vlan254)", "172.20.20.4" in ospf and "FULL" in ospf and "Vlan254" in ospf)
    abr = show("MRK-DAG1", "show ip ospf | include border")
    check("DAG1 alan sinir yonlendiricisi (ABR)", "area border" in abr)
    sb1 = show("MRK-DAG1", "show standby brief")
    sb2 = show("MRK-DAG2", "show standby brief")

    def roles(text):
        out = {}
        for line in text.splitlines():
            p = line.split()
            if len(p) >= 5 and p[0].startswith("Vl"):
                out[int(p[0][2:])] = next((x for x in p if x in ("Active", "Standby", "Init", "Speak", "Listen")), "?")
        return out

    r1, r2 = roles(sb1), roles(sb2)
    check(f"DAG1 HSRP Active: 10,30,50,90 / Standby: 20,40,60  -> {r1}",
          all(r1.get(v) == "Active" for v in (10, 30, 50, 90)) and all(r1.get(v) == "Standby" for v in (20, 40, 60)))
    check(f"DAG2 HSRP Active: 20,40,60 / Standby: 10,30,50,90  -> {r2}",
          all(r2.get(v) == "Active" for v in (20, 40, 60)) and all(r2.get(v) == "Standby" for v in (10, 30, 50, 90)))
    st1 = show("MRK-DAG1", "show spanning-tree vlan 10 | include root|Root")
    st2 = show("MRK-DAG2", "show spanning-tree vlan 20 | include root|Root")
    check("DAG1 VLAN 10 STP koku", "This bridge is the root" in st1)
    check("DAG2 VLAN 20 STP koku", "This bridge is the root" in st2)
    dh = show("MRK-DAG1", "show ip dhcp pool | include Pool")
    check("DAG1'de 6 DHCP havuzu", dh.count("Pool ") == 6)
    ping = show("MRK-DAG2", "ping 172.20.20.3 source Loopback0")
    check("DAG2 Lo0 -> DAG1 Lo0 ping (OSPF rotasi)", "!!!" in ping)

    # --- F4: DAG1 arizasi ---
    run([PY, "lab.py", "stop", "MRK-DAG1"], LAB)
    print("DAG1 durduruldu; HSRP gecisi icin 40 sn bekleniyor...", flush=True)
    time.sleep(40)
    r2 = roles(show("MRK-DAG2", "show standby brief"))
    check(f"F4: DAG1 kapaninca DAG2 tum VLAN'larda Active -> {r2}", len(r2) == 7 and all(v == "Active" for v in r2.values()))

    run([PY, "lab.py", "stop", "MRK-DAG2"], LAB)
    passed = sum(ok for _, ok in checks)
    summary = f"\nSONUC: {passed}/{len(checks)} kontrol gecti\n"
    print(summary, flush=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write("\n===== OZET =====\n" + "\n".join(("GECTI  " if ok else "KALDI  ") + l for l, ok in checks) + summary)
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
