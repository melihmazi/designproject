#!/usr/bin/env python3
"""GNS3'te calisan projedeki gercek VPCS uclarindan uctan uca kontrol (salt okunur: yalniz show ve ping).

    python gns3_vpcs.py            # GNS3 sunucusu 127.0.0.1:3080, proje acik ve dugumler baslamis olmali
"""
import json
import socket
import sys
import time
import urllib.request

API = "http://127.0.0.1:3080/v2"
INTERNET = "203.0.113.1"
# (kaynak uc, hedef, beklenen: True=gecer / False=engellenir, aciklama)
CASES = [
    ("SAT-PC1", "172.16.10.1", True, "kendi ag gecidi (HSRP sanal IP)"),
    ("SAT-PC1", "172.16.50.12", True, "Satis -> SNC-WEB"),
    ("SAT-PC1", INTERNET, True, "Satis -> internet (NAT)"),
    ("SAT-PC1", "172.16.20.11", False, "Satis -> Personel (ACL engeller)"),
    ("BIS-PC1", "172.16.10.11", True, "Bilgi Islem -> Satis"),
    ("BIS-PC1", "172.16.90.11", True, "Bilgi Islem -> ERS-SAT yonetim adresi (statik varsayilan rota duzeltmesi)"),
    ("FAB-PC1", "172.16.50.12", True, "Tesis -> SNC-WEB (GRE tuneli)"),
    ("FAB-PC1", INTERNET, True, "Tesis -> internet (tunel + NAT)"),
]


def vpcs(port, cmd, wait=12):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.settimeout(1.0)
    s.sendall(b"\r")
    time.sleep(0.5)
    s.sendall(cmd.encode() + b"\r")
    end, buf = time.monotonic() + wait, b""
    while time.monotonic() < end:
        try:
            buf += s.recv(4096)
        except socket.timeout:
            pass
    s.close()
    return buf.decode(errors="replace")


def main():
    sys.stdout.reconfigure(errors="replace")
    projects = json.load(urllib.request.urlopen(f"{API}/projects"))
    pid = next(p["project_id"] for p in projects if p["status"] == "opened")
    nodes = json.load(urllib.request.urlopen(f"{API}/projects/{pid}/nodes"))
    port = {n["name"]: n["console"] for n in nodes if n["node_type"] == "vpcs"}
    ok = 0
    for name in sorted({c[0] for c in CASES}):
        ip = vpcs(port[name], "show ip", 3)
        addr = next((l.split(":", 1)[1].strip() for l in ip.splitlines() if l.startswith("IP/MASK")), "?")
        if addr.startswith("0.0.0.0"):
            vpcs(port[name], "ip dhcp", 15)
            ip = vpcs(port[name], "show ip", 3)
            addr = next((l.split(":", 1)[1].strip() for l in ip.splitlines() if l.startswith("IP/MASK")), "?") + " (DHCP)"
        print(f"{name}: {addr}")
    for src, dst, expect, label in CASES:
        out = vpcs(port[src], f"ping {dst} -c 4", 14)
        got = out.count("bytes from")
        if expect is None:
            verdict = "BILGI"
        else:
            good = (got > 0) == expect
            ok += good
            verdict = "GECTI" if good else "KALDI"
        print(f"{verdict}  {src} -> {dst}  {got}/4 yanit   [{label}]")
    total = sum(1 for c in CASES if c[2] is not None)
    print(f"\n{ok}/{total} beklenen sonuc")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
