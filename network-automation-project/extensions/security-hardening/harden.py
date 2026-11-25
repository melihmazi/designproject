#!/usr/bin/env python3
"""Guvenlik sertlestirme modulu (Modul 7). Cekirdege dokunmaz: kendi sablonlari, cekirdegin envanteri ve push'u.

    python extensions/security-hardening/harden.py --dry-run
    python extensions/security-hardening/harden.py --only MRK-ERS-SAT
    python extensions/security-hardening/harden.py                    # 13 cihaz
    python extensions/security-hardening/harden.py --rollback         # geri al

Ne yapar
  Erisim switch'leri : Port Security (sticky, en cok 2 MAC, restrict), DHCP Snooping (uplink'ler trusted,
                       Option 82 kapali), uc portlarda DHCP hiz siniri, kullanilmayan portlari kapatma.
  OSPF cihazlari     : transit arayuzlerde MD5 kimlik dogrulama (anahtar NET_OSPF_KEY ortam degiskeninden).

Bilerek yapilmayanlar
  - Native VLAN degisikligi (90 -> 999): tum trunk'larda ayni anda yapilmali; ayri ve planli bir is.
  - DAI: statik IP'li uclar (sunucular, yazici, KAP-1) icin ARP ACL gerektirir.
  - 802.1X: VPCS desteklemez.
OSPF MD5 notu: komsuluk, linkin iki ucu da yapilandirilana kadar duser; hepsini tek seferde bas.
"""
import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / "core" / "scripts"))
import deploy  # noqa: E402

OUT = HERE / "rendered"
ENV = Environment(loader=FileSystemLoader(str(HERE / "templates")), undefined=StrictUndefined,
                  trim_blocks=True, lstrip_blocks=True)
ALL_PORTS = [f"GigabitEthernet{s}/{p}" for s in range(4) for p in range(4)]


def expand(rng):
    m = re.match(r"(\D+)(\d+)/(\d+)(?:\s*-\s*(\d+))?$", rng.strip())
    return [f"{m.group(1)}{m.group(2)}/{n}" for n in range(int(m.group(3)), int(m.group(4) or m.group(3)) + 1)]


def context(dev):
    ctx = dict(dev)
    ctx["ospf_key"] = os.getenv("NET_OSPF_KEY", "")
    if dev["role"] == "access":
        used = {"GigabitEthernet0/0", "GigabitEthernet0/1"}
        for p in dev["access_ports"]:
            used |= set(expand(p["range"]))
        used |= set(filter(None, os.getenv("NET_RESERVED_PORTS", "").split(",")))   # orn. bant disi yonetim portu
        ctx["unused_ports"] = [p for p in ALL_PORTS if p not in used]
        ctx["user_vlans"] = ",".join(str(v["id"]) for v in dev["vlans"] if v["id"] != dev["net"]["native_vlan"])
    if dev["role"] == "branch_sw":
        keep = {"GigabitEthernet0/0", "GigabitEthernet0/1"} | set(filter(None, os.getenv("NET_RESERVED_PORTS", "").split(",")))
        ctx["unused_ports"] = [p for p in ALL_PORTS if p not in keep]
    if dev["role"] == "core":
        ctx["ospf_ifs"] = [f"Port-channel{po['id']}" for po in dev["port_channels"]] + [p["name"] for p in dev["routed_ports"]]
    if dev["role"] == "dag":
        ctx["ospf_ifs"] = ["Port-channel1", "Vlan254"]
    if dev["role"] == "snr":
        ctx["ospf_ifs"] = [l["name"] for l in dev["core_links"]] + ["Tunnel0"]
    if dev["role"] == "fab":
        ctx["ospf_ifs"] = ["Tunnel0"]
    return ctx


def render(dev, rollback):
    name = f"{dev['role']}_{'geri_al' if rollback else 'guvenlik'}.j2"
    text = ENV.get_template(name).render(**context(dev))
    return [l.rstrip() for l in text.splitlines() if l.strip() and not l.strip().startswith("!")]


def work(dev, dry_run, rollback):
    start = time.monotonic()
    try:
        lines = render(dev, rollback)
    except TemplateNotFound:
        return dev["name"], "ATLANDI (bu rol icin sertlestirme yok)", []
    key = os.getenv("NET_OSPF_KEY", "")
    OUT.mkdir(exist_ok=True)
    masked = [l.replace(key, "<NET_OSPF_KEY>") if key else l for l in lines]     # anahtar diske yazilmaz
    (OUT / f"{dev['name']}_{'geri_al' if rollback else 'guvenlik'}.cfg").write_text("\n".join(masked) + "\n", encoding="utf-8")
    if any("message-digest-key" in l for l in lines) and not key and not rollback:
        return dev["name"], "HATA: NET_OSPF_KEY tanimsiz (.env)", []
    if dry_run:
        return dev["name"], f"DRY-RUN ({len(lines)} satir)", []
    try:
        _, errors = deploy.push(dev, lines)
        return dev["name"], f"{'UYARI' if errors else 'TAMAM'} ({len(lines)} satir, {time.monotonic() - start:.0f} sn)", errors
    except Exception as exc:
        return dev["name"], f"HATA: {type(exc).__name__}: {str(exc).strip().splitlines()[0] if str(exc).strip() else ''}", []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    deploy.load_dotenv()
    devices = [d for d in deploy.load_inventory() if not args.only or d["name"] in args.only]
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
