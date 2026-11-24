#!/usr/bin/env python3
"""Hizli yakinsama modulu: dugum tumden durdugunda kesintiyi kisaltir. Cekirdege dokunmaz.

    python extensions/fast-convergence/hizli.py --dry-run
    python extensions/fast-convergence/hizli.py              # CORE1/2, DAG1/2, SNR-RTR
    python extensions/fast-convergence/hizli.py --rollback   # varsayilan sureler (hello 10 / dead 40, HSRP 3 / 10)

Neden: GNS3'te (ve araya switch giren gercek aglarda) komsu dugum durunca link "up" kalir; OSPF komsunun
oldugunu ancak dead suresi (40 sn) dolunca anlar. Olculen kesinti 59-65 sn idi.
Ne yapar
  Alan 0 transit arayuzleri : ip ospf hello-interval 1 / dead-interval 4
  DAG HSRP gruplari          : standby <grup> timers 1 3
Hangi arayuzler: cekirdegin Faz 2 sablon ciktisindan okunur (alan 0'da olan, Loopback olmayan arayuzler).
Not: linkin iki ucu da ayni sureleri tasimalidir; hepsini tek seferde bas (komsuluk birkac saniye duser).
"""
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "core" / "scripts"))
import deploy  # noqa: E402

ROLES = {"core", "dag", "snr"}
HELLO, DEAD, HSRP = 1, 4, "1 3"


def lines_for(dev, rollback):
    blocks, cur = {}, None
    for line in deploy.render(dev, 2):
        if line.startswith("interface "):
            cur = line.split(None, 1)[1]
            blocks[cur] = []
        elif line.startswith(" ") and cur:
            blocks[cur].append(line.strip())
        else:
            cur = None
    out = []
    for ifname, body in blocks.items():
        cmds = []
        if "ip ospf 1 area 0" in body and not ifname.lower().startswith("loopback"):
            cmds += ([" no ip ospf hello-interval", " no ip ospf dead-interval"] if rollback else
                     [f" ip ospf hello-interval {HELLO}", f" ip ospf dead-interval {DEAD}"])
        for b in body:
            m = re.match(r"standby (\d+) ip ", b)
            if m:
                cmds.append(f" {'no ' if rollback else ''}standby {m.group(1)} timers{'' if rollback else ' ' + HSRP}")
        if cmds:
            out += [f"interface {ifname}"] + cmds
    return out


def work(dev, dry_run, rollback):
    lines = lines_for(dev, rollback)
    # sapma raporu icin: drift.py --also extensions/fast-convergence/rendered
    out = HERE / "rendered"
    out.mkdir(exist_ok=True)
    (out / f"{dev['name']}_{'geri_al' if rollback else 'hizli'}.cfg").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    if dry_run:
        return dev["name"], f"DRY-RUN ({len(lines)} satir)", lines
    try:
        _, errors = deploy.push(dev, lines, check=not rollback)
        return dev["name"], f"{'UYARI' if errors else 'TAMAM'} ({len(lines)} satir)", errors
    except Exception as exc:
        return dev["name"], f"HATA: {type(exc).__name__}", []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()
    deploy.load_dotenv()
    devs = [d for d in deploy.load_inventory() if d["role"] in ROLES and (not args.only or d["name"] in args.only)]
    failed = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        for name, status, extra in pool.map(lambda d: work(d, args.dry_run, args.rollback), devs):
            print(f"{name:12} {status}")
            for e in extra:
                print("    " + e)
            failed += not status.startswith(("TAMAM", "DRY"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
