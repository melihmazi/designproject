#!/usr/bin/env python3
"""Gercek GNS3 projesinde yol haritasi 12.3 (ACL tablosu A1-A12) ve 12.4 (DHCP) testleri; gercek VPCS uclarindan.
ACL sayaclari testten once ve sonra okunur (artis = kuralin gercekten eslestigi).

    ..\network-automation-project\.venv\Scripts\python.exe gns3_acl.py
"""
import json
import re
import socket
import sys
import time
import urllib.request

import gns3_show

API = "http://127.0.0.1:3080/v2"
INTERNET = "203.0.113.1"
SRV = {"DHCP": "172.16.50.10", "DNS": "172.16.50.11", "WEB": "172.16.50.12", "DOSYA": "172.16.50.14"}
DHCP_POOL = {"SAT-PC1": "172.16.10.", "FAB-PC1": "172.18.10.", "MSF-DZ1": "172.16.60."}


def vpcs(port, cmd, wait):
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


def addr(port):
    out = vpcs(port, "show ip", 3)
    m = re.search(r"IP/MASK\s*:\s*(\d+\.\d+\.\d+\.\d+)/", out)
    return m.group(1) if m else "0.0.0.0"


def probe(port, dst, proto="icmp", dport=0):
    """(gecti mi, ozet). Gecti = hedeften yanit geldi (echo reply, TCP baglanti/RST ya da hedefin kendi ICMP'si)."""
    opt = {"icmp": "", "tcp": f" -P 6 -p {dport}", "udp": f" -P 17 -p {dport}"}[proto]
    out = vpcs(port, f"ping {dst}{opt} -c 4", 16)
    lines = [l.strip() for l in out.splitlines() if re.search(r"seq=|timeout|prohibited|unreachable|Connect|SendData|Close", l)]
    prohibited = "prohibited" in out
    answered = len(re.findall(r"bytes from|Connect\s+\d+@.*seq=\d+ ttl|RST returned|Port unreachable|port unreachable", out))
    passed = answered > 0 and not prohibited
    return passed, (lines[0] if lines else "(cikti yok)")[:110]


def counters():
    out = {}
    for dev in ("MRK-DAG1", "MRK-DAG2", "FAB-RTR"):
        text = gns3_show.show(dev, "show access-lists")["show access-lists"]
        acl = None
        for line in text.splitlines():
            m = re.match(r"Extended IP access list (\S+)", line)
            if m:
                acl = m.group(1)
            m = re.search(r"\((\d+) match", line)
            if acl and m:
                out[(dev, acl)] = out.get((dev, acl), 0) + int(m.group(1))
    return out


def main():
    sys.stdout.reconfigure(errors="replace")
    projects = json.load(urllib.request.urlopen(f"{API}/projects"))
    pid = next(p["project_id"] for p in projects if p["status"] == "opened")
    port = {n["name"]: n["console"] for n in json.load(urllib.request.urlopen(f"{API}/projects/{pid}/nodes"))
            if n["node_type"] == "vpcs"}
    ok = total = 0

    print("== 12.4 DHCP ==")
    for name, prefix in DHCP_POOL.items():
        out = vpcs(port[name], "ip dhcp", 25)
        ip = addr(port[name])
        last = int(ip.split(".")[-1])
        good = ip.startswith(prefix) and 100 <= last <= 200
        ok += good
        total += 1
        dora = (re.search(r"D\S*O\S*R\S*A.*", out) or re.search(r"IP \d.*", out))
        print(f"{'GECTI' if good else 'KALDI'}  {name} ip dhcp -> {ip}   [{dora.group(0).strip()[:70] if dora else ''}]")

    ip = {n: addr(port[n]) for n in ("SAT-PC1", "PER-PC1", "BIS-PC1", "FAB-PC1", "MSF-DZ1")}
    print("\nUc adresleri: " + ", ".join(f"{k}={v}" for k, v in ip.items()))
    before = counters()

    cases = [
        ("A1", "BIS-PC1", ip["SAT-PC1"], "icmp", 0, True, "BIS -> SAT ping"),
        ("A2", "SAT-PC1", ip["PER-PC1"], "icmp", 0, False, "SAT -> PER ping (10->20 yasak)"),
        ("A3", "SAT-PC1", SRV["WEB"], "tcp", 80, True, "SAT -> SNC-WEB tcp/80"),
        ("A4", "SAT-PC1", SRV["DOSYA"], "icmp", 0, True, "SAT -> SNC-DOSYA ping"),
        ("A4b", "SAT-PC1", SRV["DOSYA"], "tcp", 22, False, "SAT -> SNC-DOSYA tcp/22 (servis disi port)"),
        ("A5", "SAT-PC1", "172.16.90.11", "icmp", 0, False, "SAT -> switch yonetimi (10->90 yasak)"),
        ("A6", "BIS-PC1", "172.16.90.11", "icmp", 0, True, "BIS -> switch yonetimi"),
        ("A7", "MSF-DZ1", SRV["DNS"], "udp", 53, True, "misafir -> SNC-DNS udp/53"),
        ("A8", "MSF-DZ1", SRV["WEB"], "icmp", 0, False, "misafir -> SNC-WEB ping"),
        ("A9", "MSF-DZ1", INTERNET, "icmp", 0, True, "misafir -> internet"),
        ("A10", "FAB-PC1", SRV["WEB"], "icmp", 0, True, "Tesis -> SNC-WEB"),
        ("A11", "FAB-PC1", ip["BIS-PC1"], "icmp", 0, False, "Tesis -> BIS (ACL-FAB-IN)"),
        ("A12", "SAT-PC1", ip["FAB-PC1"], "icmp", 0, True, "SAT -> Tesis ping"),
    ]
    print("\n== 12.3 ACL tablosu ==")
    for tag, src, dst, proto, dport, expect, label in cases:
        passed, line = probe(port[src], dst, proto, dport)
        good = passed == expect
        ok += good
        total += 1
        print(f"{'GECTI' if good else 'KALDI'}  {tag:4} {label:45} beklenen {'gecer' if expect else 'engel'}  | {line}")

    after = counters()
    print("\n== ACL sayaclari (once -> sonra) ==")
    for key in sorted(after):
        b, a = before.get(key, 0), after[key]
        print(f"{key[0]:9} {key[1]:13} {b:6} -> {a:6}  {'(+%d)' % (a - b) if a > b else ''}")
    print(f"\n{ok}/{total} beklenen sonuc")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
