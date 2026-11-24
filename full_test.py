#!/usr/bin/env python3
"""Tam topoloji kosusu: 13 IOS cihazinin tamami + 17 uc cihaz (hosts.py), asama asama.

    python full_test.py deploy health backup e2e failover attack_before harden attack_after rollback
    python full_test.py all

On kosul: python up.py   (13 dugum acik ve bootstrap edilmis)
Her asamanin kontrol sonuclari logs/full_test.txt ve logs/full_test.json dosyalarina eklenir.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
PROJ = LAB.parent / "network-automation-project"
PY = str(PROJ / ".venv" / "Scripts" / "python.exe")
os.environ.update({"NET_CONSOLE_HOST": "127.0.0.1", "PYTHONIOENCODING": "utf-8",
                   "NET_RESERVED_PORTS": "GigabitEthernet3/3"})
sys.path.insert(0, str(PROJ / "core" / "scripts"))
sys.path.insert(0, str(LAB))
import deploy  # noqa: E402
from validate import collect  # noqa: E402

from hosts import Host  # noqa: E402
from lab import ENDPOINTS, NODES  # noqa: E402

deploy.load_dotenv()
DEV = {d["name"]: d for d in deploy.load_inventory()}
ALL = list(NODES)
OUT = LAB / "logs" / "full_test.txt"
JSN = LAB / "logs" / "full_test.json"
INTERNET = "203.0.113.1"
SERVERS = {"SNC-DHCP": ((), ()), "SNC-DNS": ((53,), (53,)), "SNC-WEB": ((80, 443), ()),
           "SNC-POSTA": ((25, 110, 143), ()), "SNC-DOSYA": ((21, 22), ())}
DHCP_HOSTS = ["SAT-PC2", "PER-PC2", "BIS-PC2", "MSF-DZ1", "YNT-PC1", "YNT-TEL1", "FAB-PC1"]
stage_name = "?"
checks = []


def log(text=""):
    print(text, flush=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


def check(label, ok, note=""):
    checks.append({"asama": stage_name, "kontrol": label, "gecti": bool(ok), "not": note})
    log(("GECTI  " if ok else "KALDI  ") + label + (f"   [{note}]" if note else ""))
    return bool(ok)


def run(args, cwd=PROJ, timeout=7200):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def show(name, cmd):
    try:
        out = collect(DEV[name], [cmd])[cmd]
    except Exception as exc:
        out = f"<<okunamadi: {type(exc).__name__}: {exc}>>"
    with OUT.open("a", encoding="utf-8") as f:
        f.write(f"\n----- {name}# {cmd} -----\n{out}\n")
    return out


def push(name, *lines):
    out, errors = deploy.push(DEV[name], list(lines), check=False)
    if errors:
        log(f"   push {name}: {errors}")
    return errors


def validate(only=None):
    args = [PY, "core/scripts/validate.py"] + (["--only", *only, "--partial"] if only else [])
    code, out = run(args)
    log(out)
    return code, out


def open_hosts(names=None):
    """Uc cihazlari ac. Statik olanlar hazir; DHCP olanlar icin .dhcp() cagrilmali."""
    hosts = {}
    for n in names or ENDPOINTS:
        tcp, udp = SERVERS.get(n, ((), ()))
        hosts[n] = Host(n, tcp=tcp, udp=udp)
    return hosts


def close_hosts(hosts):
    for h in hosts.values():
        h.close()


def dhcp_all(hosts, names):
    """DHCP'yi paralel yap: {isim: adres}"""
    res = {}
    threads = [threading.Thread(target=lambda n=n: res.__setitem__(n, hosts[n].dhcp())) for n in names if n in hosts]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return res


def in_pool(ip, prefix):
    return bool(ip and ip.startswith(prefix + ".") and 100 <= int(ip.split(".")[-1]) <= 200)


def during(host, dst, seconds, action, lead=6):
    """Surekli ping surerken 'action' calistir. (gonderilen, kayip, en uzun kesinti sn)"""
    box = {}
    t = threading.Thread(target=lambda: box.__setitem__("r", host.ping_series(dst, seconds)))
    t.start()
    time.sleep(lead)
    action()
    t.join()
    return box["r"]


# ====================================================================== asamalar
def st_deploy():
    t0 = time.monotonic()
    code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--workers", "7"])
    secs = time.monotonic() - t0
    log(out)
    check(f"Sifirdan 13 cihaza Faz 1+2+3 (dogrulama dahil): {secs:.0f} sn", code == 0, f"cikis kodu {code}")
    log("Yakinsama icin 240 sn bekleniyor...")
    time.sleep(240)
    t0 = time.monotonic()
    code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--workers", "7"])
    log(out[-3000:])
    check(f"Ikinci basis (idempotentlik): {time.monotonic() - t0:.0f} sn, hata yok", code == 0, f"cikis kodu {code}")
    time.sleep(120)


