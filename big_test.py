#!/usr/bin/env python3
"""Buyuk dilim: 13 IOS cihazinin 9'u birlikte (OSPF yapan 6 cihazin tamami + bir erisim + tesis switch'i).

Calisan: MRK-CORE1/2, MRK-DAG1/2, SNR-RTR, ISS-RTR, FAB-RTR, MRK-ERS-SAT, FAB-ERS-1   (~6.2 GB RAM)
Calismayan: MRK-ERS-PER/BIS/YNT/SRV ve tum VPCS uclari. PC yerine switch SVI'lari DHCP istemcisi yapilir.

Asamalar: sifirdan deploy (sure olcumu) -> saglik raporu -> uctan uca (DHCP, relay, NAT, ACL) ->
guvenlik sertlestirme -> yedek + sapma -> F3 (CORE1 arizasi) -> F4 (DAG1 arizasi).
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
PROJ = LAB.parent / "network-automation-project"
PY = str(PROJ / ".venv" / "Scripts" / "python.exe")
ENVV = {**os.environ, "NET_CONSOLE_HOST": "127.0.0.1", "PYTHONIOENCODING": "utf-8", "LAB_CAPTURE": "1"}
NODES = ["SNR-RTR", "ISS-RTR", "FAB-RTR", "MRK-CORE1", "MRK-CORE2", "MRK-DAG1", "MRK-DAG2", "MRK-ERS-SAT", "FAB-ERS-1"]
OUT = LAB / "logs" / "big_test.txt"
checks = []


def run(args, cwd, timeout=3600):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=ENVV,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def log(text):
    print(text, flush=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


def check(label, ok):
    checks.append((label, bool(ok)))
    log(("GECTI  " if ok else "KALDI  ") + label)


def show(name, cmd):
    code = ("import sys; sys.path.insert(0, 'core/scripts'); import deploy; from validate import collect; "
            f"deploy.load_dotenv(); dev = next(d for d in deploy.load_inventory() if d['name'] == {name!r}); "
            f"print(collect(dev, [{cmd!r}])[{cmd!r}])")
    _, out = run([PY, "-c", code], PROJ)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {name}# {cmd} =====\n{out}\n")
    return out


def push(name, *lines):
    return run([PY, str(LAB / "_push.py"), name, *lines], PROJ)[1]


def ping(name, target):
    out = show(name, f"ping {target}")
    m = re.search(r"Success rate is (\d+) percent", out)
    return int(m.group(1)) if m else -1


def validate(only=NODES):
    code, out = run([PY, "core/scripts/validate.py", "--only", *only, "--partial"], PROJ)
    log(out)
    return code, out


def svi_ip(name, vlan):
    out = show(name, f"show ip interface brief | include Vlan{vlan}")
    m = re.search(r"Vlan\d+\s+(\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else None


def main():
    OUT.write_text("", encoding="utf-8")
    # ---------------- 0. kurulum ----------------
    for n in NODES:
        run([PY, "lab.py", "reset", n], LAB)
    run([PY, "lab.py", "start", *NODES], LAB)
    for n in NODES:
        log(run([PY, "console.py", "bootstrap", n], LAB)[1].strip().splitlines()[-1])

    # ---------------- 1. sifirdan config ----------------
    t0 = time.monotonic()
    code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--only", *NODES, "--workers", "5"], PROJ)
    secs = time.monotonic() - t0
    log(out)
    check(f"Sifirdan 9 cihaza Faz 1+2+3: {secs:.0f} sn, cikis kodu {code}", code == 0)
    log("Yakinsama icin 180 sn bekleniyor...")
    time.sleep(180)

    # ---------------- 2. saglik raporu ----------------
    code, out = validate()
    check(f"validate.py: 9 cihaz saglikli (cikis kodu {code})", code == 0)
    m = re.search(r"(\d+) OK, (\d+) HATA", out)
    log(f"   kontrol sayilari: {m.group(0) if m else '?'}")
    nb = show("MRK-CORE1", "show ip ospf neighbor")
    check("CORE1: 3 OSPF komsusu FULL (CORE2, DAG1, SNR)", nb.count("FULL") == 3)
    check("CORE1: 172.18.10.0/24 O IA (tunelden)", "inter area" in show("MRK-CORE1", "show ip route 172.18.10.0"))
    check("DAG1: default rota OSPF E2 (SNR default-information originate)", "O*E2" in show("MRK-DAG1", "show ip route ospf | include 0.0.0.0/0"))
    st = show("MRK-ERS-SAT", "show spanning-tree vlan 10")
    check("ERS-SAT VLAN 10: Gi0/0 Root FWD, Gi0/1 Altn BLK", bool(re.search(r"Gi0/0\s+Root FWD", st) and re.search(r"Gi0/1\s+Altn BLK", st)))
    check("ERS-SAT yonetim (Vlan90) -> HSRP VIP 172.16.90.1 ping", ping("MRK-ERS-SAT", "172.16.90.1") >= 60)

    # ---------------- 3. uctan uca: DHCP, relay, NAT, ACL ----------------
    log(push("MRK-ERS-SAT", "interface Vlan90", "shutdown", "no ip default-gateway", "interface Vlan10", "ip address dhcp", "no shutdown"))
    log(push("FAB-ERS-1", "no ip default-gateway", "interface Vlan110", "ip address dhcp"))
    time.sleep(75)
    sat_ip, fab_ip = svi_ip("MRK-ERS-SAT", 10), svi_ip("FAB-ERS-1", 110)
    check(f"DHCP: ERS-SAT Vlan10 istemcisi DAG1 havuzundan adres aldi -> {sat_ip}",
          bool(sat_ip and sat_ip.startswith("172.16.10.") and 100 <= int(sat_ip.split('.')[-1]) <= 200))
    check(f"DHCP relay (GRE ustunden): FAB-ERS-1 Vlan110 istemcisi adres aldi -> {fab_ip}",
          bool(fab_ip and fab_ip.startswith("172.18.10.") and 100 <= int(fab_ip.split('.')[-1]) <= 200))
    bind = show("MRK-DAG1", "show ip dhcp binding")
    check("DAG1 DHCP binding tablosunda iki kira", bool(sat_ip and fab_ip and sat_ip in bind and fab_ip in bind))

    check("SAT istemcisi -> gateway VIP 172.16.10.1", ping("MRK-ERS-SAT", "172.16.10.1") >= 60)
    check("SAT istemcisi -> internet 203.0.113.1 (NAT)", ping("MRK-ERS-SAT", "203.0.113.1") >= 60)
    nat = show("SNR-RTR", "show ip nat translations")
    check("SNR NAT tablosunda SAT istemcisinin cevirisi", bool(sat_ip and sat_ip in nat))
    check("A12: SAT istemcisi -> FAB istemcisi (tunel)", bool(fab_ip) and ping("MRK-ERS-SAT", fab_ip) >= 60)
    check("A2 benzeri: SAT -> VLAN 20 (172.16.20.1) ENGELLI", ping("MRK-ERS-SAT", "172.16.20.1") == 0)
    check("A5: SAT -> yonetim agi (172.16.90.2) ENGELLI", ping("MRK-ERS-SAT", "172.16.90.2") == 0)
    check("FAB istemcisi -> internet 203.0.113.1 (tunel + NAT)", ping("FAB-ERS-1", "203.0.113.1") >= 60)
    check("A11: FAB -> BIS agi (172.16.30.1) ENGELLI", ping("FAB-ERS-1", "172.16.30.1") == 0)
    acl = show("MRK-DAG1", "show access-lists ACL-V10-IN")
    check("ACL-V10-IN sayaclari artti (matches)", "matches" in acl)

    # ---------------- 4. guvenlik sertlestirme ----------------
    code, out = run([PY, "extensions/security-hardening/harden.py", "--only", *NODES], PROJ)
    log(out)
    check(f"harden.py 9 cihazda hatasiz (cikis kodu {code})", code == 0)
    time.sleep(120)
    code, out = validate()
    check(f"OSPF MD5 sonrasi tum komsuluklar yeniden FULL, rapor saglikli (cikis kodu {code})", code == 0)
    check("CORE1 Po1'de OSPF message-digest etkin", "Cryptographic authentication enabled" in show("MRK-CORE1", "show ip ospf interface Port-channel1"))
    ps = show("MRK-ERS-SAT", "show port-security")
    check("ERS-SAT: Gi0/2 ve Gi0/3'te Port Security (Restrict)", ps.count("Restrict") >= 2)
    sn = show("MRK-ERS-SAT", "show ip dhcp snooping")
    check("ERS-SAT: DHCP snooping VLAN 10'da etkin, uplink trusted", "snooping is enabled" in sn and "yes" in sn)
    check("ERS-SAT: kullanilmayan port kapali", "administratively down" in show("MRK-ERS-SAT", "show interfaces GigabitEthernet3/3 | include line protocol"))
    check("Sertlestirme sonrasi SAT istemcisi -> internet", ping("MRK-ERS-SAT", "203.0.113.1") >= 60)

    # ---------------- 5. yedek + sapma ----------------
    code, out = run([PY, "core/scripts/backup.py", "--only", *NODES, "--sanitize"], PROJ)
    log(out)
    check("backup.py 9 cihazi yedekledi", code == 0)
    code, out = run([PY, "extensions/drift/drift.py", "--only", *NODES], PROJ)
    log(out)
    check("drift.py: testte elle degistirilen ERS-SAT ve FAB-ERS-1 sapma olarak yakalandi",
          "MRK-ERS-SAT  SAPMA VAR" in out and "FAB-ERS-1    SAPMA VAR" in out)
    run([PY, "extensions/dashboard/dashboard.py"], PROJ)

    # ---------------- 6. F3: CORE1 arizasi ----------------
    run([PY, "lab.py", "stop", "MRK-CORE1"], LAB)
    time.sleep(60)
    check("F3: CORE1 kapaliyken SAT istemcisi -> internet (CORE2 uzerinden)", ping("MRK-ERS-SAT", "203.0.113.1") >= 60)
    check("F3: DAG1 komsulugu Vlan254 uzerinden suruyor", "Vlan254" in show("MRK-DAG1", "show ip ospf neighbor") )
    code, out = validate()
    check(f"F3: rapor CORE1'i sorunlu gosteriyor (cikis kodu {code})", code == 1 and "MRK-CORE1     " in out)
    run([PY, "lab.py", "start", "MRK-CORE1"], LAB)
    run([PY, "console.py", "wait", "MRK-CORE1"], LAB)
    time.sleep(150)
    code, out = validate()
    check(f"F3: CORE1 geri gelince rapor yeniden saglikli (cikis kodu {code})", code == 0)

    # ---------------- 7. F4: DAG1 arizasi ----------------
    run([PY, "lab.py", "stop", "MRK-DAG1"], LAB)
    time.sleep(60)
    sb = show("MRK-DAG2", "show standby brief")
    states = re.findall(r"^Vl\d+\s+\d+\s+\d+\s+(?:P\s+)?(\w+)", sb, re.M)
    check(f"F4: DAG1 kapaninca DAG2 yedi VLAN'da Active -> {states}", len(states) == 7 and set(states) == {"Active"})
    st = show("MRK-ERS-SAT", "show spanning-tree vlan 10")
    check("F4: ERS-SAT Gi0/1 forwarding'e gecti", bool(re.search(r"Gi0/1\s+Root FWD", st)))
    check("F4: SAT istemcisi -> internet (DAG2 uzerinden)", ping("MRK-ERS-SAT", "203.0.113.1") >= 60)

    run([PY, "lab.py", "stop"], LAB)
    passed = sum(ok for _, ok in checks)
    log(f"\nSONUC: {passed}/{len(checks)} kontrol gecti")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
