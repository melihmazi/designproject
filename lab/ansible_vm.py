#!/usr/bin/env python3
"""Ansible kontrol dugumu: Windows'ta Ansible calismadigi icin QEMU icinde disksiz (RAM'de) bir Alpine Linux.

    python ansible_vm.py start        # VM'i ac, ansible-core + cisco.ios koleksiyonunu kur (internet gerekir)
    python ansible_vm.py run [ansible-playbook argumanlari]     # site.yml'i calistir, ciktiyi yaz
    python ansible_vm.py sh "komut"   # VM icinde tek komut
    python ansible_vm.py stop

Ag: QEMU user-net. VM icinden 10.0.2.2 = bu makine; cihazlarin bant disi SSH portlari (127.0.0.1:22xx) oradan gorunur.
Proje dosyalari VM'e gecici bir HTTP sunucusuyla (yalniz 127.0.0.1) tar olarak aktarilir; parolalar .env'den
uretilen env.sh ile gider, konsola yazilmaz.
"""
import functools
import http.server
import io
import json
import re
import socket
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

from lab import NODES, mgmt_ports

LAB = Path(__file__).resolve().parent
PROJ = LAB.parent / "network-automation-project"
QEMU = r"C:\Program Files\qemu\qemu-system-x86_64.exe"
PORT, HTTP_PORT = 5100, 8099
STATE = LAB / "ansible_vm.json"
MIRROR = "http://dl-cdn.alpinelinux.org/alpine/v3.20"
MARK = "__BITTI__"


class Serial:
    def __init__(self):
        self.s = socket.create_connection(("127.0.0.1", PORT), timeout=10)
        self.s.settimeout(1.0)

    def read(self, seconds):
        end, data = time.monotonic() + seconds, b""
        while time.monotonic() < end:
            try:
                chunk = self.s.recv(65536)
                if not chunk:
                    break
                data += chunk
            except socket.timeout:
                pass
        data = re.sub(rb"\xff[\xfb-\xfe].", b"", data)
        return re.sub(rb"\x1b\[[0-9;?]*[A-Za-z]", b"", data).decode(errors="replace")      # busybox imlec sorgusu vb.

    def send(self, text):
        self.s.sendall(text.encode() + b"\n")

    def wait_for(self, pattern, timeout, poke=None):
        buf, end = "", time.monotonic() + timeout
        while time.monotonic() < end:
            buf += self.read(2)
            if re.search(pattern, buf):
                return buf
            if poke is not None:
                self.send(poke)
        raise TimeoutError(f"beklenen cikti gelmedi: {pattern!r}; son: {buf[-400:]!r}")

    def run(self, cmd, timeout=600):
        """Komutu calistir, (cikis kodu, cikti) dondur."""
        self.read(0.5)
        self.send(f"{cmd}; echo {MARK}$?")
        buf = self.wait_for(MARK + r"\d+", timeout)
        code = int(re.search(MARK + r"(\d+)", buf).group(1))
        body = buf.split("\n", 1)[1] if "\n" in buf else buf
        return code, re.sub(MARK + r"\d+.*", "", body, flags=re.S).rstrip()


def start():
    args = [QEMU, "-name", "ansible", "-m", "1024", "-smp", "2", "-display", "none",
            "-kernel", str(LAB / "alpine" / "vmlinuz-virt"), "-initrd", str(LAB / "alpine" / "initramfs-virt"),
            "-append", f"console=ttyS0 ip=dhcp alpine_repo={MIRROR}/main modloop={MIRROR}/releases/x86_64/netboot/modloop-virt",
            "-serial", f"telnet:127.0.0.1:{PORT},server,nowait",
            "-netdev", "user,id=n0", "-device", "virtio-net-pci,netdev=n0"]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    for accel in (["-accel", "whpx,kernel-irqchip=off"], ["-accel", "tcg"]):
        log = open(LAB / "logs" / "ansible_vm.log", "w")
        p = subprocess.Popen(args + accel, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags)
        time.sleep(8)
        if p.poll() is None:
            break
        print(f"hizlandirici {accel[1]} calismadi, sonraki deneniyor")
    STATE.write_text(json.dumps({"pid": p.pid, "accel": accel[1]}))
    print(f"VM basladi (pid {p.pid}, {accel[1]}); acilis bekleniyor...")
    t0 = time.monotonic()
    c = Serial()
    c.wait_for(r"login:", 900, poke="")
    c.send("root")
    c.wait_for(r"#\s*$", 60, poke="")
    print(f"giris yapildi ({time.monotonic() - t0:.0f} sn)")
    provision(c)


def provision(c=None):
    c = c or Serial()
    t0 = time.monotonic()
    c.run("stty cols 250 2>/dev/null; export PS1='# '", 30)
    steps = [f"printf '%s\\n' {MIRROR}/main {MIRROR}/community > /etc/apk/repositories",
             "apk update -q",
             "apk add -q ansible-core py3-paramiko py3-yaml",
             "ansible-galaxy collection install cisco.ios 2>&1 | tail -3",
             "ansible --version | head -1"]
    for s in steps:
        code, out = c.run(s, timeout=1800)
        print(f"[{code}] {s}\n{out[-400:]}")
        if code:
            sys.exit("kurulum adimi basarisiz")
    print(f"hazir ({time.monotonic() - t0:.0f} sn)")


def bundle():
    """extensions/ansible + devices.yaml + lab adres haritasi + env.sh -> bellek ici tar"""
    env = {}
    for line in (PROJ / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.split("#")[0].strip()
    netmap = "\n".join(f'{n}: "10.0.2.2:{mgmt_ports(n)[0]}"' for n in NODES) + "\n"
    envsh = "".join(f"export {k}='{env.get(k, '')}'\n" for k in ("NET_USER", "NET_PASS", "NET_ENABLE"))
    envsh += "export ANSIBLE_NET_MAP=/root/p/lab_map.yaml\n"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.add(PROJ / "extensions" / "ansible", arcname="p/extensions/ansible",
                filter=lambda ti: None if "__pycache__" in ti.name else ti)
        tar.add(PROJ / "core" / "inventory" / "devices.yaml", arcname="p/core/inventory/devices.yaml")
        for name, text in (("p/lab_map.yaml", netmap), ("p/env.sh", envsh)):
            data = text.encode()
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def push_files(c):
    payload = bundle()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", HTTP_PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        code, out = c.run(f"rm -rf /root/p && cd /root && wget -q -O p.tar http://10.0.2.2:{HTTP_PORT}/ && tar xf p.tar && rm p.tar && chmod -R go-w p && chmod +x p/extensions/ansible/inventory.py && echo aktarildi", 120)
    finally:
        srv.shutdown()
    if code:
        sys.exit(f"dosya aktarimi basarisiz: {out}")


def main():
    sys.stdout.reconfigure(errors="replace")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "start":
        start()
    elif cmd == "provision":
        provision()
    elif cmd == "stop":
        if STATE.exists():
            subprocess.run(["taskkill", "/F", "/PID", str(json.loads(STATE.read_text())["pid"])], capture_output=True)
            STATE.unlink()
            print("VM durduruldu")
    elif cmd == "sh":
        c = Serial()
        code, out = c.run(sys.argv[2], 1800)
        print(out)
        sys.exit(code)
    elif cmd == "run":
        c = Serial()
        push_files(c)
        extra = " ".join(sys.argv[2:])
        code, out = c.run(f"cd /root/p/extensions/ansible && . /root/p/env.sh && ANSIBLE_FORCE_COLOR=0 ansible-playbook site.yml {extra} 2>&1", 3600)
        print(out)
        sys.exit(code)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
