#!/usr/bin/env python3
"""Gercek GNS3 projesine yalniz bulunan duzeltmeleri basar (tum fazi degil):
  - L2 switch'lere statik varsayilan rota (IOSvL2 'ip default-gateway'i yok sayiyor)
  - routed Port-channel aciklamalari (yeniden baslatmada kayboluyor)
  - yeniden yuklemede kapali gelen SVI'lar icin 'no shutdown'
Satirlar cekirdek sablonlarindan uretilir.   Calistirma: python gns3_run.py sw ../lab/gns3_fix.py
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "network-automation-project" / "core" / "scripts"))
import deploy

SVI = {"dag": [10, 20, 30, 40, 50, 60, 90, 254], "access": [90], "branch_sw": [110]}


def lines_for(dev):
    role, out = dev["role"], []
    for v in SVI.get(role, []):
        out += [f"interface Vlan{v}", " no shutdown"]
    if role in ("access", "branch_sw"):
        out += [l for l in deploy.render(dev, 2 if role == "access" else 3) if l.startswith("ip route 0.0.0.0")]
    if role in ("core", "dag"):
        cur = None
        for l in deploy.render(dev, 2):
            if l.startswith("interface "):
                cur = l if l.startswith("interface Port-channel") else None
            elif cur and l.strip().startswith("description"):
                out += [cur, l]
    return out


def work(dev):
    lines = lines_for(dev)
    if "--dry-run" in sys.argv:
        return dev["name"], lines, []
    _, errors = deploy.push(dev, lines)
    return dev["name"], lines, errors


deploy.load_dotenv()
devs = [d for d in deploy.load_inventory() if d["role"] in ("core", "dag", "access", "branch_sw")]
bad = 0
with ThreadPoolExecutor(max_workers=5) as pool:
    for name, lines, errors in pool.map(work, devs):
        print(f"{name:12} {len(lines)} satir, hata {len(errors)}: {[l.strip() for l in lines if 'Vlan' not in l and 'shutdown' not in l]}")
        for e in errors:
            print("    " + e)
        bad += bool(errors)
sys.exit(1 if bad else 0)