def st_health():
    code, out = validate()
    m = re.search(r"(\d+) OK, (\d+) HATA", out)
    check("validate.py: 13/13 cihaz saglikli", code == 0, m.group(0) if m else "")
    nb = "\n".join(show(n, "show ip ospf neighbor") for n in ("MRK-CORE1", "MRK-CORE2", "MRK-DAG1", "MRK-DAG2", "SNR-RTR", "FAB-RTR"))
    check("OSPF: 14 komsuluk girisinin tamami FULL", nb.count("FULL") == 14, f"{nb.count('FULL')} FULL")
    sb1, sb2 = show("MRK-DAG1", "show standby brief"), show("MRK-DAG2", "show standby brief")
    check("HSRP: DAG1 4 grupta, DAG2 3 grupta Active", len(re.findall(r"\sActive\s+local", sb1)) == 4 and len(re.findall(r"\sActive\s+local", sb2)) == 3)
    for sw, vlan in (("MRK-ERS-SAT", 10), ("MRK-ERS-PER", 20), ("MRK-ERS-BIS", 30), ("MRK-ERS-YNT", 40), ("MRK-ERS-SRV", 50)):
        st = show(sw, f"show spanning-tree vlan {vlan}")
        check(f"STP {sw} VLAN {vlan}: bir uplink Root FWD, digeri Altn BLK",
              bool(re.search(r"Gi0/[01]\s+Root FWD", st) and re.search(r"Gi0/[01]\s+Altn BLK", st)))


def st_backup():
    code, out = run([PY, "core/scripts/backup.py", "--sanitize", "--workers", "6"])
    log(out)
    check("backup.py: 13 cihaz yedeklendi", code == 0)
    code, out = run([PY, "extensions/drift/drift.py"])
    log(out)
    m = re.search(r"(\d+)/(\d+) cihaz uyumlu", out)
    check("drift.py: 13/13 cihaz sablonla uyumlu", bool(m) and m.group(1) == m.group(2) == "13", m.group(0) if m else "")
    run([PY, "extensions/config-history/commit_backups.py"])
    run([PY, "extensions/dashboard/dashboard.py"])


def acl_matrix(hosts, tag=""):
    sys.path.insert(0, str(PROJ / "extensions" / "tests"))
    import test_offline as T
    actor = {T.SAT: "SAT-PC1", T.PER: "PER-PC1", T.BIS: "BIS-PC1", T.MSF: "MSF-DZ1", T.FAB: "FAB-PC1"}
    ok_all = True
    for label, src, dst, proto, dport, expected in T.MATRIX:
        h = hosts[actor[src]]
        target = hosts[actor[dst]].ip if dst in actor else dst
        if not h.ip or not target:
            ok_all &= check(f"{tag}{label}", False, "ucun adresi yok")
            continue
        got = h.flow(target, proto, dport)
        if got != expected and expected:           # izinli akista ilk deneme ARP/yakinsama yuzunden dusebilir
            time.sleep(3)
            got = h.flow(target, proto, dport)
        ok_all &= check(f"{tag}{label}: beklenen {'GECER' if expected else 'ENGEL'}, gercek {'GECER' if got else 'ENGEL'}",
                        got == expected, f"{h.ip} -> {target}")
    return ok_all


