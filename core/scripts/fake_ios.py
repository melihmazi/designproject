#!/usr/bin/env python3
"""GNS3 kapaliyken deploy.py'nin baglanti kodunu denemek icin SAHTE IOS telnet konsolu.

Gercek IOS degildir: komutlari dogrulamaz, yalnizca prompt/mod gecislerini taklit eder ve
"BOZUK" iceren satirlara '% Invalid input' doner (hata yakalamayi sinamak icin).

    python core/scripts/fake_ios.py --selftest        # sahte cihaza Faz 1 config'i basar, sonucu yazar
    python core/scripts/fake_ios.py --port 5999       # elle denemek icin sunucu olarak calistir
"""
import argparse
import socket
import sys
import threading

ENABLE_SECRET = "test-enable"


def serve_client(sock, hostname, received):
    mode = "user"                      # user | enable | config
    f = sock.makefile("rwb", buffering=0)

    def prompt():
        return {"user": f"{hostname}>", "enable": f"{hostname}#", "config": f"{hostname}(config)#"}[mode]

    def send(text):
        f.write(text.replace("\n", "\r\n").encode())

    send("\n" + prompt())
    waiting_password = False
    buf = b""
    try:
        while True:
            ch = f.read(1)
            if not ch:
                return
            if ch[0] == 255:           # telnet IAC pazarligini yut
                f.read(2)
                continue
            if ch not in (b"\r", b"\n"):
                buf += ch
                if not waiting_password:
                    f.write(ch)        # echo
                continue
            if ch == b"\r":
                continue
            line, buf = buf.decode(errors="replace").strip(), b""
            send("\n")
            if waiting_password:
                waiting_password = False
                if line == ENABLE_SECRET:
                    mode = "enable"
                else:
                    send("% Access denied\n")
            elif line == "enable" and mode == "user":
                waiting_password = True
                send("Password: ")
                continue
            elif line.startswith("conf") and mode == "enable":
                mode = "config"
                send("Enter configuration commands, one per line.  End with CNTL/Z.\n")
            elif line in ("end", "exit") and mode == "config":
                mode = "enable"
            elif line.startswith(("write", "copy run")):
                send("Building configuration...\n[OK]\n")
            elif line and mode == "config":
                received.append(line)
                if "BOZUK" in line:
                    send("            ^\n% Invalid input detected at '^' marker.\n\n")
            send(prompt())
    except (ConnectionError, OSError):
        return


def start_server(port=0, hostname="SAHTE-SW"):
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(5)
    received = []

    def loop():
        while True:
            try:
                client, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=serve_client, args=(client, hostname, received), daemon=True).start()

    threading.Thread(target=loop, daemon=True).start()
    return srv, srv.getsockname()[1], received


def selftest():
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import deploy

    os.environ["NET_ENABLE"] = ENABLE_SECRET
    dev = next(d for d in deploy.load_inventory() if d["name"] == "MRK-ERS-SAT")
    lines = deploy.render(dev, 1)
    sent = [l.strip() for l in lines]          # sahte konsol satirlari kirpilmis kaydeder
    srv, port, received = start_server()
    dev = {**dev, "console_host": "127.0.0.1", "console_port": port}

    ok = True
    _, errors = deploy.push(dev, lines)
    print(f"1) temiz config : {len(lines)} satir gonderildi, {len(received)} alindi, {len(errors)} hata")
    ok &= received == sent and not errors

    received.clear()
    _, errors = deploy.push(dev, lines)
    print(f"2) ikinci kez   : {len(received)} alindi, {len(errors)} hata (idempotent calistirma yolu)")
    ok &= received == sent and not errors

    received.clear()
    _, errors = deploy.push(dev, lines[:3] + ["switchport BOZUK komut"] + lines[3:])
    print(f"3) bozuk satir  : {len(errors)} hata yakalandi -> {errors}")
    ok &= len(errors) == 1 and "BOZUK" in errors[0]

    srv.close()
    print("SONUC:", "BASARILI" if ok else "BASARISIZ")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--port", type=int, default=5999)
    args = ap.parse_args()
    if args.selftest:
        selftest()
    srv, port, _ = start_server(args.port)
    print(f"Sahte IOS konsolu 127.0.0.1:{port} (enable parolasi: {ENABLE_SECRET}). Ctrl+C ile kapat.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
