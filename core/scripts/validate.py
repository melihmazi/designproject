#!/usr/bin/env python3
"""Ag Saglik Raporu: canli durumu devices.yaml'daki beklenen durumla karsilastirir.

    python core/scripts/validate.py                              # 13 cihaz, tam topoloji
    python core/scripts/validate.py --only MRK-DAG1 MRK-DAG2 --partial
    python core/scripts/validate.py --details                    # yalniz sorunlu degil, tum kontroller

Kontroller: erisim, CDP kablolama, EtherChannel, OSPF komsuluk, HSRP rolleri, GRE tuneli.
--partial: secilmeyen cihazlara bakan beklentiler ATLANDI sayilir (kucuk lab parcasi icin).
Cikti: konsol tablosu + reports/health_YYYYMMDD_HHMMSS.json.  Cikis kodu: 0 saglikli, 1 sorun var.
"""
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deploy  # noqa: E402

OK, FAIL, SKIP = "OK", "HATA", "ATLANDI"
SHORT = (("GigabitEthernet", "Gi"), ("Port-channel", "Po"), ("Vlan", "Vl"), ("Tunnel", "Tu"), ("Loopback", "Lo"))


def short(intf):
    intf = intf.strip().replace(" ", "")
    for long, abbr in SHORT:
        if intf.startswith(long):
            return abbr + intf[len(long):]
    return intf


# ------------------------------------------------------------------ toplama
def collect(dev, commands, attempts=3):
    """Cihaza baglanir, komutlarin ham ciktisini {komut: cikti} olarak dondurur."""
    from netmiko import ConnectHandler
    last = None
    for _ in range(attempts):
        try:
            deploy.wake_console(dev["console_host"], dev["console_port"])
            with ConnectHandler(**deploy.conn_params(dev)) as conn:
                if not conn.check_enable_mode():
                    conn.enable()
                return {c: conn.send_command(c, read_timeout=90) for c in commands}
        except Exception as exc:
            last = exc
            time.sleep(5)
    raise last


# ------------------------------------------------------------------ ayristirma
def parse_cdp(text):
    """show cdp neighbors detail -> {yerel port: (komsu adi, komsu portu)}"""
    out = {}
    for block in text.split("-------------------------")[1:]:
        dev = re.search(r"Device ID:\s*(\S+)", block)
        ports = re.search(r"Interface:\s*(\S+),\s*Port ID \(outgoing port\):\s*(\S+)", block)
        if dev and ports:
            out[short(ports.group(1))] = (dev.group(1).split(".")[0], short(ports.group(2)))
    return out


def parse_etherchannel(text):
    """show etherchannel summary -> {po no: (bayraklar, {uye: bayrak})}"""
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\s+Po\d+\((\w+)\)\s+\S+\s*(.*)", line)
        if m:
            out[int(m.group(1))] = (m.group(2), dict(re.findall(r"(\S+?)\((\w+)\)", m.group(3))))
    return out


def parse_ospf(text):
    """show ip ospf neighbor -> {(router-id, arayuz): durum}"""
    out = {}
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 6 and re.match(r"\d+\.\d+\.\d+\.\d+$", p[0]):
            out[(p[0], short(p[-1]))] = p[2].split("/")[0]
    return out


def parse_hsrp(text):
    """show standby brief -> {vlan: durum}"""
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*Vl(\d+)\s+\d+\s+\d+\s+(?:P\s+)?(\w+)", line)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


# ------------------------------------------------------------------ kontroller
def build_checks(dev, raw, inv, selected, partial):
    name, checks = dev["name"], []
    names = {d["name"] for d in inv["devices"]}
    rid = {d["name"]: d.get("router_id") for d in inv["devices"]}
    exp = inv.get("expected", {})

    def add(kontrol, durum, beklenen, gercek):
        checks.append({"cihaz": name, "kontrol": kontrol, "durum": durum, "beklenen": beklenen, "gercek": gercek})

    def out_of_scope(peer):
        return partial and peer not in selected

    # --- CDP kablolama ---
    cdp = parse_cdp(raw["show cdp neighbors detail"])
    for a, pa, b, pb in inv["links"]:
        for me, my_port, peer, peer_port in ((a, pa, b, pb), (b, pb, a, pa)):
            if me != name:
                continue
            want = f"{peer} {peer_port}"
            if out_of_scope(peer):
                add(f"CDP {my_port}", SKIP, want, "kapsam disi")
                continue
            got = cdp.get(my_port)
            add(f"CDP {my_port}", OK if got == (peer, peer_port) else FAIL, want,
                f"{got[0]} {got[1]}" if got else "komsu yok")

    # --- EtherChannel ---
    if name in exp.get("etherchannel", {}):
        ec = parse_etherchannel(raw["show etherchannel summary"])
        for e in exp["etherchannel"][name]:
            peer = next((b if a == name else a for a, pa, b, pb in inv["links"]
                         if (a == name and pa == e["members"][0]) or (b == name and pb == e["members"][0])), None)
            want = f"Po{e['po']}({e['flags']}) " + " ".join(f"{m}(P)" for m in e["members"])
            if out_of_scope(peer):
                add(f"EtherChannel Po{e['po']}", SKIP, want, "kapsam disi")
                continue
            flags, members = ec.get(e["po"], ("yok", {}))
            good = flags == e["flags"] and all(members.get(m) == "P" for m in e["members"])
            add(f"EtherChannel Po{e['po']}", OK if good else FAIL, want,
                f"Po{e['po']}({flags}) " + " ".join(f"{m}({f})" for m, f in members.items()))

    # --- OSPF ---
    if name in exp.get("ospf", {}):
        ospf = parse_ospf(raw["show ip ospf neighbor"])
        for e in exp["ospf"][name]:
            want = f"{e['peer']} FULL ({e['intf']})"
            if out_of_scope(e["peer"]):
                add(f"OSPF {e['peer']}", SKIP, want, "kapsam disi")
                continue
            state = ospf.get((rid[e["peer"]], e["intf"]))
            add(f"OSPF {e['peer']}", OK if state == "FULL" else FAIL, want, state or "komsuluk yok")

    # --- HSRP ---
    if dev["role"] == "dag":
        peer = next(d["name"] for d in inv["devices"] if d["role"] == "dag" and d["name"] != name)
        hsrp = parse_hsrp(raw["show standby brief"])
        for s in inv["network"]["svis"]:
            want = "Active" if s["active"] == name else "Standby"
            if out_of_scope(peer):
                add(f"HSRP Vlan{s['vlan']}", SKIP, want, "kapsam disi")
                continue
            got = hsrp.get(s["vlan"], "yok")
            add(f"HSRP Vlan{s['vlan']}", OK if got == want else FAIL, want, got)

    # --- Tunel ---
    if name in exp.get("tunnel", {}):
        t = exp["tunnel"][name]
        if out_of_scope(t["peer"]):
            add(t["intf"], SKIP, "up/up", "kapsam disi")
        else:
            m = re.search(r"is (.+?), line protocol is (\w+)", raw[f"show interfaces {t['intf']}"])
            got = f"{m.group(1)}/{m.group(2)}" if m else "arayuz yok"
            add(t["intf"], OK if got == "up/up" else FAIL, "up/up", got)

    assert name in names
    return checks


