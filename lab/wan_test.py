#!/usr/bin/env python3
"""WAN dilimi: SNR-RTR + ISS-RTR + FAB-RTR kablolu (L11, L12) calistirilir; Faz 3 kenar ozellikleri sinanir.

Sinananlar: underlay ping, GRE Tunnel0 up/up, tunel uzerinden OSPF Area 300 komsulugu, FAB-RTR'da O*IA default
(totally stubby), FAB LAN'indan internete NAT/PAT, Merkez<->Tesis trafiginin NAT'a girmemesi, validate.py raporu.
Paketler lab/captures altina kaydedilir (GRE icin L11).

    python wan_test.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
PROJ = LAB.parent / "network-automation-project"
PY = str(PROJ / ".venv" / "Scripts" / "python.exe")
ENVV = {**os.environ, "NET_CONSOLE_HOST": "127.0.0.1", "PYTHONIOENCODING": "utf-8", "LAB_CAPTURE": "1"}
TRIO = ["SNR-RTR", "ISS-RTR", "FAB-RTR"]
OUT = LAB / "logs" / "wan_test.txt"


def run(args, cwd, timeout=2400):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=ENVV,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def show(name, cmd):
    code = ("import sys; sys.path.insert(0, 'core/scripts'); import deploy; from validate import collect; "
            f"deploy.load_dotenv(); dev = next(d for d in deploy.load_inventory() if d['name'] == {name!r}); "
            f"print(collect(dev, [{cmd!r}])[{cmd!r}])")
    _, out = run([PY, "-c", code], PROJ)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {name}# {cmd} =====\n{out}")
    return out


def main():
    OUT.write_text("", encoding="utf-8")
    checks = []

    def check(label, ok):
        checks.append((label, ok))
        print(("GECTI  " if ok else "KALDI  ") + label, flush=True)

    for n in TRIO:
        run([PY, "lab.py", "reset", n], LAB)
    run([PY, "lab.py", "start", *TRIO], LAB)
    for n in TRIO:
        print(run([PY, "console.py", "bootstrap", n], LAB)[1].strip().splitlines()[-1], flush=True)
    code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--only", *TRIO], PROJ)
    print(out, flush=True)
    check(f"deploy 1 2 3 uc router'da hatasiz (cikis kodu {code})", code == 0)
    print("Yakinsama icin 90 sn bekleniyor...", flush=True)
    time.sleep(90)

    check("Underlay: SNR -> FAB genel adresi (198.51.100.6) ping", "!!!" in show("SNR-RTR", "ping 198.51.100.6"))
    check("SNR Tunnel0 up/up", "line protocol is up" in show("SNR-RTR", "show interfaces Tunnel0 | include line protocol"))
    nb = show("SNR-RTR", "show ip ospf neighbor")
    check("SNR OSPF komsusu 172.20.20.6 FULL (Tunnel0)", "172.20.20.6" in nb and "FULL" in nb and "Tunnel0" in nb)
    rt = show("FAB-RTR", "show ip route ospf")
    check("FAB-RTR'da O*IA 0.0.0.0/0 (totally stubby default)", "O*IA" in rt and "0.0.0.0/0" in rt)
    check("FAB-RTR'da baska OSPF rotasi yok (no-summary)", rt.count("\nO") == 1)
    rec = show("FAB-RTR", "show ip route 198.51.100.0 255.255.255.252")
    check("Rekursif yonlendirme korumasi: 198.51.100.0/30 statik, Tunnel0 degil", "static" in rec and "Tunnel0" not in rec)
    check("SNR'da 172.18.10.0/24 tunelden ogrenildi", "Tunnel0" in show("SNR-RTR", "show ip route 172.18.10.0"))
    check("Tesis LAN -> internet (203.0.113.1) ping, kaynak Gi0/1",
          "!!!" in show("FAB-RTR", "ping 203.0.113.1 source GigabitEthernet0/1"))
    nat = show("SNR-RTR", "show ip nat translations")
    check("NAT tablosunda 172.18.10.1 -> 198.51.100.1 cevirisi", "172.18.10.1" in nat and "198.51.100.1" in nat)
    show("SNR-RTR", "clear ip nat translation *")
    check("Tesis LAN -> Merkez (SNR Lo0 172.20.20.5) ping",
          "!!!" in show("FAB-RTR", "ping 172.20.20.5 source GigabitEthernet0/1"))
    nat2 = show("SNR-RTR", "show ip nat translations")
    check("Merkez<->Tesis trafigi NAT'a girmedi", "172.18.10.1" not in nat2)
    acl = show("FAB-RTR", "show access-lists ACL-FAB-IN")
    check("ACL-FAB-IN yuklu (11 satir)", acl.count("permit") + acl.count("deny") == 11)

    code, out = run([PY, "core/scripts/validate.py", "--only", *TRIO, "--partial"], PROJ)
    print(out, flush=True)
    check(f"validate.py uc router'i saglikli raporladi (cikis kodu {code})", code == 0)

    # F7: tunel arizasi
    run([PY, str(LAB / "_push.py"), "SNR-RTR", "interface Tunnel0", "shutdown"], PROJ)
    time.sleep(50)
    code, out = run([PY, "core/scripts/validate.py", "--only", *TRIO, "--partial"], PROJ)
    print(out, flush=True)
    check(f"F7: Tunnel0 kapatilinca rapor kirmizi (cikis kodu {code})", code == 1 and "Tunnel0" in out)
    run([PY, str(LAB / "_push.py"), "SNR-RTR", "interface Tunnel0", "no shutdown"], PROJ)
    time.sleep(60)
    code, out = run([PY, "core/scripts/backup.py", "--only", *TRIO, "--sanitize"], PROJ)
    print(out, flush=True)
    check("backup.py uc router'i yedekledi", code == 0)

    run([PY, "lab.py", "stop"], LAB)
    passed = sum(ok for _, ok in checks)
    summary = f"\nSONUC: {passed}/{len(checks)} kontrol gecti\n"
    print(summary, flush=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write("\n===== OZET =====\n" + "\n".join(("GECTI  " if ok else "KALDI  ") + l for l, ok in checks) + summary)
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
