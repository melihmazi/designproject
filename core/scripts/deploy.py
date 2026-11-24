#!/usr/bin/env python3
"""Sablondan config uretip Netmiko ile GNS3 konsolu (telnet) uzerinden basar.

    python core/scripts/deploy.py --phase 1 --dry-run            # sadece uret (cihaza dokunmaz)
    python core/scripts/deploy.py --phase 1 --only MRK-ERS-SAT   # tek cihaz
    python core/scripts/deploy.py --phase 1 2 3                  # fazlari sirayla bas
    python core/scripts/deploy.py --list                         # envanter + konsol portlari

Parolalar ortam degiskenlerinden okunur: NET_USER, NET_PASS, NET_ENABLE
(proje kokundeki .env dosyasi varsa otomatik yuklenir; .env repoya girmez).
"""
import argparse
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

CORE = Path(__file__).resolve().parents[1]
PROJECT = CORE.parent
INVENTORY = CORE / "inventory" / "devices.yaml"
CONSOLES = CORE / "inventory" / "consoles.yaml"
TEMPLATES = CORE / "configs" / "templates"
RENDERED = CORE / "configs" / "rendered"
ERROR_MARKERS = ("% Invalid", "% Incomplete", "% Ambiguous", "% Unknown", "Command rejected")
# '%' ile baslayip hata olmayan IOS bilgi mesajlari
BENIGN = re.compile(r"^%\s*(Warning: portfast|Portfast (has been|will be) configured|Generating|Interface .* changed state|"
                    r"OSPF: Reference bandwidth is changed)", re.I)

log = logging.getLogger("deploy")


def load_dotenv(path=PROJECT / ".env"):
    """Bagimlilik eklememek icin minimal .env okuyucu (mevcut ortam degiskenini ezmez)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_inventory():
    """devices.yaml + consoles.yaml -> cihaz sozlukleri listesi. Her cihaza 'net' (ag geneli) eklenir."""
    data = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    consoles = {}
    if CONSOLES.exists():
        cdata = yaml.safe_load(CONSOLES.read_text(encoding="utf-8")) or {}
        consoles = cdata.get("consoles", {})
        if cdata.get("console_host"):
            data.setdefault("defaults", {})["console_host"] = cdata["console_host"]
    if os.getenv("NET_CONSOLE_HOST"):          # orn. yerel QEMU lab icin 127.0.0.1
        data.setdefault("defaults", {})["console_host"] = os.environ["NET_CONSOLE_HOST"]
    devices = []
    for d in data["devices"]:
        dev = {**data.get("defaults", {}), **d, "net": data.get("network", {})}
        if dev.get("console_port") is None:
            dev["console_port"] = consoles.get(dev["name"])
        devices.append(dev)
    return devices


def conn_params(dev):
    return {
        "device_type": dev["device_type"],
        "host": dev["console_host"],
        "port": dev["console_port"],
        "username": os.getenv("NET_USER", "admin"),
        "password": os.getenv("NET_PASS", ""),
        "secret": os.getenv("NET_ENABLE", ""),
        "global_delay_factor": 2,     # IOSv konsolu yavas; takilirsa 4 yap
        "fast_cli": False,
        "timeout": 60,
    }


_env = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined,
                   trim_blocks=True, lstrip_blocks=True)


def render(dev, phase):
    """<role>_faz<N>.j2 -> komut satirlari listesi (bos satirlar ve '!' yorumlari atilir)."""
    text = _env.get_template(f"{dev['role']}_faz{phase}.j2").render(**dev)
    return [l.rstrip() for l in text.splitlines() if l.strip() and not l.strip().startswith("!")]


def find_errors(output):
    """IOS hata satirlarini, hataya yol acan komutla birlikte dondurur."""
    errors, last_cmd = [], ""
    for line in output.splitlines():
        if "#" in line and not line.lstrip().startswith("%"):
            last_cmd = line.split("#", 1)[1].strip() or last_cmd
        text = line.strip()
        # IOS'un komuta verdigi her yanit '%' ile baslar (syslog satirlari '*' ile); bilinen zararsizlar haric hepsi raporlanir
        if any(m in line for m in ERROR_MARKERS) or (text.startswith("%") and not BENIGN.match(text)):
            errors.append(f"{text}   <- {last_cmd}")
    return errors


def verify(conn, lines):
    """Basilan satirlar gercekten running-config'e girdi mi? Eksikleri [(bolum, satir)] olarak dondurur.
    Okuma kararli degilse (konsol gurultusu) karar verilmez: None."""
    import confcheck
    running, stable = confcheck.read_running(conn)
    if not stable:
        return None
    return confcheck.missing_lines(lines, running)


def wake_console(host, port, timeout=30):
    """Konsolu uyandir: onceki oturum 'exit' ile kapandiysa IOS 'Press RETURN' + lisans metni basar.
    Netmiko'nun ilk komutu bu metne takilmasin diye prompt gorunene kadar Enter gonderilir."""
    import re
    import socket
    end, buf = time.monotonic() + timeout, b""
    with socket.create_connection((host, port), timeout=10) as s:
        s.settimeout(1.5)
        while time.monotonic() < end:
            s.sendall(bytes([13]))         # Enter (CR)
            try:
                buf = (buf + s.recv(65536))[-2000:]
            except socket.timeout:
                pass
            if re.search(rb"[>#]\s*$", buf):
                time.sleep(1.0)            # gec gelen log satirlari aksin
                return True
    return False


