#!/usr/bin/env python3
"""Gercek GNS3 projesinde dugum arizasi olcumu: bir VPCS ucundan surekli ping atarken bir dugumu durdurur,
en uzun kesintiyi olcer, sonra dugumu yeniden baslatir.

    python gns3_failover.py MRK-CORE1                 # SAT-PC1 -> internet
    python gns3_failover.py MRK-DAG1 --count 120
"""
import argparse
import json
import re
import socket
import sys
import threading
import time
import urllib.request

API = "http://127.0.0.1:3080/v2"


def api(path, method="GET"):
    req = urllib.request.Request(API + path, data=b"{}" if method == "POST" else None, method=method,
                                 headers={"Content-Type": "application/json"})
    body = urllib.request.urlopen(req, timeout=120).read()
    return json.loads(body) if body else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("node")
    ap.add_argument("--src", default="SAT-PC1")
    ap.add_argument("--dst", default="203.0.113.1")
    ap.add_argument("--count", type=int, default=110)
    ap.add_argument("--before", type=int, default=15, help="ariza oncesi saniye")
    ap.add_argument("--no-restart", action="store_true")
    a = ap.parse_args()
    pid = next(p["project_id"] for p in api("/projects") if p["status"] == "opened")
    nodes = {n["name"]: n for n in api(f"/projects/{pid}/nodes")}
    s = socket.create_connection(("127.0.0.1", nodes[a.src]["console"]), timeout=5)
    s.settimeout(1.0)
    s.sendall(b"\r")
    time.sleep(1)
    try:
        s.recv(65536)
    except socket.timeout:
        pass
    events, done = [], threading.Event()      # (zaman, basarili mi)

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
                    if len(events) >= a.count:
                        done.set()

    s.sendall(f"ping {a.dst} -c {a.count} -i 500\r".encode())
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    time.sleep(a.before)
    t_fail = time.monotonic()
    api(f"/projects/{pid}/nodes/{nodes[a.node]['node_id']}/stop", "POST")
    print(f"{a.node} durduruldu (ariza ani t=0)", flush=True)
    done.wait(a.count * 3 + 60)
    done.set()
    s.sendall(b"\x03")
    s.close()
    ok = [t for t, good in events if good]
    before = [t for t in ok if t < t_fail]
    after = [t for t in ok if t >= t_fail]
    lost = sum(1 for _, good in events if not good)
    # en uzun kesinti: ardisik iki basarili yanit arasindaki en buyuk bosluk
    gaps = [(b - x, x - t_fail) for x, b in zip(ok, ok[1:])]
    worst = max(gaps) if gaps else (0, 0)
    print(f"ping: {len(events)} gonderildi, {lost} kayip; ariza oncesi {len(before)} yanit, sonrasi {len(after)} yanit")
    if after:
        print(f"EN UZUN KESINTI: {worst[0]:.1f} sn (t={worst[1]:.0f} sn'de basladi)")
    else:
        print("ARIZA SONRASI HIC YANIT YOK (trafik geri gelmedi)")
    if not a.no_restart:
        nid = nodes[a.node]["node_id"]
        for _ in range(5):               # durdurma bitmeden gelen start 409 doner
            try:
                api(f"/projects/{pid}/nodes/{nid}/start", "POST")
                break
            except Exception:
                time.sleep(5)
        time.sleep(3)
        # GNS3 2.2.61 (Windows): dugum yeniden baslayinca konsol sarmalayicisi baglantilari dusuruyor; sifirlamak duzeltir
        api(f"/projects/{pid}/nodes/{nid}/console/reset", "POST")
        print(f"{a.node} yeniden baslatildi")


if __name__ == "__main__":
    main()