def commands_for(dev, inv):
    cmds = ["show cdp neighbors detail"]
    exp = inv.get("expected", {})
    if dev["name"] in exp.get("etherchannel", {}):
        cmds.append("show etherchannel summary")
    if dev["name"] in exp.get("ospf", {}):
        cmds.append("show ip ospf neighbor")
    if dev["role"] == "dag":
        cmds.append("show standby brief")
    if dev["name"] in exp.get("tunnel", {}):
        cmds.append(f"show interfaces {exp['tunnel'][dev['name']]['intf']}")
    return cmds


def check_device(dev, inv, selected, partial):
    try:
        raw = collect(dev, commands_for(dev, inv))
    except Exception as exc:
        msg = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return [{"cihaz": dev["name"], "kontrol": "Erisim", "durum": FAIL, "beklenen": "konsol", "gercek": msg}]
    reach = [{"cihaz": dev["name"], "kontrol": "Erisim", "durum": OK, "beklenen": "konsol", "gercek": "baglandi"}]
    return reach + build_checks(dev, raw, inv, selected, partial)


# ------------------------------------------------------------------ ana
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None, help="yalniz bu cihazlar")
    ap.add_argument("--partial", action="store_true", help="secilmeyen cihazlara bakan beklentileri atla")
    ap.add_argument("--details", action="store_true", help="tum kontrolleri listele")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    deploy.load_dotenv()

    inv = yaml.safe_load(deploy.INVENTORY.read_text(encoding="utf-8"))
    devices = deploy.load_inventory()
    if args.only:
        unknown = set(args.only) - {d["name"] for d in devices}
        if unknown:
            ap.error(f"envanterde olmayan cihaz: {', '.join(sorted(unknown))}")
        devices = [d for d in devices if d["name"] in args.only]
    selected = {d["name"] for d in devices}

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda d: check_device(d, inv, selected, args.partial), devices))

    green = "\033[92m" if sys.stdout.isatty() else ""
    red = "\033[91m" if sys.stdout.isatty() else ""
    off = "\033[0m" if sys.stdout.isatty() else ""
    print(f"\n{'CIHAZ':13} {'DURUM':9} {'OK':>3} {'HATA':>4} {'ATL':>4}")
    print("-" * 38)
    all_checks, bad_devices = [], 0
    for dev, checks in zip(devices, results):
        all_checks += checks
        n_ok = sum(c["durum"] == OK for c in checks)
        n_fail = sum(c["durum"] == FAIL for c in checks)
        n_skip = sum(c["durum"] == SKIP for c in checks)
        bad_devices += bool(n_fail)
        label = f"{red}SORUNLU{off}  " if n_fail else f"{green}SAGLIKLI{off} "
        print(f"{dev['name']:13} {label} {n_ok:>3} {n_fail:>4} {n_skip:>4}")
        for c in checks:
            if c["durum"] == FAIL or (args.details and c["durum"] == OK):
                mark = f"{red}x{off}" if c["durum"] == FAIL else f"{green}+{off}"
                print(f"   {mark} {c['kontrol']:20} beklenen: {c['beklenen']:32} gercek: {c['gercek']}")

    totals = {s: sum(c["durum"] == s for c in all_checks) for s in (OK, FAIL, SKIP)}
    report = {
        "zaman": datetime.now().isoformat(timespec="seconds"),
        "kapsam": sorted(selected), "kismi": args.partial,
        "ozet": {"cihaz": len(devices), "saglikli": len(devices) - bad_devices, "sorunlu": bad_devices, **totals},
        "kontroller": all_checks,
    }
    out_dir = deploy.PROJECT / "reports"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"health_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("-" * 38)
    print(f"{len(devices) - bad_devices}/{len(devices)} cihaz saglikli | {totals[OK]} OK, {totals[FAIL]} HATA, "
          f"{totals[SKIP]} atlandi | {time.monotonic() - start:.0f} sn")
    print(f"Rapor: {path}")
    sys.exit(1 if bad_devices else 0)


if __name__ == "__main__":
    main()
