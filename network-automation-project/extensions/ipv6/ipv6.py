#!/usr/bin/env python3
"""IPv6 dual-stack: mevcut IPv4'un ustune OSPFv3 + IPv6 ACL (yol haritasi Bolum 10, modul 6).

Cekirdege dokunmaz: envanteri okur, kendi sablonlarini (templates/) kendi adres planiyla (plan.yaml) uretir,
config'i cekirdegin deploy.push() fonksiyonuyla basar. IPv4 yapisi degismez; --rollback her seyi geri alir.

    python extensions/ipv6/ipv6.py --dry-run
    python extensions/ipv6/ipv6.py                 # 7 L3 cihaza bas (core, dag, snr, iss, fab)
    python extensions/ipv6/ipv6.py --verify        # OSPFv3 komsuluklari + loopback ping'leri
    python extensions/ipv6/ipv6.py --rollback

Tasarim:
  * VLAN N -> 2001:db8:acad:N::/64, DAG1 ::2, DAG2 ::3. Uclar SLAAC ile adres alir.
  * Varsayilan ag gecidi: IPv4'te HSRP active olan DAG, RA'da "High" tercih yayinlar (HSRP surumu degistirilmez).
  * Transit linklerde global adres yok; OSPFv3 link-local uzerinden calisir. Alanlar IPv4 ile ayni (0 / 100 / 300).
  * GRE tuneli IPv6'yi da tasir; Area 300 yine totally stubby.
  * IPv6'da NAT yok: ISS-RTR sirket /48'ine statik rota tutar.
"""
import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / "core" / "scripts"))
import deploy  # noqa: E402

OUT = HERE / "rendered"
ENV = Environment(loader=FileSystemLoader(str(HERE / "templates")), undefined=StrictUndefined,
                  trim_blocks=True, lstrip_blocks=True)
PLAN = yaml.safe_load((HERE / "plan.yaml").read_text(encoding="utf-8"))
# OSPFv3 komsuluk beklentisi: cihaz -> FULL olmasi gereken komsu sayisi (IPv4'teki 14 girisin aynisi)
EXPECTED_NEIGHBORS = {"MRK-CORE1": 3, "MRK-CORE2": 3, "MRK-DAG1": 2, "MRK-DAG2": 2, "SNR-RTR": 3, "FAB-RTR": 1}


def context(dev):
    ctx = dict(dev, v6=PLAN)
    if "router_id" in dev:
        ctx["rid"] = dev["router_id"].rsplit(".", 1)[1]
    if dev["role"] == "core":
        ctx["transit"] = [f"Port-channel{po['id']}" for po in dev["port_channels"]] + [p["name"] for p in dev["routed_ports"]]
    if dev["role"] == "dag":
        ctx["transit"] = ["Port-channel1", "Vlan254"]
    if dev["role"] == "snr":
        ctx["transit"] = [l["name"] for l in dev["core_links"]]
    return ctx


def render(dev, rollback=False):
    text = ENV.get_template(f"{dev['role']}_{'geri_al' if rollback else 'ipv6'}.j2").render(**context(dev))
    return [l.rstrip() for l in text.splitlines() if l.strip() and not l.strip().startswith("!")]


def work(dev, dry_run, rollback):
    start = time.monotonic()
    try:
        lines = render(dev, rollback)
    except TemplateNotFound:
        return dev["name"], "ATLANDI (L2 cihaz: IPv6 icin degisiklik gerekmez)", []
    OUT.mkdir(exist_ok=True)
    (OUT / f"{dev['name']}_{'geri_al' if rollback else 'ipv6'}.cfg").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if dry_run:
        return dev["name"], f"DRY-RUN ({len(lines)} satir)", []
    try:
        _, errors = deploy.push(dev, lines, check=not rollback)      # geri almada "satir var mi" dogrulamasi anlamsiz
        return dev["name"], f"{'UYARI' if errors else 'TAMAM'} ({len(lines)} satir, {time.monotonic() - start:.0f} sn)", errors
    except Exception as exc:
        return dev["name"], f"HATA: {type(exc).__name__}: {str(exc).strip().splitlines()[0] if str(exc).strip() else ''}", []


def verify(devices):
    """OSPFv3 komsuluklari ve her L3 cihazdan tum IPv6 loopback'lerine ping. Hata sayisini dondurur."""
    from validate import collect
    by = {d["name"]: d for d in devices}
    loopbacks = {n: f"{PLAN['loopbacks']}::{by[n]['router_id'].rsplit('.', 1)[1]}" for n in EXPECTED_NEIGHBORS if n in by}
    bad = 0
    for name, want in EXPECTED_NEIGHBORS.items():
        if name not in by:
            continue
        cmds = ["show ipv6 ospf neighbor"] + [f"ping ipv6 {ip}" for n, ip in loopbacks.items() if n != name] + [f"ping ipv6 {PLAN['internet']}"]
        out = collect(by[name], cmds)
        full = out[cmds[0]].count("FULL")
        ok = full == want
        bad += not ok
        print(f"{name:12} OSPFv3 komsu {full}/{want} FULL  {'OK' if ok else 'HATA'}")
        for c in cmds[1:]:
            m = re.search(r"Success rate is (\d+) percent", out[c])
            rate = int(m.group(1)) if m else -1
            if rate < 60:
                bad += 1
                print(f"   HATA  {c}: basari %{rate}")
    print(f"\nIPv6 dogrulama: {'TAMAM' if not bad else str(bad) + ' HATA'}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--verify", action="store_true", help="config basma; yalniz dogrula")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    deploy.load_dotenv()
    devices = [d for d in deploy.load_inventory() if not args.only or d["name"] in args.only]
    if args.verify:
        sys.exit(1 if verify(devices) else 0)
    failed = warned = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for name, status, errors in pool.map(lambda d: work(d, args.dry_run, args.rollback), devices):
            print(f"{name:12} {status}")
            for e in errors:
                print("    " + e)
            failed += status.startswith("HATA")
            warned += status.startswith("UYARI")
    sys.exit(1 if failed else (2 if warned else 0))


if __name__ == "__main__":
    main()