def st_e2e(tag=""):
    hosts = open_hosts()
    try:
        leases = dhcp_all(hosts, DHCP_HOSTS)
        log(f"   DHCP kiralari: {leases}")
        prefix = {"SAT-PC2": "172.16.10", "PER-PC2": "172.16.20", "BIS-PC2": "172.16.30", "MSF-DZ1": "172.16.60",
                  "YNT-PC1": "172.16.40", "YNT-TEL1": "172.16.40", "FAB-PC1": "172.18.10"}
        for n in DHCP_HOSTS:
            check(f"{tag}DHCP {n}: {leases.get(n)}", in_pool(leases.get(n), prefix[n]), f"gw {hosts[n].gw}")
        check(f"{tag}FAB-PC1 kirasi relay ile geldi (giaddr 172.18.10.1)", hosts["FAB-PC1"].giaddr == "172.18.10.1", str(hosts["FAB-PC1"].giaddr))
        check(f"{tag}SAT-PC2 kirasi relay'siz (giaddr 0.0.0.0)", hosts["SAT-PC2"].giaddr == "0.0.0.0", str(hosts["SAT-PC2"].giaddr))
        bind = show("MRK-DAG1", "show ip dhcp binding")
        check(f"{tag}DAG1 binding tablosunda 7 kira", sum(1 for ip in leases.values() if ip and ip in bind) == 7)
        for n in ("SAT-PC1", "PER-PC1", "BIS-PC1", "BIS-YAZICI1", "KAP-1", "SNC-DHCP", "SNC-DNS", "SNC-WEB", "SNC-POSTA", "SNC-DOSYA"):
            check(f"{tag}{n} ({hosts[n].ip}) -> ag gecidi {hosts[n].gw}", hosts[n].ping(hosts[n].gw) > 0)
        check(f"{tag}Ayni VLAN: SAT-PC1 -> SAT-PC2", hosts["SAT-PC1"].ping(hosts["SAT-PC2"].ip or "0.0.0.0") > 0)
        check(f"{tag}SAT-PC1 -> internet {INTERNET} (NAT)", hosts["SAT-PC1"].ping(INTERNET) > 0)
        check(f"{tag}FAB-PC1 -> internet (tunel + NAT)", hosts["FAB-PC1"].ping(INTERNET) > 0)
        nat = show("SNR-RTR", "show ip nat translations")
        check(f"{tag}SNR NAT tablosunda SAT-PC1 ve FAB-PC1 cevirisi", "172.16.10.11" in nat and (hosts["FAB-PC1"].ip or "x") in nat)
        acl_matrix(hosts, tag)
        acl = show("MRK-DAG1", "show access-lists") + show("MRK-DAG2", "show access-lists") + show("FAB-RTR", "show access-lists")
        for name in ("ACL-V10-IN", "ACL-V20-IN", "ACL-V60-IN", "ACL-SRV-OUT", "ACL-V90-OUT", "ACL-FAB-IN"):
            blocks = re.findall(rf"Extended IP access list {name}\n((?:\s+\d+ .*\n?)+)", acl)
            check(f"{tag}{name} sayaclari artti", any("match" in b for b in blocks))
    finally:
        close_hosts(hosts)


def _settle(seconds, label):
    log(f"   {label}: {seconds} sn bekleniyor")
    time.sleep(seconds)


def drift_ok():
    run([PY, "core/scripts/backup.py", "--sanitize", "--workers", "6"])
    code, out = run([PY, "extensions/drift/drift.py"])
    log(out)
    m = re.search(r"(\d+)/(\d+) cihaz uyumlu", out)
    return (int(m.group(1)) if m else -1), out


def heal_after_reload():
    """IOSvL2 yeniden acilinca routed Port-channel aciklamalarini kaybeder (gercek projedeki kayitli
    konfigurasyonlarda da yok). Sapma denetimi bunu yakalar, deploy ayni sablonu basarak onarir."""
    n, out = drift_ok()
    lost = re.findall(r"EKSIK\s+\[interface Port-channel\d+\] description", out)
    other = [l for l in out.splitlines() if ("EKSIK" in l or "FAZLA" in l) and "description PO" not in l]
    check(f"Yeniden baslatma sonrasi sapma denetimi kaybolan Po aciklamalarini yakaladi ({len(lost)} satir), baska sapma yok",
          len(lost) > 0 and not other, f"{n}/13 uyumlu")
    code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--only", "MRK-CORE1", "MRK-DAG1", "--workers", "2"])
    log(out[-1500:])
    check("Onarim: deploy.py CORE1 ve DAG1'e ayni sablonu basti, hata yok", code == 0, f"cikis kodu {code}")
    time.sleep(60)
    n, out = drift_ok()
    check("Onarim sonrasi sapma raporu 13/13", n == 13, f"{n}/13")


