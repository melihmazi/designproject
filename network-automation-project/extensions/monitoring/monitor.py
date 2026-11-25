#!/usr/bin/env python3
"""Self-hosted izleme: 13 cihazi SNMP (v2c, salt okunur) ile yoklar, alarm uretir (yol haritasi Bolum 10, modul 5).

Bulut servisi yok, ek sunucu yok: tek Python sureci. Cikti reports/monitor_latest.json dosyasidir; web panosu
(extensions/dashboard) bu dosyayi "Canli izleme" bolumunde gosterir.

    python extensions/monitoring/monitor.py --setup          # cihazlara SNMP config'i bas (snmp.j2)
    python extensions/monitoring/monitor.py                  # tek yoklama
    python extensions/monitoring/monitor.py --watch 30       # 30 sn'de bir; durum degisince ALARM satiri
    python extensions/monitoring/monitor.py --rollback       # SNMP config'ini kaldir

Hedef adresler: varsayilan olarak envanterden (Loopback0 / yonetim SVI'si, UDP 161). Baska bir yol icin
--targets DOSYA.yaml  ({cihaz: "adres:port"}); laboratuvar bant disi portlari boyle verir.
Topluluk dizgisi .env icindeki NET_SNMP_RO'dan okunur, diske yazilmaz. Izin verilen istasyon: NET_SNMP_STATION
(varsayilan yonetim agi 172.16.90.0/24).

Alarm kurallari:
  * cihaz SNMP'ye yanit vermiyor                          -> ERISILEMIYOR
  * envanterde kablolu gorunen port / Port-channel / Tunnel0 "up" degil  -> LINK
  * iki yoklama arasinda herhangi bir arayuz up -> down    -> olay kaydi (reports/monitor_events.jsonl)
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / "core" / "scripts"))
import deploy  # noqa: E402

REPORTS = PROJECT / "reports"
LATEST = REPORTS / "monitor_latest.json"
EVENTS = REPORTS / "monitor_events.jsonl"
ENV = Environment(loader=FileSystemLoader(str(HERE)), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
OID = {"uptime": "1.3.6.1.2.1.1.3.0", "name": "1.3.6.1.2.1.1.5.0", "descr": "1.3.6.1.2.1.2.2.1.2",
       "admin": "1.3.6.1.2.1.2.2.1.7", "oper": "1.3.6.1.2.1.2.2.1.8", "cpu": "1.3.6.1.4.1.9.9.109.1.1.1.1.6"}
SHORT = {"GigabitEthernet": "Gi", "Port-channel": "Po", "Loopback": "Lo", "Tunnel": "Tu", "Vlan": "Vl"}


def short(ifname):
    for long_, s in SHORT.items():
        if ifname.startswith(long_):
            return s + ifname[len(long_):]
    return ifname


def default_target(dev):
    """Gercek ortamda izleme istasyonu yonetim agindadir: L3 cihazlar Loopback0, L2 cihazlar yonetim SVI'si."""
    ip = dev.get("router_id") or dev.get("mgmt_ip") or dev["net"]["wan"]["iss_to_snr"]
    return f"{ip}:161"


def critical_ports(devices, data):
    """cihaz -> 'up' olmasi beklenen arayuzler (envanterdeki kablolar + demetler + tunel)."""
    out = {d["name"]: set() for d in devices}
    for a, pa, b, pb in data.get("links", []):
        out.setdefault(a, set()).add(pa)
        out.setdefault(b, set()).add(pb)
    for d in devices:
        if d["role"] == "core":
            out[d["name"]] |= {f"Po{po['id']}" for po in d["port_channels"]}
        if d["role"] == "dag":
            out[d["name"]] |= {"Po1", "Po2"}
        if d["role"] in ("snr", "fab"):
            out[d["name"]].add("Tu0")
    return out