def push(dev, lines, attempts=3, check=True):
    """Satirlari basar. check=True ise running-config'i geri okur; eksik satir varsa tum blogu bir kez daha
    basar ve yine eksik kalani hata olarak dondurur (konsolda sessizce dusen/geri alinan komutlara karsi)."""
    from netmiko import ConnectHandler   # dry-run netmiko kurulu olmadan da calissin
    last = None
    for attempt in range(1, attempts + 1):
        try:
            wake_console(dev["console_host"], dev["console_port"])
            with ConnectHandler(**conn_params(dev)) as conn:
                if not conn.check_enable_mode():
                    conn.enable()
                out = conn.send_config_set(lines, cmd_verify=False, read_timeout=180)
                errors = find_errors(out)
                if check:
                    missing = verify(conn, lines)
                    if missing:
                        log.info("%-12s %d satir cihaza girmemis, yeniden basiliyor: %s", dev["name"], len(missing),
                                 "; ".join(f"[{s}] {l}" for s, l in missing[:3]))
                        out += conn.send_config_set(lines, cmd_verify=False, read_timeout=180)
                        missing = verify(conn, lines)
                    errors += [f"EKSIK (cihaza girmedi): [{s}] {l}" for s, l in (missing or [])]
                conn.save_config()
            return out, errors
        except Exception as exc:          # konsol mesgul / yavas: kisa bekle, yeniden dene
            last = exc
            log.info("%-12s deneme %d/%d basarisiz: %s", dev["name"], attempt, attempts,
                     str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__)
            time.sleep(5)
    raise last


def worker(dev, phase, dry_run):
    start = time.monotonic()
    try:
        lines = render(dev, phase)
    except TemplateNotFound:
        return dev["name"], "ATLANDI (bu faz icin sablon yok)", [], 0.0
    RENDERED.mkdir(parents=True, exist_ok=True)
    (RENDERED / f"{dev['name']}_faz{phase}.cfg").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if dry_run:
        return dev["name"], f"DRY-RUN ({len(lines)} satir uretildi)", [], time.monotonic() - start
    if dev.get("console_port") is None:
        return dev["name"], "HATA: console_port tanimsiz (gen_inventory.py calistir)", [], 0.0
    try:
        _, errors = push(dev, lines)
        status = "UYARI" if errors else "TAMAM"
        return dev["name"], f"{status} ({len(lines)} satir)", errors, time.monotonic() - start
    except Exception as exc:                       # baglanti / zaman asimi vb.
        return dev["name"], f"HATA: {type(exc).__name__}: {exc}", [], time.monotonic() - start


def run_phase(devices, phase, dry_run, workers):
    log.info("===== FAZ %s %s=====", phase, "(dry-run) " if dry_run else "")
    start = time.monotonic()
    failed = warned = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, d, phase, dry_run) for d in devices]
        for f in as_completed(futures):
            name, status, errors, secs = f.result()
            log.info("%-12s %-45s %5.1f sn", name, status, secs)
            for e in errors:
                log.info("    %s", e)
            failed += status.startswith("HATA")
            warned += status.startswith("UYARI")
    log.info("Faz %s bitti: %.1f sn, %d hata, %d uyari", phase, time.monotonic() - start, failed, warned)
    return failed, warned


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", type=int, nargs="+", help="basilacak faz(lar), orn. 1 veya 1 2 3")
    ap.add_argument("--only", nargs="*", default=None, help="yalniz bu cihazlar")
    ap.add_argument("--dry-run", action="store_true", help="sadece configs/rendered altina uret")
    ap.add_argument("--workers", type=int, default=4, help="es zamanli baglanti (GNS3 VM'i yormamak icin dusuk tut)")
    ap.add_argument("--list", action="store_true", help="envanteri listele ve cik")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    load_dotenv()

    devices = load_inventory()
    if args.list:
        for d in devices:
            print(f"{d['name']:12} {d['role']:10} {d['console_host']}:{d['console_port']}")
        return
    if not args.phase:
        ap.error("--phase gerekli (veya --list)")
    if args.only:
        unknown = set(args.only) - {d["name"] for d in devices}
        if unknown:
            ap.error(f"envanterde olmayan cihaz: {', '.join(sorted(unknown))}")
        devices = [d for d in devices if d["name"] in args.only]

    failed = warned = 0
    for phase in args.phase:
        f, w = run_phase(devices, phase, args.dry_run, args.workers)
        failed += f
        warned += w
        if f and not args.dry_run:
            log.info("Faz %s hatali bitti; sonraki fazlar BASILMADI.", phase)
            break
    sys.exit(1 if failed else (2 if warned else 0))


if __name__ == "__main__":
    main()
