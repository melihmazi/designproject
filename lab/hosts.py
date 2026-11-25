#!/usr/bin/env python3
"""Uc cihaz benzetimi: asil projedeki 17 VPCS dugumunun yerini tutar (VPCS'in yapamadiklarini da yapar).

Her Host, switch portuna bagli QEMU UDP soketinin obur ucudur; Ethernet cercevelerini scapy ile kurar/cozer.
Yapabildikleri: ARP, ICMP echo (istek + yanit), DHCP istemcisi (DORA), TCP SYN yoklamasi ve dinleme,
UDP yoklamasi ve yankisi, IPv6 SLAAC + ping6, surekli ping olcumu (failover kaybi), ve saldiri testleri icin
kacak DHCP sunucusu ile MAC tasmasi.

    from hosts import Host
    with Host("SAT-PC2") as pc:
        print(pc.dhcp(), pc.ping("172.16.10.1"))
"""
import ipaddress
import logging
import random
import socket
import threading
import time

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
logging.getLogger("scapy.loading").setLevel(logging.ERROR)
from scapy.layers.dhcp import BOOTP, DHCP  # noqa: E402
from scapy.layers.inet import ICMP, IP, TCP, UDP  # noqa: E402
from scapy.layers.inet6 import (ICMPv6DestUnreach, ICMPv6EchoReply, ICMPv6EchoRequest, ICMPv6ND_NA, ICMPv6ND_NS, ICMPv6ND_RA,  # noqa: E402
                                ICMPv6ND_RS, ICMPv6NDOptDstLLAddr, ICMPv6NDOptPrefixInfo, ICMPv6NDOptSrcLLAddr, IPv6)
from scapy.layers.l2 import ARP, Ether  # noqa: E402
from scapy.packet import Raw  # noqa: E402

from lab import ENDPOINTS, endpoint_ports  # noqa: E402

BCAST = "ff:ff:ff:ff:ff:ff"