def st_failover():
    hosts = open_hosts(["SAT-PC1", "BIS-PC1", "PER-PC1", "FAB-PC1", "SNC-WEB", "SNC-DNS"])
    try:
        sat, bis, fab = hosts["SAT-PC1"], hosts["BIS-PC1"], hosts["FAB-PC1"]
        check("On kosul: FAB-PC1 DHCP", in_pool(fab.dhcp(), "172.18.10"), str(fab.ip))
        check("On kosul: SAT-PC1 -> internet", sat.ping(INTERNET) > 0)

        # ---- F1: LACP uyesi kaybi ----
        r = during(sat, INTERNET, 40, lambda: push("MRK-CORE1", "interface GigabitEthernet0/0", "shutdown"))
        ec = show("MRK-CORE1", "show etherchannel summary")
        check("F1: CORE1 Gi0/0 kapali, Po1 tek uyeyle ayakta (RU, Gi0/1 P)", bool(re.search(r"Po1\(RU\).*Gi0/0\(D\).*Gi0/1\(P\)", ec)))
        check("F1: CORE1-CORE2 OSPF komsulugu kopmadi", bool(re.search(r"172\.20\.20\.2\s+\d+\s+FULL", show("MRK-CORE1", "show ip ospf neighbor"))))
        check(f"F1: surekli ping kaybi {r[1]}/{r[0]}, en uzun kesinti {r[2]:.1f} sn", r[2] <= 5)
        push("MRK-CORE1", "interface GigabitEthernet0/0", "no shutdown")
        _settle(45, "F1 geri alma")

        # ---- F2: tum demet kaybi ----
        r = during(sat, INTERNET, 60, lambda: push("MRK-CORE1", "interface range GigabitEthernet0/0 - 1", "shutdown"))
        rt = show("MRK-CORE1", "show ip route 172.20.20.2")
        check("F2: Po1 dusunce CORE1 -> CORE2 rotasi halkanin obur yonunden (DAG1, Po2)", "Port-channel2" in rt and "Port-channel1" not in rt)
        tr = show("MRK-CORE1", "traceroute 172.20.20.2")
        check("F2: traceroute DAG1 ve DAG2 uzerinden geciyor", "172.20.254.6" in tr and "172.20.254.14" in tr, " ".join(re.findall(r"\d+\.\d+\.\d+\.\d+", tr)[1:]))
        check(f"F2: surekli ping kaybi {r[1]}/{r[0]}, en uzun kesinti {r[2]:.1f} sn", r[2] <= 15)
        push("MRK-CORE1", "interface range GigabitEthernet0/0 - 1", "no shutdown")
        _settle(75, "F2 geri alma")
        check("F2: geri alinca Po1 yeniden RU, iki uye P", bool(re.search(r"Po1\(RU\).*Gi0/0\(P\).*Gi0/1\(P\)", show("MRK-CORE1", "show etherchannel summary"))))

        # ---- F5: erisim uplink kaybi ----
        r = during(sat, INTERNET, 40, lambda: push("MRK-DAG1", "interface GigabitEthernet1/0", "shutdown"))
        st = show("MRK-ERS-SAT", "show spanning-tree vlan 10")
        check("F5: ERS-SAT Gi0/1 Root FWD oldu", bool(re.search(r"Gi0/1\s+Root FWD", st)))
        check("F5: VLAN 10 HSRP active hala DAG1 (trafik Po2 L2 trunk'indan gecer)", bool(re.search(r"Vl10\s+10\s+\d+\s+P?\s*Active", show("MRK-DAG1", "show standby brief"))))
        mac = show("MRK-DAG1", "show mac address-table address 0200.0000.0001")
        check("F5: DAG1, SAT-PC1'in MAC'ini Po2 uzerinden ogrendi", "Po2" in mac)
        check(f"F5: surekli ping kaybi {r[1]}/{r[0]}, en uzun kesinti {r[2]:.1f} sn (RSTP)", r[2] <= 10)
        push("MRK-DAG1", "interface GigabitEthernet1/0", "no shutdown")
        _settle(45, "F5 geri alma")

        # ---- F8: sunucu uplink kaybi ----
        r = during(bis, "172.16.50.12", 40, lambda: push("MRK-DAG1", "interface GigabitEthernet1/2", "shutdown"))
        st = show("MRK-ERS-SRV", "show spanning-tree vlan 50")
        check("F8: ERS-SRV Gi0/1 Root FWD oldu", bool(re.search(r"Gi0/1\s+Root FWD", st)))
        check("F8: SAT-PC1 -> SNC-WEB tcp/80 hala acik", sat.tcp("172.16.50.12", 80) == "open")
        check(f"F8: BIS-PC1 -> SNC-WEB surekli ping kaybi {r[1]}/{r[0]}, en uzun kesinti {r[2]:.1f} sn (RSTP)", r[2] <= 10)
        push("MRK-DAG1", "interface GigabitEthernet1/2", "no shutdown")
        _settle(45, "F8 geri alma")

        # ---- F7: tunel arizasi ----
        push("SNR-RTR", "interface Tunnel0", "shutdown")
        _settle(30, "F7")
        check("F7: Tesis LAN rotasi CORE1'den kalkti", "not in table" in show("MRK-CORE1", "show ip route 172.18.10.0"))
        check("F7: Merkez ici trafik etkilenmedi (SAT-PC1 -> SNC-WEB, internet)", sat.tcp("172.16.50.12", 80) == "open" and sat.ping(INTERNET) > 0)
        check("F7: FAB-PC1 -> Merkez erisemiyor", fab.ping("172.16.50.12") == 0)
        push("SNR-RTR", "interface Tunnel0", "no shutdown")
        _settle(75, "F7 geri alma")
        check("F7: geri alinca FAB-PC1 -> SNC-WEB tcp/80", fab.tcp("172.16.50.12", 80) == "open")

        # ---- F6: ISS / WAN kaybi ----
        push("SNR-RTR", "interface GigabitEthernet0/2", "shutdown")
        _settle(45, "F6")
        check("F6: default rota CORE1'de OSPF'ten kalkti", "not in table" in show("MRK-CORE1", "show ip route 0.0.0.0") or "0.0.0.0" not in show("MRK-CORE1", "show ip route ospf | include 0.0.0.0/0"))
        check("F6: SNR Tunnel0 line protocol down", bool(re.search(r"Tunnel0 is \S+, line protocol is down", show("SNR-RTR", "show interfaces Tunnel0 | include line protocol"))))
        check("F6: internet kesildi (SAT-PC1)", sat.ping(INTERNET) == 0)
        check("F6: Tesis izole (FAB-PC1 -> SNC-WEB yok)", fab.ping("172.16.50.12") == 0)
        check("F6: Merkez ici trafik suruyor (SAT-PC1 -> SNC-WEB)", sat.tcp("172.16.50.12", 80) == "open")
        push("SNR-RTR", "interface GigabitEthernet0/2", "no shutdown")
        _settle(120, "F6 geri alma")
        check("F6: geri alinca internet ve Tesis geri geldi", sat.ping(INTERNET) > 0 and fab.ping("172.16.50.12") > 0)

        # ---- F3: Core dugum arizasi ----
        r = during(sat, INTERNET, 100, lambda: run([PY, "lab.py", "stop", "MRK-CORE1"], LAB))
        check(f"F3: CORE1 durdu, SAT-PC1 -> internet kendiliginden geri geldi; kayip {r[1]}/{r[0]}, en uzun kesinti {r[2]:.1f} sn (OSPF dead 40 sn + SPF)", sat.ping(INTERNET) > 0 and r[2] <= 70)
        nb = show("MRK-DAG1", "show ip ospf neighbor")
        check("F3: DAG1 komsulugu Vlan254 uzerinden suruyor", bool(re.search(r"FULL.*Vlan254", nb)))
        code, out = validate()
        check("F3: saglik raporu CORE1'i kirmizi gosteriyor", code == 1 and "MRK-CORE1" in out)
        run([PY, "lab.py", "start", "MRK-CORE1"], LAB)
        run([PY, "console.py", "wait", "MRK-CORE1"], LAB)
        _settle(180, "F3 CORE1 geri geliyor")

        # ---- F4: Dagitim dugum arizasi ----
        r = during(sat, INTERNET, 100, lambda: run([PY, "lab.py", "stop", "MRK-DAG1"], LAB))
        sb = show("MRK-DAG2", "show standby brief")
        states = re.findall(r"^Vl\d+\s+\d+\s+\d+\s+(?:P\s+)?(\w+)", sb, re.M)
        check("F4: DAG1 durunca DAG2 yedi VLAN'da Active", len(states) == 7 and set(states) == {"Active"}, str(states))
        check("F4: ERS-SAT Gi0/1 forwarding", bool(re.search(r"Gi0/1\s+Root FWD", show("MRK-ERS-SAT", "show spanning-tree vlan 10"))))
        check(f"F4: SAT-PC1 -> internet kendiliginden geri geldi; kayip {r[1]}/{r[0]}, en uzun kesinti {r[2]:.1f} sn (HSRP 10 sn + OSPF dead 40 sn)", sat.ping(INTERNET) > 0 and r[2] <= 70)
        with Host("SAT-PC2") as pc2:
            got = pc2.dhcp(timeout=15)
        check("F4 gozlemi: DAG1 kapaliyken DHCP yok (tek DHCP sunucusu DAG1)", got is None, f"kira: {got}")
        run([PY, "lab.py", "start", "MRK-DAG1"], LAB)
        run([PY, "console.py", "wait", "MRK-DAG1"], LAB)
        _settle(240, "F4 DAG1 geri geliyor")
        code, out = validate()
        check("Tum demolardan sonra saglik raporu yeniden 13/13", code == 0)
        sb = show("MRK-DAG1", "show standby brief")
        check("DAG1 geri gelince preempt ile 4 grupta yeniden Active", len(re.findall(r"\sActive\s+local", sb)) == 4)
        heal_after_reload()
    finally:
        close_hosts(hosts)


