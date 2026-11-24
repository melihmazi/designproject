#!/usr/bin/env python3
"""Gercek GNS3 projesinde bes baglantida ayni anda paket kaydi alir (GNS3 API), kayit surerken gercek VPCS
uclarindan trafik uretir (DHCP, internet ping'i, ACL'e takilan ping), dosyalari docs/captures/gercek/ altina kopyalar.

    ..\network-automation-project\.venv\Scripts\python.exe gns3_capture.py
"""
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import gns3_acl

API = "http://127.0.0.1:3080/v2"
OUT = Path(__file__).resolve().parent.parent / "network-automation-project" / "docs" / "captures" / "gercek"
LINKS = {   # dosya adi: (uc A, uc B)
    "G1_SNR-Gi0-2_ISS-Gi0-0": ("SNR-RTR", "ISS-RTR"),
    "G2_ISS-Gi0-1_FAB-RTR-Gi0-0": ("ISS-RTR", "FAB-RTR"),
    "G3_CORE1-Gi0-0_CORE2-Gi0-0": ("MRK-CORE1", "MRK-CORE2"),
    "G4_ERS-SAT-Gi0-0_DAG1-Gi1-0": ("MRK-ERS-SAT", "MRK-DAG1"),
    "G5_ERS-SAT-Gi0-2_SAT-PC1": ("MRK-ERS-SAT", "SAT-PC1"),
}


def api(path, method="GET", data=None):
    req = urllib.request.Request(API + path, data=json.dumps(data or {}).encode() if method == "POST" else None,
                                 method=method, headers={"Content-Type": "application/json"})
    body = urllib.request.urlopen(req, timeout=60).read()
    return json.loads(body) if body else None


def main():
    pid = next(p["project_id"] for p in api("/projects") if p["status"] == "opened")
    project = next(p for p in api("/projects") if p["project_id"] == pid)
    nodes = {n["node_id"]: n for n in api(f"/projects/{pid}/nodes")}
    port = {n["name"]: n["console"] for n in nodes.values() if n["node_type"] == "vpcs"}
    links = api(f"/projects/{pid}/links")
    chosen = {}
    for fname, pair in LINKS.items():
        for l in links:
            names = [nodes[x["node_id"]]["name"] for x in l["nodes"]]
            if sorted(names) == sorted(pair) and fname not in chosen:
                chosen[fname] = l["link_id"]
    assert len(chosen) == len(LINKS), chosen
    for fname, lid in chosen.items():
        api(f"/projects/{pid}/links/{lid}/start_capture", "POST", {"capture_file_name": fname + ".pcap", "data_link_type": "DLT_EN10MB"})
    print("kayit basladi:", ", ".join(chosen), flush=True)
    time.sleep(12)                                        # periyodik protokoller (LACP, STP, HSRP, OSPF hello)
    for src, cmd, wait in [("SAT-PC1", "ip dhcp", 20), ("FAB-PC1", "ip dhcp", 25),
                           ("SAT-PC1", "ping 203.0.113.1 -c 5", 10), ("SAT-PC1", "ping 172.16.20.11 -c 3", 8),
                           ("SAT-PC1", "ping 172.16.50.12 -P 6 -p 80 -c 3", 10), ("FAB-PC1", "ping 172.16.50.12 -c 5", 10),
                           ("FAB-PC1", "ping 203.0.113.1 -c 3", 8)]:
        out = gns3_acl.vpcs(port[src], cmd, wait)
        print(f"  {src}> {cmd}: {len(out.splitlines())} satir", flush=True)
    time.sleep(10)
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, lid in chosen.items():
        api(f"/projects/{pid}/links/{lid}/stop_capture", "POST")
    time.sleep(2)
    src_dir = Path(project["path"]) / "project-files" / "captures"
    for fname in chosen:
        shutil.copy2(src_dir / (fname + ".pcap"), OUT / (fname + ".pcap"))
        print(f"{fname}.pcap  {(OUT / (fname + '.pcap')).stat().st_size} bayt")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