class Host:
    avoid = None          # dhcp(): bu sunucudan gelen Offer'i secme (kacak sunucu testinde gercek kirayi almak icin)
    giaddr = None
    rogue = None
    rogue_hits = 0

    def __init__(self, name, tcp=(), udp=()):
        self.name = name
        self.switch, self.port, self.vlan, static = ENDPOINTS[name]
        local, remote = endpoint_ports(name)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", local))
        self.sock.settimeout(0.3)
        self.peer = ("127.0.0.1", remote)
        idx = list(ENDPOINTS).index(name)
        self.mac = "02:00:00:00:%02x:01" % idx
        self.ip = static
        self.gw = static.rsplit(".", 1)[0] + ".1" if static else None
        self.tcp_listen, self.udp_listen = set(tcp), set(udp)
        self.arp_cache, self.seen, self.offers = {}, [], []
        self.ip6, self.gw6_mac, self.gw6, self.nd_cache, self.ra_prefix = None, None, None, {}, None
        self.gw6_rank = 0
        self.ll6 = "fe80::ff:fe00:%x01" % idx
        self.lock = threading.Lock()
        self.alive = True
        self.thread = threading.Thread(target=self._rx, daemon=True)
        self.thread.start()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        self.alive = False
        self.thread.join(1)
        self.sock.close()

    # ---------------- alt katman ----------------
    def send(self, pkt):
        try:
            self.sock.sendto(bytes(pkt), self.peer)
        except OSError:
            pass

    def _note(self, *item):
        with self.lock:
            self.seen.append(item)

    def _wait(self, pred, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                for item in self.seen:
                    if pred(item):
                        return item
            time.sleep(0.02)
        return None

    def _rx(self):
        while self.alive:
            try:
                data, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:              # Windows: karsi port kapaliyken WSAECONNRESET
                time.sleep(0.05)
                continue
            try:
                self._handle(Ether(data))
            except Exception:            # bozuk cerceve testi durdurmasin
                pass

    def _handle(self, f):
        if f.src == self.mac:
            return
        if ARP in f:
            a = f[ARP]
            if a.op == 1 and self.ip and a.pdst == self.ip:
                self.send(Ether(src=self.mac, dst=a.hwsrc) / ARP(op=2, hwsrc=self.mac, psrc=self.ip, hwdst=a.hwsrc, pdst=a.psrc))
            if a.op == 2:
                self.arp_cache[a.psrc] = a.hwsrc
            return
        if IPv6 in f:
            return self._handle6(f)
        if IP not in f:
            return
        p = f[IP]
        if BOOTP in p:
            return self._handle_dhcp(f)
        if not self.ip or p.dst != self.ip:
            return
        if ICMP in p:
            i = p[ICMP]
            if i.type == 8:
                self.send(Ether(src=self.mac, dst=f.src) / IP(src=self.ip, dst=p.src) / ICMP(type=0, id=i.id, seq=i.seq) / bytes(i.payload))
            elif i.type == 0:
                self._note("echo", p.src, i.id, i.seq, time.monotonic())
            elif i.type == 3:
                self._note("unreach", p.src, i.code)
        elif TCP in p:
            t = p[TCP]
            flags = int(t.flags)
            if flags & 0x02 and not flags & 0x10:            # SYN
                reply = "SA" if t.dport in self.tcp_listen else "RA"
                self.send(Ether(src=self.mac, dst=f.src) / IP(src=self.ip, dst=p.src) /
                          TCP(sport=t.dport, dport=t.sport, flags=reply, seq=1000, ack=t.seq + 1))
            elif flags & 0x12 == 0x12:                       # SYN-ACK
                self._note("synack", p.src, t.sport, t.dport)
                self.send(Ether(src=self.mac, dst=f.src) / IP(src=self.ip, dst=p.src) /
                          TCP(sport=t.dport, dport=t.sport, flags="R", seq=t.ack))
            elif flags & 0x04:
                self._note("rst", p.src, t.sport, t.dport)
        elif UDP in p:
            u = p[UDP]
            if u.dport in self.udp_listen:
                self.send(Ether(src=self.mac, dst=f.src) / IP(src=self.ip, dst=p.src) / UDP(sport=u.dport, dport=u.sport) / Raw(b"yanit"))
            else:
                self._note("udp", p.src, u.sport, u.dport)

    # ---------------- IPv4 ----------------
    def resolve(self, ip, tries=3):
        self.arp_cache.pop(ip, None)
        for _ in range(tries):
            self.send(Ether(src=self.mac, dst=BCAST) / ARP(op=1, hwsrc=self.mac, psrc=self.ip, pdst=ip))
            end = time.monotonic() + 1.0
            while time.monotonic() < end:
                if ip in self.arp_cache:
                    return self.arp_cache[ip]
                time.sleep(0.02)
        return None

    def _nexthop_mac(self, dst):
        same = dst.rsplit(".", 1)[0] == self.ip.rsplit(".", 1)[0]
        return self.resolve(dst if same else self.gw)

    def ping(self, dst, count=4, timeout=1.5):
        """Yanit alinan istek sayisi (0 = erisim yok)."""
        if not self.ip:
            return 0
        mac = self._nexthop_mac(dst)
        if not mac:
            return 0
        ident, ok = random.randint(1, 65000), 0
        for seq in range(count):
            self.send(Ether(src=self.mac, dst=mac) / IP(src=self.ip, dst=dst) / ICMP(type=8, id=ident, seq=seq) / Raw(b"anadolu-makina"))
            if self._wait(lambda e: e[0] == "echo" and e[2] == ident and e[3] == seq, timeout):
                ok += 1
        return ok

    def ping_series(self, dst, seconds, interval=0.5):
        """Surekli ping: (gonderilen, kaybolan, en uzun kesinti sn). Failover demolarinda kayip olcumu."""
        ident, sent, t0 = random.randint(1, 65000), 0, time.monotonic()
        mac = self._nexthop_mac(dst)
        while time.monotonic() - t0 < seconds:
            if not mac:
                mac = self._nexthop_mac(dst)
            if mac:
                self.send(Ether(src=self.mac, dst=mac) / IP(src=self.ip, dst=dst) / ICMP(type=8, id=ident, seq=sent) / Raw(b"seri"))
            sent += 1
            time.sleep(interval)
        time.sleep(1.5)
        with self.lock:
            got = {e[3] for e in self.seen if e[0] == "echo" and e[2] == ident}
        longest = run = 0
        for i in range(sent):
            run = run + 1 if i not in got else 0
            longest = max(longest, run)
        return sent, sent - len(got), longest * interval

    def tcp(self, dst, dport, tries=3, timeout=2.0):
        """'open' (SYN-ACK), 'closed' (RST) ya da 'filtered' (yanit yok)."""
        mac = self._nexthop_mac(dst)
        if not mac:
            return "filtered"
        for _ in range(tries):
            sport = random.randint(20000, 60000)
            self.send(Ether(src=self.mac, dst=mac) / IP(src=self.ip, dst=dst) / TCP(sport=sport, dport=dport, flags="S", seq=random.randint(1, 2**31)))
            e = self._wait(lambda e: e[0] in ("synack", "rst") and e[1] == dst and e[3] == sport, timeout)
            if e:
                return "open" if e[0] == "synack" else "closed"
        return "filtered"

    def udp(self, dst, dport, tries=3, timeout=2.0):
        mac = self._nexthop_mac(dst)
        if not mac:
            return False
        for _ in range(tries):
            sport = random.randint(20000, 60000)
            self.send(Ether(src=self.mac, dst=mac) / IP(src=self.ip, dst=dst) / UDP(sport=sport, dport=dport) / Raw(b"soru"))
            if self._wait(lambda e: e[0] == "udp" and e[1] == dst and e[3] == sport, timeout):
                return True
        return False

    def flow(self, dst, proto, dport=None):
        """ACL matrisi icin tek soru: bu akis gecti mi?"""
        if proto == "icmp":
            return self.ping(dst) > 0
        if proto == "tcp":
            return self.tcp(dst, dport) == "open"
        return self.udp(dst, dport)

    # ---------------- DHCP ----------------
    def _handle_dhcp(self, f):
        b = f[BOOTP]
        opts = {o[0]: o[1] for o in f[DHCP].options if isinstance(o, tuple)} if DHCP in f else {}
        mtype = opts.get("message-type")
        if b.op == 2 and b.chaddr[:6] == bytes.fromhex(self.mac.replace(":", "")):
            self._note("dhcp", mtype, b.yiaddr, opts.get("server_id"), opts.get("router"), b.xid, b.giaddr)
        elif b.op == 1 and self.rogue and mtype == 1:                     # kacak sunucu: her Discover'a Offer
            self.rogue_hits += 1
            self.send(Ether(src=self.mac, dst=BCAST) / IP(src=self.ip, dst="255.255.255.255") / UDP(sport=67, dport=68) /
                      BOOTP(op=2, xid=b.xid, yiaddr=self.rogue, siaddr=self.ip, chaddr=b.chaddr, flags=0x8000) /
                      DHCP(options=[("message-type", "offer"), ("server_id", self.ip), ("lease_time", 600),
                                    ("subnet_mask", "255.255.255.0"), ("router", self.ip), "end"]))

    def start_rogue_dhcp(self, offer_ip):
        """Kacak DHCP sunucusu: bu uc kendini ag gecidi gosteren Offer'lar yollar."""
        self.rogue, self.rogue_hits = offer_ip, 0

    def _dhcp_send(self, xid, mtype, extra=()):
        chaddr = bytes.fromhex(self.mac.replace(":", ""))
        self.send(Ether(src=self.mac, dst=BCAST) / IP(src="0.0.0.0", dst="255.255.255.255") / UDP(sport=68, dport=67) /
                  BOOTP(op=1, xid=xid, chaddr=chaddr, flags=0x8000) /
                  DHCP(options=[("message-type", mtype), ("hostname", self.name), *extra, "end"]))

    def dhcp(self, timeout=40, collect=4.0):
        """DORA. Adresi dondurur (alinamazsa None). self.offers: gorulen tum Offer'larin sunucu adresleri."""
        xid = random.randint(1, 2**31)
        self.offers = []
        end = time.monotonic() + timeout
        offer = None
        while time.monotonic() < end and not offer:
            self._dhcp_send(xid, "discover")
            offer = self._wait(lambda e: e[0] == "dhcp" and e[1] == 2 and e[5] == xid, 5)
        if not offer:
            return None
        time.sleep(collect)                                   # baska sunuculardan gelen Offer'lari da topla
        with self.lock:
            all_offers = [e for e in self.seen if e[0] == "dhcp" and e[1] == 2 and e[5] == xid]
        self.offers = sorted({e[3] for e in all_offers})
        legit = [e for e in all_offers if e[3] != self.avoid]
        if not legit:
            return None
        offer = legit[0]
        for _ in range(3):
            self._dhcp_send(xid, "request", [("requested_addr", offer[2]), ("server_id", offer[3])])
            ack = self._wait(lambda e: e[0] == "dhcp" and e[1] == 5 and e[5] == xid, 5)
            if ack:
                self.ip, self.gw, self.giaddr = ack[2], ack[4], ack[6]
                return self.ip
        return None

    # ---------------- saldiri: MAC tasmasi ----------------
    def mac_flood(self, count=60):
        """Rastgele kaynak MAC'li cerceveler: CAM tablosunu doldurma girisimi."""
        for _ in range(count):
            src = "02:%02x:%02x:%02x:%02x:%02x" % tuple(random.randint(0, 255) for _ in range(5))
            self.send(Ether(src=src, dst=BCAST) / ARP(op=1, hwsrc=src, psrc="0.0.0.0", pdst="172.16.255.254"))
            time.sleep(0.02)

    # ---------------- IPv6 ----------------
    def _handle6(self, f):
        p = f[IPv6]
        if ICMPv6DestUnreach in p:
            # Yonlendiricinin "yasak" hatasi asil paketi icinde tasir; scapy onu Echo Reply diye ayristirabilir.
            # Canli testte ACL'in engelledigi ping bu yuzden "gecti" gorunmustu.
            self._note("unreach6", p.src, p[ICMPv6DestUnreach].code, 0)
            return
        if ICMPv6ND_RA in p:
            rank = {1: 2, 0: 1, 3: 0}.get(int(p[ICMPv6ND_RA].prf), 1)      # RFC 4191: High > Medium > Low
            if self.gw6_mac is None or rank >= self.gw6_rank:
                self.gw6_mac, self.gw6, self.gw6_rank = f.src, p.src, rank
            if ICMPv6NDOptPrefixInfo in p:
                self.ra_prefix = p[ICMPv6NDOptPrefixInfo].prefix
        elif ICMPv6ND_NS in p:
            tgt = p[ICMPv6ND_NS].tgt
            if tgt in (self.ip6, self.ll6):
                self.send(Ether(src=self.mac, dst=f.src) / IPv6(src=tgt, dst=p.src if p.src != "::" else "ff02::1") /
                          ICMPv6ND_NA(tgt=tgt, R=0, S=1, O=1) / ICMPv6NDOptDstLLAddr(lladdr=self.mac))
        elif ICMPv6ND_NA in p:
            self.nd_cache[p[ICMPv6ND_NA].tgt] = f.src
        elif ICMPv6EchoRequest in p and p.dst in (self.ip6, self.ll6):
            e = p[ICMPv6EchoRequest]
            self.send(Ether(src=self.mac, dst=f.src) / IPv6(src=p.dst, dst=p.src) / ICMPv6EchoReply(id=e.id, seq=e.seq, data=e.data))
        elif ICMPv6EchoReply in p:
            e = p[ICMPv6EchoReply]
            self._note("echo6", p.src, e.id, e.seq)

    def slaac(self, timeout=30):
        """Router Solicitation yolla, RA'daki /64 onekinden adres kur. Adresi dondurur."""
        end = time.monotonic() + timeout
        while time.monotonic() < end and not self.ra_prefix:
            self.send(Ether(src=self.mac, dst="33:33:00:00:00:02") / IPv6(src=self.ll6, dst="ff02::2") /
                      ICMPv6ND_RS() / ICMPv6NDOptSrcLLAddr(lladdr=self.mac))
            time.sleep(2)
        if not self.ra_prefix:
            return None
        net = ipaddress.IPv6Network(self.ra_prefix + "/64")
        self.ip6 = str(net.network_address + int(ipaddress.IPv6Address(self.ll6)) % 2**64)
        return self.ip6

    def _resolve6(self, ip, tries=3):
        tail = ipaddress.IPv6Address(ip).packed[-3:]
        sol = "ff02::1:ff%02x:%02x%02x" % tuple(tail)
        mmac = "33:33:ff:%02x:%02x:%02x" % tuple(tail)
        self.nd_cache.pop(ip, None)
        for _ in range(tries):
            self.send(Ether(src=self.mac, dst=mmac) / IPv6(src=self.ip6, dst=sol) / ICMPv6ND_NS(tgt=ip) / ICMPv6NDOptSrcLLAddr(lladdr=self.mac))
            end = time.monotonic() + 1.0
            while time.monotonic() < end:
                if ip in self.nd_cache:
                    return self.nd_cache[ip]
                time.sleep(0.02)
        return None

    def ping6(self, dst, count=4, timeout=1.5):
        if not self.ip6:
            return 0
        same = ipaddress.IPv6Address(dst) in ipaddress.IPv6Network(self.ra_prefix + "/64")
        mac = self._resolve6(dst) if same else self.gw6_mac
        if not mac:
            return 0
        ident, ok = random.randint(1, 65000), 0
        for seq in range(count):
            self.send(Ether(src=self.mac, dst=mac) / IPv6(src=self.ip6, dst=dst) / ICMPv6EchoRequest(id=ident, seq=seq, data=b"anadolu"))
            if self._wait(lambda e: e[0] == "echo6" and e[2] == ident and e[3] == seq, timeout):
                ok += 1
        return ok


if __name__ == "__main__":
    import sys
    with Host(sys.argv[1]) as h:
        if not h.ip:
            print("DHCP:", h.dhcp())
        print(h.name, h.ip, "gw", h.gw, "-> ping gw:", h.ping(h.gw) if h.ip else "-")
        for t in sys.argv[2:]:
            print("ping", t, h.ping(t))