def _attack(tag, expect_blocked):
    hosts = open_hosts(["SAT-PC1", "SAT-PC2"])
    try:
        attacker, victim = hosts["SAT-PC1"], hosts["SAT-PC2"]
        attacker.ping(attacker.gw)                         # saldirganin gercek MAC'i once ogrenilsin
        # --- kacak DHCP sunucusu ---
        attacker.start_rogue_dhcp("172.16.10.250")
        victim.avoid = attacker.ip
        lease = victim.dhcp()
        rogue_seen = attacker.ip in victim.offers
        log(f"   {tag}: kurbanin gordugu Offer sunuculari {victim.offers}; kacak sunucu {attacker.rogue_hits} Discover gordu; gercek kira {lease}")
        if expect_blocked:
            check(f"{tag}: kacak DHCP Offer'i kurbana ULASMADI (DHCP snooping)", not rogue_seen, f"offers={victim.offers}")
            check(f"{tag}: Discover guvenilmeyen porta hic iletilmedi (kacak sunucu {attacker.rogue_hits} Discover gordu)", attacker.rogue_hits == 0)
            check(f"{tag}: kurban gercek sunucudan kira alabildi", in_pool(lease, "172.16.10"), str(lease))
        else:
            check(f"{tag}: kacak DHCP Offer'i kurbana ulasti (acik gosterildi)", rogue_seen, f"offers={victim.offers}")
        attacker.rogue = None
        # --- MAC tasmasi ---
        push("MRK-ERS-SAT", "do clear mac address-table dynamic interface GigabitEthernet0/2")
        attacker.mac_flood(60)
        time.sleep(3)
        mt = show("MRK-ERS-SAT", "show mac address-table interface GigabitEthernet0/2")
        learned = len(re.findall(r"^\s*10\s+[0-9a-f.]{14}\s+(?:DYNAMIC|STATIC)", mt, re.M))
        ps = show("MRK-ERS-SAT", "show port-security interface GigabitEthernet0/2")
        viol = re.search(r"Security Violation Count\s*:\s*(\d+)", ps)
        if expect_blocked:
            check(f"{tag}: MAC tasmasi engellendi (portta ogrenilen MAC {learned} <= 2)", learned <= 2, f"ihlal sayaci {viol.group(1) if viol else '?'}")
            check(f"{tag}: Port Security ihlal sayaci artti", bool(viol) and int(viol.group(1)) > 0)
            check(f"{tag}: port kapanmadi (restrict), mesru uc calisiyor", attacker.ping(attacker.gw) > 0)
        else:
            check(f"{tag}: MAC tasmasi CAM tablosunu doldurdu (portta {learned} MAC)", learned >= 40)
    finally:
        close_hosts(hosts)


