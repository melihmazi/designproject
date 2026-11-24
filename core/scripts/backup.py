#!/usr/bin/env python3
"""Her cihazin running-config'ini backups/YYYY-MM-DD_HHMM/<hostname>.cfg olarak kaydeder.

    python core/scripts/backup.py                         # 13 cihaz
    python core/scripts/backup.py --only MRK-DAG1 MRK-DAG2
    python core/scripts/backup.py --diff                  # bir onceki yedekle farki da goster
    python core/scripts/backup.py --every 60              # 60 dakikada bir tekrarla (Ctrl+C ile dur)

Guvenlik: yedeklerde parola ozetleri bulunur -> backups/ .gitignore icindedir.
--sanitize ile 'secret'/'password' satirlari maskelenmis bir kopya (backups/<damga>/sanitized/) da yazilir.
"""
import argparse
import difflib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deploy  # noqa: E402
from validate import collect  # noqa: E402

BACKUPS = deploy.PROJECT / "backups"
VOLATILE = re.compile(r"^(Building configuration|Current configuration|! Last configuration|! NVRAM config|ntp clock-period)")
SECRET = re.compile(r"^(\s*(?:enable secret|enable password|username \S+ .*?secret|username \S+ .*?password|"
                    r"password|snmp-server community|key-string|ip ospf message-digest-key \d+ md5)\s+(?:\d\s+)?)\S+.*$")


def clean(text):
    """Her yedekte degisen satirlari (zaman damgasi, boyut) at; kalan icerik karsilastirilabilir olsun."""
    # bos satirlar da atilir: konsol ciktisinda araya rastgele girebiliyor ve sahte fark uretiyor
    lines = [l.rstrip() for l in text.splitlines() if l.strip() and not VOLATILE.match(l)]
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).strip() + "\n"


def sanitize(text):
    return "\n".join(SECRET.sub(r"\1<MASKELENDI>", l) for l in text.splitlines()) + "\n"


def previous_dir(current):
    dirs = sorted(d for d in BACKUPS.iterdir() if d.is_dir() and d != current) if BACKUPS.exists() else []
    return dirs[-1] if dirs else None


def backup_one(dev, out_dir, do_sanitize):
    """Kararli okuma (confcheck.read_running): iki ardisik okuma ayni olmadan yedek yazilmaz."""
    from netmiko import ConnectHandler
    import confcheck
    cfg, err = None, "baglanti kurulamadi"
    for _ in range(3):
        try:
            deploy.wake_console(dev["console_host"], dev["console_port"])
            with ConnectHandler(**deploy.conn_params(dev)) as conn:
                if not conn.check_enable_mode():
                    conn.enable()
                cfg, stable = confcheck.read_running(conn)
            if stable:
                err = None
                break
            err = "kararsiz okuma (ardisik iki okuma farkli)"
        except Exception as exc:
            err = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            time.sleep(5)
    if err:
        return dev["name"], None, err
    (out_dir / f"{dev['name']}.cfg").write_text(cfg, encoding="utf-8")
    if do_sanitize:
        (out_dir / "sanitized").mkdir(exist_ok=True)
        (out_dir / "sanitized" / f"{dev['name']}.cfg").write_text(sanitize(cfg), encoding="utf-8")
    return dev["name"], cfg, None


def backup_all(devices, show_diff=False, do_sanitize=False, workers=4):
    stamp = f"{datetime.now():%Y-%m-%d_%H%M%S}"
    out_dir = BACKUPS / stamp
    prev = previous_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda d: backup_one(d, out_dir, do_sanitize), devices))
    failed = 0
    for name, cfg, err in results:
        if err:
            failed += 1
            print(f"HATA   {name:12} {err}")
            continue
        note = ""
        old = prev / f"{name}.cfg" if prev else None
        if old is not None and old.exists():
            diff = list(difflib.unified_diff(old.read_text(encoding="utf-8").splitlines(), cfg.splitlines(),
                                             f"{prev.name}/{name}", f"{stamp}/{name}", lineterm="", n=1))
            changed = sum(1 for l in diff if l[:1] in "+-" and l[:3] not in ("+++", "---"))
            note = f"onceki yedege gore {changed} satir degisti" if changed else "onceki yedekle ayni"
            if show_diff and changed:
                note += "\n" + "\n".join("      " + l for l in diff)
        print(f"TAMAM  {name:12} {len(cfg.splitlines()):4} satir  {note}")
    print(f"Yedek klasoru: {out_dir}  ({len(results) - failed}/{len(results)} cihaz)")
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--diff", action="store_true", help="onceki yedekle farki goster")
    ap.add_argument("--sanitize", action="store_true", help="parolalari maskelenmis kopya da yaz")
    ap.add_argument("--every", type=int, default=0, metavar="DAKIKA", help="bu aralikla surekli yedekle")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    deploy.load_dotenv()
    devices = deploy.load_inventory()
    if args.only:
        unknown = set(args.only) - {d["name"] for d in devices}
        if unknown:
            ap.error(f"envanterde olmayan cihaz: {', '.join(sorted(unknown))}")
        devices = [d for d in devices if d["name"] in args.only]
    while True:
        failed = backup_all(devices, args.diff, args.sanitize, args.workers)
        if not args.every:
            sys.exit(1 if failed else 0)
        print(f"Sonraki yedek {args.every} dakika sonra (Ctrl+C ile dur)")
        try:
            time.sleep(args.every * 60)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
