#!/usr/bin/env python3
"""Config sapma (drift) raporu: canli config <-> sablonlardan uretilen "altin" config.

Cekirdege dokunmaz; girdi olarak core/configs/rendered/*.cfg ve backups/<son>/ *.cfg kullanir.
Karsilastirma kurallari core/scripts/confcheck.py icindedir (deploy.py'nin basis sonrasi kontroluyle ortak).

    python extensions/drift/drift.py                      # en son yedek klasoru
    python extensions/drift/drift.py --backup backups/2026-11-24_024336
    python extensions/drift/drift.py --running-dir ../lab/logs --suffix _running.cfg

EKSIK  = sablonda var, cihazda yok (biri silmis ya da hic basilmamis)
FAZLA  = sablonun yonettigi bir bolumde, sablonda olmayan satir (biri elle eklemis)

Not: NAPALM yerine yerel karsilastirma kullanildi. NAPALM'in IOS surucusu SSH/SCP ister; bu projede yonetim yolu
konsol telnet oldugu icin (yol haritasi U6) NAPALM calismaz. Mantik ayni: istenen durum <-> canli durum farki.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "core" / "scripts"))
import confcheck  # noqa: E402

RENDERED = PROJECT / "core" / "configs" / "rendered"
BACKUPS = PROJECT / "backups"


ALSO = []          # --also ile eklenen ek "altin" klasorler (orn. sertlestirme ciktilari)


def compare(name, running_text):
    files = sorted(RENDERED.glob(f"{name}_faz*.cfg"))
    for extra_dir in ALSO:
        files += sorted(f for f in Path(extra_dir).glob(f"{name}_*.cfg") if "geri_al" not in f.name)
    golden = confcheck.merge(f.read_text(encoding="utf-8") for f in files)
    missing, extra = confcheck.compare(golden, running_text)
    return {"cihaz": name, "sablon_dosyasi": len(files), "eksik": missing, "fazla": extra}


def latest_backup():
    dirs = sorted(d for d in BACKUPS.iterdir() if d.is_dir()) if BACKUPS.exists() else []
    if not dirs:
        sys.exit("backups/ altinda yedek yok; once core/scripts/backup.py calistir")
    return dirs[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backup", default=None, help="yedek klasoru (varsayilan: en son)")
    ap.add_argument("--running-dir", default=None, help="running-config dosyalarinin oldugu baska bir klasor")
    ap.add_argument("--suffix", default=".cfg")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--also", nargs="*", default=[], metavar="KLASOR",
                    help="altin config'e eklenecek klasorler, orn. extensions/security-hardening/rendered")
    args = ap.parse_args()
    ALSO.extend(args.also)

    src = Path(args.running_dir or args.backup or latest_backup())
    results = []
    for f in sorted(src.glob(f"*{args.suffix}")):
        name = f.name[: -len(args.suffix)]
        if args.only and name not in args.only:
            continue
        if not list(RENDERED.glob(f"{name}_faz*.cfg")):
            continue
        results.append(compare(name, f.read_text(encoding="utf-8")))

    drifted = 0
    print(f"Kaynak: {src}\n")
    for r in results:
        n = len(r["eksik"]) + len(r["fazla"])
        drifted += bool(n)
        print(f"{r['cihaz']:12} {'SAPMA VAR' if n else 'UYUMLU   '}  eksik {len(r['eksik']):2}  fazla {len(r['fazla']):2}")
        for section, line in r["eksik"]:
            print(f"   - EKSIK  [{section}] {line}")
        for section, line in r["fazla"]:
            print(f"   + FAZLA  [{section}] {line}")
    out = PROJECT / "reports" / f"drift_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"kaynak": str(src), "sonuc": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(results) - drifted}/{len(results)} cihaz uyumlu | Rapor: {out}")
    sys.exit(1 if drifted else 0)


if __name__ == "__main__":
    main()