def st_attack_before():
    _attack("Sertlestirme oncesi", expect_blocked=False)


def st_harden():
    code, out = run([PY, "extensions/security-hardening/harden.py", "--workers", "7"])
    log(out)
    check("harden.py 13 cihazda hatasiz", code == 0, f"cikis kodu {code}")
    _settle(150, "OSPF MD5 sonrasi yakinsama")
    code, out = validate()
    check("Sertlestirme sonrasi saglik raporu 13/13 (OSPF MD5 ile 14 komsuluk FULL)", code == 0)
    check("CORE1 Po1'de OSPF MD5 etkin", "Cryptographic authentication enabled" in show("MRK-CORE1", "show ip ospf interface Port-channel1"))
    for sw in ("MRK-ERS-SAT", "MRK-ERS-PER", "MRK-ERS-BIS", "MRK-ERS-YNT", "MRK-ERS-SRV", "FAB-ERS-1"):
        sn = show(sw, "show ip dhcp snooping")
        ps = show(sw, "show port-security")
        check(f"{sw}: DHCP snooping etkin, uc portlarda Port Security (Restrict)", "snooping is enabled" in sn and "Restrict" in ps)
    check("ERS-SAT: kullanilmayan port kapali", "administratively down" in show("MRK-ERS-SAT", "show interfaces GigabitEthernet3/2 | include line protocol"))


def st_attack_after():
    _attack("Sertlestirme sonrasi", expect_blocked=True)
    st_e2e("Sertlestirilmis agda ")


