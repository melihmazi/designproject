#!/usr/bin/env python3
"""Gercek GNS3 projesindeki switch'lere kayitli config'i, bilinen parolalarla yeniden yukler.

Neden: 10 switch'in enable parolasi belgelerde yoktu. Switch diskleri (hda_disk.qcow2) lab/gns3_disk_yedek/
altina tasindi, GNS3 bos diskle yeni bir kopya acti. Bu betik bos switch'in konsoluna lab/gns3_export/saved/
<isim>.cfg icerigini satir satir yazar; enable ve kullanici parolalarini lab/gns3_env.txt'den alir
(degerler ekrana yazilmaz), SSH anahtari uretir ve write memory yapar.

    python gns3_reset_switch.py                 # 10 switch, paralel
    python gns3_reset_switch.py MRK-ERS-SAT     # tek cihaz
Onkosul: GNS3 sunucusu 127.0.0.1:3080, proje acik, switch'ler baslamis.
"""
import json
import re
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

LAB = Path(__file__).resolve().parent
API = "http://127.0.0.1:3080/v2"
SAVED = LAB / "gns3_export" / "saved"
SKIP = re.compile(r"^(!|version |boot-(start|end)-marker|Building configuration|Current configuration|end$)")
lock = threading.Lock()


def log(name, msg):
    with lock:
        print(f"[{time.strftime('%H:%M:%S')}] {name:12} {msg}", flush=True)


def env():
    out = {}
    for line in (LAB / "gns3_env.txt").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def config_lines(name, e):
    lines, in_banner = [], False
    for raw in (SAVED / f"{name}.cfg").read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if line.startswith("banner "):
            in_banner = True          # bos imaj ayni varsayilan banner'lari zaten tasiyor
            continue
        if in_banner:
            if line == "!" or line.startswith("line "):
                in_banner = False
            else:
                continue
        if not line.strip() or SKIP.match(line):
            continue
        if line.startswith("enable secret"):
            line = f"enable secret {e['SWITCH_ENABLE']}"
        m = re.match(r"username (\S+) privilege 15 secret", line)
        if m:
            line = f"username {e.get('SWITCH_KULLANICI', m.group(1))} privilege 15 secret {e['SWITCH_KULLANICI_PAROLASI']}"
        lines.append(line)
    return lines


class Console:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.s.settimeout(0.3)
        self.buf = ""

    def read(self, t):
        end = time.monotonic() + t
        while time.monotonic() < end:
            try:
                d = self.s.recv(65536)
                if d:
                    self.buf += d.decode(errors="replace")
            except socket.timeout:
                pass
        return self.buf

    def until(self, pattern, t):
        end = time.monotonic() + t
        while time.monotonic() < end:
            self.read(0.5)
            m = re.search(pattern, self.buf)
            if m:
                out, self.buf = self.buf[:m.end()], self.buf[m.end():]
                return out
        return None

    def send(self, text):
        self.s.sendall(text.encode() + b"\r")


def wait_boot(c, name):
    """Bos switch acilisini bekler; ilk kurulum sorusuna 'no' der, Switch> ya da Switch# istemine ulasir."""
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        c.send("")
        out = c.until(r"initial configuration dialog\? \[yes/no\]:|terminate autoinstall\? \[yes\]:|[\w-]+[>#]\s*$", 15)
        if not out:
            continue
        if "initial configuration" in out:
            c.send("no")
            log(name, "ilk kurulum sorusu: no")
            time.sleep(5)
        elif "autoinstall" in out:
            c.send("yes")
        elif re.search(r"Switch[>#]\s*$", out):
            return True
        else:
            log(name, "beklenmeyen istem: " + out.strip().splitlines()[-1][-40:])
            if not re.search(r"Switch", out):
                return False          # config zaten yuklenmis olabilir
    return False


def reset(name, port, e):
    lines = config_lines(name, e)
    c = Console(port)
    log(name, f"konsol {port}, acilis bekleniyor ({len(lines)} satir yuklenecek)")
    if not wait_boot(c, name):
        log(name, "HATA: bos switch istemine ulasilamadi")
        return False
    time.sleep(20)                     # acilis mesajlari dinsin
    c.read(2)
    c.buf = ""
    c.send("enable")
    c.until(r"#\s*$", 20)
    c.send("terminal length 0")
    c.until(r"#\s*$", 20)
    c.send("configure terminal")
    c.until(r"\(config\)#\s*$", 20)
    errors = []
    for i, line in enumerate(lines, 1):
        c.send(line)
        out = c.until(r"\(config[^)]*\)#\s*$", 60)
        if out is None:
            errors.append(f"{line}  (zaman asimi)")
            c.read(3)
            c.buf = ""
        elif re.search(r"% (Invalid|Incomplete|Ambiguous)", out):
            errors.append(line)
        if i % 50 == 0:
            log(name, f"{i}/{len(lines)} satir")
    c.send("crypto key generate rsa general-keys modulus 2048")
    c.until(r"\(config\)#\s*$", 300)
    c.send("end")
    c.until(r"#\s*$", 30)
    c.send("write memory")
    ok = c.until(r"\[OK\]", 180) is not None
    c.until(r"#\s*$", 30)
    log(name, f"bitti: {len(lines)} satir, {len(errors)} reddedilen, write memory {'OK' if ok else 'HATA'}")
    for err in errors:
        log(name, "   reddedildi: " + err[:90])
    c.s.close()
    return ok


def main():
    sys.stdout.reconfigure(errors="replace")
    e = env()
    projects = json.load(urllib.request.urlopen(f"{API}/projects"))
    pid = next(p["project_id"] for p in projects if p["status"] == "opened")
    nodes = json.load(urllib.request.urlopen(f"{API}/projects/{pid}/nodes"))
    switches = {n["name"]: n["console"] for n in nodes
                if n["node_type"] == "qemu" and "l2" in n["properties"].get("hda_disk_image", "").lower()}
    wanted = sys.argv[1:] or sorted(switches)
    results = {}
    threads = [threading.Thread(target=lambda n=n: results.__setitem__(n, reset(n, switches[n], e))) for n in wanted]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    good = sum(1 for v in results.values() if v)
    print(f"\n{good}/{len(wanted)} switch yeniden yuklendi")
    sys.exit(0 if good == len(wanted) else 1)


if __name__ == "__main__":
    main()
