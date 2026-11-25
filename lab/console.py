#!/usr/bin/env python3
"""Lab dugumlerinin konsolu icin yardimci: acilisi bekler, Faz 0-D bootstrap'ini yapar, komut calistirir.

    python console.py wait ISIM ...        # IOS prompt'u gelene kadar bekle (ilk kurulum sorusuna 'no' der)
    python console.py bootstrap ISIM ...   # hostname, enable secret, admin kullanicisi, konsol ayarlari
    python console.py show ISIM "komut"    # enable modunda tek komut calistir, ciktiyi yaz

Parolalar network-automation-project/.env dosyasindan okunur (NET_ENABLE, NET_PASS).
RSA anahtari uretilmez: lab yalniz konsol kullanir, SSH yok (TCG'de anahtar uretimi dakikalar surer).
"""
import re
import socket
import sys
import time
from pathlib import Path

from lab import NODES

ENV = Path(__file__).resolve().parent.parent / "network-automation-project" / ".env"
PROMPT = re.compile(r"[\w.()-]+[>#]\s*$")


def env():
    out = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class Console:
    def __init__(self, name):
        self.name = name
        self.sock = socket.create_connection(("127.0.0.1", NODES[name][1]), timeout=10)
        self.sock.settimeout(1.0)

    def read(self, seconds=1.0):
        end, data = time.monotonic() + seconds, b""
        while time.monotonic() < end:
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                data += chunk
            except socket.timeout:
                pass
        data = re.sub(rb"\xff[\xfb-\xfe].", b"", data)          # telnet IAC pazarligini at
        return data.decode(errors="replace")

    def send(self, text):
        self.sock.sendall(text.encode() + b"\r")

    def wait_prompt(self, timeout=1800):
        """Acilisi bekle. Ilk kurulum diyalogunu ve 'Press RETURN' ekranini gecer."""
        start, buf = time.monotonic(), ""
        while time.monotonic() - start < timeout:
            self.send("")
            buf = (buf + self.read(4))[-4000:]
            if "initial configuration dialog" in buf:
                self.send("no")
                buf = ""
                continue
            if "terminate autoinstall" in buf:
                self.send("yes")
                buf = ""
                continue
            tail = buf.strip().splitlines()[-1] if buf.strip() else ""
            if PROMPT.search(tail) and "(boot)" not in tail:
                return time.monotonic() - start
        raise TimeoutError(f"{self.name}: {timeout} sn icinde prompt gelmedi. Son cikti: {buf[-300:]!r}")

    def cmd(self, text, wait=2.0, until=PROMPT, timeout=60):
        self.send(text)
        out, end = "", time.monotonic() + timeout
        while time.monotonic() < end:
            out += self.read(wait)
            last = out.strip().splitlines()[-1] if out.strip() else ""
            if until.search(last) or "assword" in last:
                break
        return out

    def enable(self):
        self.send("")
        out = self.read(1.5)
        last = out.strip().splitlines()[-1] if out.strip() else ""
        if last.endswith("#") and "(config" not in last:
            return
        if "(config" in last:
            self.cmd("end")
            return
        out = self.cmd("enable")
        if "assword" in out:
            self.cmd(env().get("NET_ENABLE", ""))

    def close(self):
        self.sock.close()


def bootstrap(name):
    e = env()
    c = Console(name)
    secs = c.wait_prompt()
    c.enable()
    lines = ["configure terminal", "no ip domain-lookup", f"hostname {name}",
             "ip domain-name anadolumakina.local", "service password-encryption",
             f"enable secret {e['NET_ENABLE']}", f"username admin privilege 15 secret {e['NET_PASS']}",
             "line con 0", " exec-timeout 0 0", " logging synchronous",
             "line vty 0 4", " login local", " transport input ssh", " exec-timeout 30 0", "exit"]
    if NODES[name][0] == "l3":
        lines += ["interface range GigabitEthernet0/0 - 3", " no shutdown", "exit",
                  "interface GigabitEthernet0/3", " description LAB-BANT-DISI-YONETIM",
                  " ip address 10.0.2.15 255.255.255.0", "exit"]
    else:
        lines += ["interface GigabitEthernet3/3", " no switchport", " description LAB-BANT-DISI-YONETIM",
                  " ip address 10.0.2.15 255.255.255.0", " no shutdown", "exit"]
    if "--ssh" in sys.argv:           # Ansible icin: SSH sunucusu (TCG'de anahtar uretimi 1-2 dk surer)
        lines += ["crypto key generate rsa modulus 1024", "ip ssh version 2"]
    bad = []
    for line in lines:
        out = c.cmd(line, wait=1.0, timeout=300 if line.startswith("crypto key") else 60)
        if "% " in out:
            bad.append((line.split(" secret ")[0], out.strip().splitlines()[-2:]))
    c.cmd("end")
    out = c.cmd("write memory", wait=3.0, timeout=120)
    c.close()
    print(f"{name}: bootstrap tamam (acilis bekleme {secs:.0f} sn, hata {len(bad)}) {'[OK]' if '[OK]' in out else out[-80:]!r}")
    for b in bad:
        print("   ", b)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    action = sys.argv[1]
    if action == "wait":
        for n in sys.argv[2:]:
            c = Console(n)
            print(f"{n}: prompt geldi ({c.wait_prompt():.0f} sn)")
            c.close()
    elif action == "bootstrap":
        for n in sys.argv[2:]:
            if n in NODES:
                bootstrap(n)
    elif action == "show":
        c = Console(sys.argv[2])
        c.enable()
        c.cmd("terminal length 0")
        print(c.cmd(sys.argv[3], wait=3.0, timeout=120))
        c.close()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