def st_rollback():
    code, out = run([PY, "extensions/security-hardening/harden.py", "--rollback", "--workers", "7"])
    log(out)
    check("harden.py --rollback 13 cihazda hatasiz", code == 0, f"cikis kodu {code}")
    _settle(150, "geri alma sonrasi yakinsama")
    code, out = validate()
    check("Geri alma sonrasi saglik raporu 13/13", code == 0)
    check("CORE1 Po1'de OSPF kimlik dogrulama kalkti", "authentication enabled" not in show("MRK-CORE1", "show ip ospf interface Port-channel1"))
    ps = show("MRK-ERS-SAT", "show port-security")
    check("ERS-SAT: Port Security kalkti", "Restrict" not in ps)
    check("ERS-SAT: DHCP snooping kapali", "snooping is disabled" in show("MRK-ERS-SAT", "show ip dhcp snooping"))
    check("ERS-SAT: kullanilmayan port yeniden acik", "administratively down" not in show("MRK-ERS-SAT", "show interfaces GigabitEthernet3/2 | include line protocol"))
    for sw in ("MRK-ERS-PER", "MRK-ERS-BIS", "MRK-ERS-YNT", "MRK-ERS-SRV", "FAB-ERS-1"):
        check(f"{sw}: DHCP snooping kapali", "snooping is disabled" in show(sw, "show ip dhcp snooping"))
    n, out = drift_ok()
    check("Geri alma sonrasi sapma raporu: 13/13 sablonla uyumlu", n == 13, f"{n}/13")



V6 = "2001:db8:acad"
V6_NET = "2001:db8:ffff::1"


def st_ipv6():
    code, out = run([PY, "extensions/ipv6/ipv6.py", "--workers", "7"])
    log(out)
    check("ipv6.py 7 L3 cihazda hatasiz", code == 0, f"cikis kodu {code}")
    _settle(120, "OSPFv3 yakinsama")
    code, out = run([PY, "extensions/ipv6/ipv6.py", "--verify"])
    log(out)
    check("OSPFv3: 14 komsuluk FULL, her L3 cihazdan tum IPv6 loopback ve internet ping", code == 0)
    check("FAB-RTR: IPv6 varsayilan rota tunelden (OI ::/0)", bool(re.search(r"OI\s+::/0", show("FAB-RTR", "show ipv6 route ospf"))))
    hosts = open_hosts(["SAT-PC1", "PER-PC1", "BIS-PC1", "MSF-DZ1", "SNC-WEB", "FAB-PC1"])
    try:
        want = {"SAT-PC1": "10", "PER-PC1": "20", "BIS-PC1": "30", "MSF-DZ1": "60", "SNC-WEB": "50", "FAB-PC1": "110"}
        for n, v in want.items():
            addr = hosts[n].slaac()
            check(f"SLAAC {n}: {addr}", bool(addr) and addr.startswith(f"{V6}:{v}:"), f"RA oneki {hosts[n].ra_prefix}")
        sat, per, bis, msf, web, fab = (hosts[n] for n in want)
        check("SAT-PC1 -> ag gecidi (DAG1 global adresi)", sat.ping6(f"{V6}:10::2") > 0)
        check("SAT-PC1 -> SNC-WEB (IPv6)", sat.ping6(web.ip6) > 0)
        check("SAT-PC1 -> internet 2001:db8:ffff::1", sat.ping6(V6_NET) > 0)
        check("FAB-PC1 -> SNC-WEB (GRE tuneli IPv6 tasiyor)", fab.ping6(web.ip6) > 0)
        check("FAB-PC1 -> internet (IPv6)", fab.ping6(V6_NET) > 0)
        check("IPv6 ACL: BIS-PC1 -> SAT-PC1 GECER", bis.ping6(sat.ip6) > 0)
        check("IPv6 ACL: SAT-PC1 -> PER-PC1 ENGEL", sat.ping6(per.ip6) == 0)
        check("IPv6 ACL: MSF-DZ1 -> SNC-WEB ENGEL", msf.ping6(web.ip6) == 0)
        check("IPv6 ACL: MSF-DZ1 -> internet GECER", msf.ping6(V6_NET) > 0)
        check("IPv6 ACL: MSF-DZ1 -> DAG1 Loopback ENGEL", msf.ping6(f"{V6}:ffff::3") == 0)
        check("IPv6 RA tercihi: SAT-PC1 ag gecidi DAG1, MSF-DZ1 ag gecidi DAG2 (HSRP active ile ayni)",
              sat.gw6_rank == 2 and msf.gw6_rank == 2 and sat.gw6_mac != msf.gw6_mac, f"{sat.gw6_mac} / {msf.gw6_mac}")
        check("IPv6 ACL: FAB-PC1 -> BIS-PC1 ENGEL", fab.ping6(bis.ip6) == 0)
        check("IPv4 etkilenmedi: SAT-PC1 -> internet", sat.ping(INTERNET) > 0)
    finally:
        close_hosts(hosts)
    code, out = validate()
    check("Dual-stack agda IPv4 saglik raporu hala 13/13", code == 0)


