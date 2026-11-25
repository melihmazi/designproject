#!/usr/bin/env python3
"""Gercek GNS3 projesinde baglanti arizasi senaryolari (F1, F2, F5, F8, F7, F6): gercek VPCS uclarindan
surekli ping atarken arayuz kapatilir, kayip ve en uzun kesinti olculur, sonra arayuz geri acilir.
Dugum arizalari (F3, F4) icin gns3_failover.py kullanilir.

    ..\network-automation-project\.venv\Scripts\python.exe gns3_links.py            # hepsi
    ..\network-automation-project\.venv\Scripts\python.exe gns3_links.py F5 F8      # secilenler
Parolalar gns3_run.py'deki gibi okunur (ekrana yazilmaz).
"""
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parent / "network-automation-project" / "core" / "scripts"))
os.environ["NET_CONSOLE_HOST"] = "127.0.0.1"
os.environ.pop("NET_NO_ENABLE", None)
import deploy
import gns3_run

API = "http://127.0.0.1:3080/v2"
INTERNET, WEB = "203.0.113.1", "172.16.50.12"
DEV = {d["name"]: d for d in deploy.load_inventory()}
results = []


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def check(label, ok):
    results.append(ok)
    log(("GECTI  " if ok else "KALDI  ") + label)


def push(name, *lines):
    user, pw, en = gns3_run.creds("rtr" if name in gns3_run.RTR else "sw")
    os.environ.update(NET_USER=user, NET_PASS=pw, NET_ENABLE=en)
    _, errors = deploy.push(DEV[name], list(lines), check=False)
    if errors:
        log(f"   push {name}: {errors}")


def consoles():
    projects = json.load(urllib.request.urlopen(f"{API}/projects"))
    pid = next(p["project_id"] for p in projects if p["status"] == "opened")
    nodes = json.load(urllib.request.urlopen(f"{API}/projects/{pid}/nodes"))
    return {n["name"]: n["console"] for n in nodes if n["node_type"] == "vpcs"}


PORT = consoles()


def series(src, dst, count, action=None, lead=8):
    """count adet ping (0,5 sn aralik); action ping surerken calisir. (gonderilen, kayip, en uzun kesinti sn)"""
    s = socket.create_connection(("127.0.0.1", PORT[src]), timeout=5)
    s.settimeout(1.0)
    s.sendall(b"\r")
    time.sleep(1)
    try:
        s.recv(65536)
    except socket.timeout:
        pass
    events, done = [], threading.Event()

    def reader():
        buf = ""
        while not done.is_set():
            try:
                buf += s.recv(4096).decode(errors="replace")
            except socket.timeout:
                continue
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if "icmp_seq" in line:
                    events.append((time.monotonic(), "bytes from" in line))
                    if len(events) >= count:
                        done.set()

    s.sendall(f"ping {dst} -c {count} -i 500\r".encode())
    threading.Thread(target=reader, daemon=True).start()
    if action:
        time.sleep(lead)
        action()
    done.wait(count * 3 + 60)
    done.set()
    s.sendall(b"\x03")
    time.sleep(1)
    s.close()
    ok = [t for t, good in events if good]
    lost = sum(1 for _, good in events if not good)
    gap = max((b - a for a, b in zip(ok, ok[1:])), default=0.0) if lost else 0.0
    if lost and not ok:
        gap = float("inf")
    return len(events), lost, gap


def ping(src, dst):
    sent, lost, _ = series(src, dst, 6)
    return sent - lost


def settle(sec, label):
    log(f"   {label}: {sec} sn bekleniyor")
    time.sleep(sec)


def recover(label, tests, limit=420):
    """Geri alma sonrasi tum (src, dst) ciftleri yanit verene kadar yoklar; sureyi raporlar."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        if all(ping(s, d) > 0 for s, d in tests):
            check(f"{label} ({time.monotonic() - t0:.0f} sn icinde)", True)
            return
        time.sleep(5)
    check(f"{label} ({limit} sn icinde donmedi)", False)


def measured(tag, src, dst, count, dev, iface, limit, restore_wait):
    r = series(src, dst, count, lambda: push(dev, f"interface {iface}", "shutdown"))
    check(f"{tag}: {dev} {iface} kapatildi; {src} -> {dst} kayip {r[1]}/{r[0]}, en uzun kesinti {r[2]:.1f} sn", r[2] <= limit)
    push(dev, f"interface {iface}", "no shutdown")
    settle(restore_wait, f"{tag} geri alma")
    check(f"{tag}: geri alinca {src} -> {dst} yanit veriyor", ping(src, dst) > 0)


def f1():
    measured("F1", "SAT-PC1", INTERNET, 160, "MRK-CORE1", "GigabitEthernet0/0", 5, 45)


def f2():
    measured("F2", "SAT-PC1", INTERNET, 200, "MRK-CORE1", "range GigabitEthernet0/0 - 1", 15, 75)


def f5():
    measured("F5", "SAT-PC1", INTERNET, 160, "MRK-DAG1", "GigabitEthernet1/0", 10, 45)


def f8():
    measured("F8", "BIS-PC1", WEB, 160, "MRK-DAG1", "GigabitEthernet1/2", 10, 45)


def f7():
    push("SNR-RTR", "interface Tunnel0", "shutdown")
    settle(30, "F7")
    check("F7: tunel kapaliyken FAB-PC1 -> SNC-WEB yok", ping("FAB-PC1", WEB) == 0)
    check("F7: Merkez etkilenmedi (SAT-PC1 -> SNC-WEB ve internet)", ping("SAT-PC1", WEB) > 0 and ping("SAT-PC1", INTERNET) > 0)
    push("SNR-RTR", "interface Tunnel0", "no shutdown")
    recover("F7: geri alinca FAB-PC1 -> SNC-WEB", [("FAB-PC1", WEB)])


def f6():
    push("SNR-RTR", "interface GigabitEthernet0/2", "shutdown")
    settle(45, "F6")
    check("F6: WAN kapaliyken internet yok (SAT-PC1)", ping("SAT-PC1", INTERNET) == 0)
    check("F6: Tesis izole (FAB-PC1 -> SNC-WEB yok)", ping("FAB-PC1", WEB) == 0)
    check("F6: Merkez ici trafik suruyor (SAT-PC1 -> SNC-WEB)", ping("SAT-PC1", WEB) > 0)
    push("SNR-RTR", "interface GigabitEthernet0/2", "no shutdown")
    recover("F6: geri alinca internet ve Tesis geri geldi", [("SAT-PC1", INTERNET), ("FAB-PC1", WEB)])


ALL = {"F1": f1, "F2": f2, "F5": f5, "F8": f8, "F7": f7, "F6": f6}

if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    for tag in (sys.argv[1:] or list(ALL)):
        log(f"==== {tag} ====")
        ALL[tag]()
    print(f"\n{sum(results)}/{len(results)} kontrol gecti")
    sys.exit(0 if all(results) else 1)