# ------------------------------------------------------------------ SNMP
async def poll_device(engine, target, community):
    from pysnmp.hlapi.v3arch.asyncio import (CommunityData, ContextData, ObjectIdentity, ObjectType,
                                             UdpTransportTarget, bulk_walk_cmd, get_cmd)
    host, port = target.rsplit(":", 1)
    transport = await UdpTransportTarget.create((host, int(port)), timeout=4, retries=2)
    auth, ctx = CommunityData(community, mpModel=1), ContextData()
    err, status, _, binds = await get_cmd(engine, auth, transport, ctx,
                                          ObjectType(ObjectIdentity(OID["uptime"])), ObjectType(ObjectIdentity(OID["name"])))
    if err or status:
        raise RuntimeError(str(err or status.prettyPrint()))
    res = {"uptime_sn": int(binds[0][1]) // 100, "sysname": str(binds[1][1]), "arayuzler": {}}
    cols = {}
    for key in ("descr", "admin", "oper", "cpu"):
        cols[key] = {}
        async for err, status, _, binds in bulk_walk_cmd(engine, auth, transport, ctx, 0, 20,
                                                         ObjectType(ObjectIdentity(OID[key])), lexicographicMode=False):
            if err or status:
                break
            for oid, val in binds:
                cols[key][str(oid).rsplit(".", 1)[1]] = val
    for idx, name in cols["descr"].items():
        res["arayuzler"][short(str(name))] = {"admin": int(cols["admin"].get(idx, 0)), "oper": int(cols["oper"].get(idx, 0))}
    cpu = [int(v) for v in cols["cpu"].values()]
    res["cpu"] = max(cpu) if cpu else None
    return res


async def poll_all(targets, community):
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
    engine = SnmpEngine()

    async def one(name, target):
        try:
            return name, await asyncio.wait_for(poll_device(engine, target, community), 60)
        except Exception as exc:
            return name, {"hata": f"{type(exc).__name__}: {exc}"[:120]}

    out = dict(await asyncio.gather(*(one(n, t) for n, t in targets.items())))
    engine.close_dispatcher()
    return out


def evaluate(polled, critical, previous):
    """Ham yoklama -> rapor sozlugu + (yeni olaylar)."""
    now = datetime.now().isoformat(timespec="seconds")
    report, events = {"zaman": now, "cihazlar": {}, "alarmlar": []}, []
    for name, data in polled.items():
        if "hata" in data:
            report["cihazlar"][name] = {"durum": "ERISILEMIYOR", "hata": data["hata"]}
            report["alarmlar"].append({"cihaz": name, "tur": "ERISILEMIYOR", "ayrinti": data["hata"]})
            if previous.get(name, {}).get("durum") not in (None, "ERISILEMIYOR"):
                events.append({"zaman": now, "cihaz": name, "olay": "cihaz erisilemez oldu"})
            continue
        ifs = data["arayuzler"]
        down = sorted(p for p in critical.get(name, ()) if ifs.get(p, {}).get("oper") != 1)
        for p in down:
            report["alarmlar"].append({"cihaz": name, "tur": "LINK", "ayrinti": f"{p} up degil"})
        old = previous.get(name, {}).get("arayuzler", {})
        for p, st in ifs.items():
            was = old.get(p, {}).get("oper")
            if was is not None and was != st["oper"]:
                events.append({"zaman": now, "cihaz": name, "olay": f"{p} {'up' if was == 1 else 'down'} -> {'up' if st['oper'] == 1 else 'down'}"})
        if previous.get(name, {}).get("durum") == "ERISILEMIYOR":
            events.append({"zaman": now, "cihaz": name, "olay": "cihaz yeniden erisilebilir"})
        report["cihazlar"][name] = {"durum": "ALARM" if down else "OK", "uptime_sn": data["uptime_sn"], "cpu": data["cpu"],
                                   "up": sum(1 for s in ifs.values() if s["oper"] == 1), "toplam": len(ifs),
                                   "kritik_down": down, "arayuzler": ifs}
    return report, events


def poll_once(targets, community, critical):
    previous = json.loads(LATEST.read_text(encoding="utf-8")).get("cihazlar", {}) if LATEST.exists() else {}
    report, events = evaluate(asyncio.run(poll_all(targets, community)), critical, previous)
    REPORTS.mkdir(exist_ok=True)
    LATEST.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    if events:
        with EVENTS.open("a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return report, events


def print_report(report, events):
    for name, d in report["cihazlar"].items():
        if d["durum"] == "ERISILEMIYOR":
            print(f"{name:12} ERISILEMIYOR  {d['hata']}")
        else:
            up = f"{d['uptime_sn'] // 3600}sa{d['uptime_sn'] % 3600 // 60:02}dk"
            print(f"{name:12} {d['durum']:6} uptime {up:>8}  CPU {str(d['cpu']) + '%' if d['cpu'] is not None else '-':>4}  "
                  f"arayuz {d['up']}/{d['toplam']} up" + (f"  DOWN: {', '.join(d['kritik_down'])}" if d["kritik_down"] else ""))
    for e in events:
        print(f"OLAY   {e['zaman']} {e['cihaz']}: {e['olay']}")
    for a in report["alarmlar"]:
        print(f"ALARM  {a['cihaz']}: {a['tur']} - {a['ayrinti']}")
    ok = sum(1 for d in report["cihazlar"].values() if d["durum"] == "OK")
    print(f"\n{ok}/{len(report['cihazlar'])} cihaz OK, {len(report['alarmlar'])} alarm | {LATEST}")


def setup(devices, rollback, workers=6):
    from concurrent.futures import ThreadPoolExecutor
    community = os.getenv("NET_SNMP_RO", "")
    station = os.getenv("NET_SNMP_STATION", "172.16.90.0 0.0.0.255")
    if not community and not rollback:
        sys.exit("NET_SNMP_RO tanimsiz (.env)")

    def work(dev):
        text = ENV.get_template("snmp_geri_al.j2" if rollback else "snmp.j2").render(community=community, station=station, **dev)
        lines = [l.rstrip() for l in text.splitlines() if l.strip() and not l.strip().startswith("!")]
        try:
            _, errors = deploy.push(dev, lines, check=False)        # topluluk dizgisi dogrulama ciktisina dusmesin
            return dev["name"], "UYARI" if errors else "TAMAM", errors
        except Exception as exc:
            return dev["name"], f"HATA: {type(exc).__name__}", []

    failed = 0
    with ThreadPoolExecutor(workers) as pool:
        for name, status, errors in pool.map(work, devices):
            print(f"{name:12} {status}")
            for e in errors:
                print("    " + e.replace(community, "<NET_SNMP_RO>") if community else e)
            failed += status != "TAMAM"
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setup", action="store_true", help="SNMP config'ini cihazlara bas")
    ap.add_argument("--rollback", action="store_true", help="SNMP config'ini kaldir")
    ap.add_argument("--watch", type=int, default=0, metavar="SANIYE", help="bu aralikla surekli yokla")
    ap.add_argument("--targets", default=None, help="{cihaz: 'adres:port'} YAML dosyasi")
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    deploy.load_dotenv()
    devices = [d for d in deploy.load_inventory() if not args.only or d["name"] in args.only]
    if args.setup or args.rollback:
        sys.exit(1 if setup(devices, args.rollback) else 0)
    community = os.getenv("NET_SNMP_RO", "")
    if not community:
        sys.exit("NET_SNMP_RO tanimsiz (.env)")
    targets = {d["name"]: default_target(d) for d in devices}
    if args.targets:
        override = yaml.safe_load(Path(args.targets).read_text(encoding="utf-8"))
        targets = {n: override.get(n, t) for n, t in targets.items()}
    data = yaml.safe_load((PROJECT / "core" / "inventory" / "devices.yaml").read_text(encoding="utf-8"))
    critical = critical_ports(devices, data)
    while True:
        report, events = poll_once(targets, community, critical)
        if args.watch:
            ok = sum(1 for d in report["cihazlar"].values() if d["durum"] == "OK")
            print(f"{report['zaman']}  {ok}/{len(report['cihazlar'])} OK, {len(report['alarmlar'])} alarm", flush=True)
            for e in events:
                print(f"   OLAY  {e['cihaz']}: {e['olay']}", flush=True)
            for a in report["alarmlar"]:
                print(f"   ALARM {a['cihaz']}: {a['tur']} - {a['ayrinti']}", flush=True)
            time.sleep(args.watch)
        else:
            print_report(report, events)
            sys.exit(1 if report["alarmlar"] else 0)


if __name__ == "__main__":
    main()