def st_ipv6_rollback():
    code, out = run([PY, "extensions/ipv6/ipv6.py", "--rollback", "--workers", "7"])
    log(out)
    check("ipv6.py --rollback hatasiz", code == 0, f"cikis kodu {code}")
    left = []
    for n in ("MRK-CORE1", "MRK-DAG1", "SNR-RTR", "ISS-RTR", "FAB-RTR"):
        rc = show(n, "show running-config | include ipv6")
        left += [f"{n}: {l.strip()}" for l in rc.splitlines() if "ipv6" in l and "#" not in l and not l.strip().startswith(("no ipv6 cef", "ipv6 ioam", "ipv6 multicast rpf"))]
    check("Geri almadan sonra running-config icinde IPv6 satiri kalmadi", not left, "; ".join(left[:6]))
    _settle(60, "geri alma sonrasi")
    code, out = validate()
    check("IPv6 geri alindiktan sonra saglik raporu 13/13", code == 0)


def st_monitor():
    import yaml
    from lab import mgmt_ports
    targets = LAB / "monitor_targets.yaml"
    targets.write_text(yaml.safe_dump({n: f"127.0.0.1:{mgmt_ports(n)[1]}" for n in NODES}), encoding="utf-8")
    os.environ["NET_SNMP_STATION"] = "10.0.2.2"
    mon = [PY, "extensions/monitoring/monitor.py", "--targets", str(targets)]
    code, out = run([PY, "extensions/monitoring/monitor.py", "--setup"])
    log(out)
    check("monitor.py --setup: 13 cihaza SNMP config basildi", code == 0)
    for f in ("monitor_latest.json", "monitor_events.jsonl"):
        (PROJ / "reports" / f).unlink(missing_ok=True)
    code, out = run(mon)
    log(out)
    check("SNMP yoklamasi: 13/13 cihaz OK, alarm yok", code == 0 and "13/13 cihaz OK" in out)
    push("MRK-CORE1", "interface GigabitEthernet0/0", "shutdown")
    time.sleep(20)
    code, out = run(mon)
    log(out)
    check("Link kapatilinca ALARM: CORE1 Gi0/0 (lab linkleri UDP oldugu icin karsi uc down gormez)", code == 1 and "ALARM  MRK-CORE1: LINK - Gi0/0" in out)
    check("Olay kaydi: Gi0/0 up -> down", "Gi0/0 up -> down" in out)
    run([PY, "extensions/dashboard/dashboard.py"])
    (PROJ / "reports" / "dashboard_alarm.html").write_text((PROJ / "reports" / "dashboard.html").read_text(encoding="utf-8"), encoding="utf-8")
    push("MRK-CORE1", "interface GigabitEthernet0/0", "no shutdown")
    time.sleep(45)
    code, out = run(mon)
    log(out)
    check("Link acilinca alarm kalkti, 13/13 OK", code == 0 and "13/13 cihaz OK" in out)
    run([PY, "extensions/dashboard/dashboard.py"])


STAGES = {"deploy": st_deploy, "health": st_health, "backup": st_backup, "e2e": st_e2e, "failover": st_failover,
          "attack_before": st_attack_before, "harden": st_harden, "attack_after": st_attack_after, "rollback": st_rollback,
          "ipv6": st_ipv6, "ipv6_rollback": st_ipv6_rollback, "monitor": st_monitor}


def main():
    global stage_name
    wanted = sys.argv[1:]
    if wanted == ["all"]:
        wanted = list(STAGES)
    if not wanted or any(w not in STAGES for w in wanted):
        sys.exit(__doc__)
    for stage_name in wanted:
        log(f"\n================ ASAMA: {stage_name}  ({time.strftime('%H:%M:%S')}) ================")
        t0 = time.monotonic()
        try:
            STAGES[stage_name]()
        except Exception as exc:
            check(f"{stage_name}: asama istisnayla kesildi", False, f"{type(exc).__name__}: {exc}")
            import traceback
            log(traceback.format_exc())
        log(f"--- {stage_name} bitti: {time.monotonic() - t0:.0f} sn")
    old = json.loads(JSN.read_text(encoding="utf-8")) if JSN.exists() else []
    old = [c for c in old if c["asama"] not in wanted] + checks
    JSN.write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf-8")
    passed = sum(c["gecti"] for c in checks)
    log(f"\nSONUC ({' '.join(wanted)}): {passed}/{len(checks)} kontrol gecti")
    for c in checks:
        if not c["gecti"]:
            log(f"   KALDI: [{c['asama']}] {c['kontrol']}  {c['not']}")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
