#!/usr/bin/env python3
"""Faz 6-B: pcap dosyalarindan protokol analizi raporu (Markdown) uretir. Wireshark'in yaninda, tekrarlanabilir kanit.

    python core/scripts/pcap_report.py docs/captures/*.pcap -o docs/captures/analiz.md

Cozulen protokoller: LACP, PVST+ (STP), HSRP, OSPF, CDP, ARP. Birden cok dosya zaman damgasina gore birlestirilir
(ornegin bir LACP demetinin iki uyesi), boylece OSPF komsuluk kurulumu tek zaman cizgisinde gorulur.
"""
import argparse
import glob
import ipaddress
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.all import ARP, BOOTP, DHCP, GRE, ICMP, Dot1Q, IP, STP, load_contrib, rdpcap  # noqa: E402
from scapy.layers.hsrp import HSRP  # noqa: E402

load_contrib("ospf")
load_contrib("lacp")
from scapy.contrib.lacp import LACP  # noqa: E402
from scapy.contrib.ospf import OSPF_Hdr, OSPF_Hello  # noqa: E402

OSPF_TYPES = {1: "Hello", 2: "DBD (Database Description)", 3: "LSR (Link State Request)",
              4: "LSU (Link State Update)", 5: "LSAck"}
HSRP_STATES = {0: "Initial", 1: "Learn", 2: "Listen", 4: "Speak", 8: "Standby", 16: "Active"}
HSRP_OPS = {0: "Hello", 1: "Coup", 2: "Resign"}
LACP_BITS = ["Activity(aktif)", "Timeout(kisa)", "Aggregation", "Synchronization", "Collecting", "Distributing",
             "Defaulted", "Expired"]


def lacp_flags(value):
    return ", ".join(name for bit, name in enumerate(LACP_BITS) if value & (1 << bit)) or "-"


def vlan_of(pkt):
    return pkt[Dot1Q].vlan if pkt.haslayer(Dot1Q) else None


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def analyze(files):
    packets = []
    for f in files:
        for p in rdpcap(str(f)):
            packets.append((float(p.time), Path(f).stem, p))
    packets.sort(key=lambda x: x[0])
    if not packets:
        sys.exit("pcap dosyalarinda paket yok")
    t0 = packets[0][0]
    md = ["# Paket Analizi Raporu (Faz 6-B)\n",
          f"Kaynak dosyalar: {', '.join('`' + Path(f).name + '`' for f in files)}\n",
          f"Toplam {len(packets)} paket, sure {packets[-1][0] - t0:.0f} sn. Zamanlar ilk pakete goredir.\n"]

    counts = Counter()
    lacp, stp, hsrp, ospf = defaultdict(list), defaultdict(list), defaultdict(list), []
    for t, src_file, p in packets:
        rel = t - t0
        if p.haslayer(LACP):
            counts["LACP"] += 1
            lacp[p.src].append((rel, p[LACP]))
        elif p.haslayer(STP):
            counts["STP / PVST+"] += 1
            s = p[STP]
            stp[s.bridgeid & 0xFFF].append((rel, s))
        elif p.haslayer(HSRP):
            counts["HSRP"] += 1
            hsrp[p[HSRP].group].append((rel, p[IP].src, p[HSRP], vlan_of(p)))
        elif p.haslayer(OSPF_Hdr):
            counts["OSPF"] += 1
            ospf.append((rel, p))
        elif p.dst == "01:00:0c:cc:cc:cc":
            counts["CDP / VTP / DTP (Cisco L2)"] += 1
        elif p.haslayer(ARP):
            counts["ARP"] += 1
        else:
            counts["Diger"] += 1

    md.append("## 1. Protokol dagilimi\n")
    md.append(table(["Protokol", "Paket"], counts.most_common()))

    # ---------------- LACP ----------------
    if lacp:
        md.append("## 2. LACP (IEEE 802.3ad, Slow Protocols 0x8809)\n")
        rows = []
        for mac, items in sorted(lacp.items()):
            times = [t for t, _ in items]
            gap = (times[-1] - times[0]) / (len(times) - 1) if len(times) > 1 else 0
            first, last = items[0][1], items[-1][1]
            rows.append([mac, len(items), f"{gap:.1f} sn", last.actor_system, last.actor_key, last.actor_port_number,
                         lacp_flags(first.actor_state), lacp_flags(last.actor_state), last.partner_system])
        md.append(table(["Gonderen MAC", "PDU", "Ort. aralik", "Actor sistem", "Key", "Port", "Ilk PDU bayraklari",
                         "Son PDU bayraklari", "Partner sistem (son)"], rows))
        md.append("Yorum: `Activity` biti iki tarafta da set, yani iki uc `mode active`. Ilk PDU'da partner bilinmez "
                  "(00:00:00:00:00:00); `Synchronization + Collecting + Distributing` bitleri geldiginde port demete "
                  "katilmis (`P`) demektir. `Timeout(kisa)` biti yoksa PDU araligi 30 sn, zaman asimi 90 sn'dir.\n")

    # ---------------- STP ----------------
    if stp:
        md.append("## 3. Rapid-PVST+ BPDU'lari (hedef 01:00:0c:cc:cc:cd)\n")
        rows = []
        for vlan, items in sorted(stp.items()):
            last = items[-1][1]
            bridges = sorted({f"{s.bridgeid - vlan}/{s.bridgemac}" for _, s in items})
            times = [t for t, _ in items]
            gap = (times[-1] - times[0]) / (len(times) - 1) * len(bridges) if len(times) > 1 else 0
            rows.append([vlan, len(items), f"{last.rootid - vlan}", last.rootmac, "<br>".join(bridges),
                         f"{gap:.1f} sn", last.hellotime, last.maxage, last.fwddelay])
        md.append(table(["VLAN", "BPDU", "Kok onceligi", "Kok MAC", "Gorulen kopruler (oncelik/MAC)",
                         "Kopru basina aralik", "Hello", "MaxAge", "FwdDelay"], rows))
        md.append("Yorum: oncelik alani `oncelik + VLAN no` olarak tasinir (extended system ID); tabloda VLAN cikarilmis "
                  "hali var. Kok onceligi 4096 olan kopru o VLAN'in kokudur; plan: VLAN 10/30/50/90/254 -> DAG1, "
                  "VLAN 20/40/60 -> DAG2.\n")

    # ---------------- HSRP ----------------
    if hsrp:
        md.append("## 4. HSRP (UDP 1985, 224.0.0.2)\n")
        rows, events = [], []
        for group, items in sorted(hsrp.items()):
            per_src = defaultdict(list)
            for t, src, h, vlan in items:
                per_src[src].append((t, h))
            for src, lst in sorted(per_src.items()):
                last = lst[-1][1]
                states, prev = [], None
                for t, h in lst:
                    if h.opcode != 0:
                        events.append((t, group, src, HSRP_OPS.get(h.opcode, h.opcode)))
                    if h.state != prev:
                        states.append(f"{HSRP_STATES.get(h.state, h.state)}@{t:.0f}s")
                        prev = h.state
                rows.append([group, src, last.priority, last.virtualIP, f"{last.hellotime}/{last.holdtime}",
                             len(lst), " -> ".join(states)])
        md.append(table(["Grup", "Kaynak IP", "Oncelik", "Sanal IP", "Hello/Hold", "Paket", "Durum gecisleri"], rows))
        if events:
            md.append("**Ozel mesajlar (failover ani):**\n")
            md.append(table(["Zaman", "Grup", "Kaynak", "Mesaj"],
                            [[f"{t:.1f} sn", g, s, m] for t, g, s, m in sorted(events)]))
        md.append("Yorum: `Speak -> Standby -> Active` acilis sirasidir. `Resign` aktif yonlendiricinin gorevi "
                  "biraktigini (ornegin SVI kapatildi), `Coup` ise daha yuksek oncelikli yonlendiricinin `preempt` ile "
                  "aktifligi geri aldigini gosterir. Kimlik dogrulama alani varsayilan duz metin `cisco`'dur.\n")

    # ---------------- OSPF ----------------
    if ospf:
        md.append("## 5. OSPF (IP protokol 89)\n")
        per_type = Counter(p[OSPF_Hdr].type for _, p in ospf)
        first = {}
        for t, p in ospf:
            first.setdefault((p[OSPF_Hdr].type, p[IP].src), t)
        md.append(table(["Tip", "Ad", "Paket"], [[k, OSPF_TYPES.get(k, "?"), v] for k, v in sorted(per_type.items())]))
        hello = next((p for _, p in ospf if p.haslayer(OSPF_Hello)), None)
        if hello is not None:
            h, hdr = hello[OSPF_Hello], hello[OSPF_Hdr]
            md.append(table(["Alan", "Hello araligi", "Dead araligi", "Ag maskesi", "DR", "BDR", "VLAN", "Hedef"],
                            [[int(ipaddress.ip_address(hdr.area)), f"{h.hellointerval} sn", f"{h.deadinterval} sn", h.mask, h.router, h.backup,
                              vlan_of(hello), hello[IP].dst]]))
        routers = sorted({(p[OSPF_Hdr].src, p[IP].src) for _, p in ospf})
        md.append(table(["Router-ID", "Arayuz IP"], routers))
        md.append("**Komsuluk kurulumu zaman cizgisi (her tip/kaynak icin ilk gorulme):**\n")
        md.append(table(["Zaman", "Kaynak", "Paket"],
                        [[f"{t:.1f} sn", src, OSPF_TYPES.get(typ, typ)] for (typ, src), t in sorted(first.items(), key=lambda x: x[1])]))
        md.append("Yorum: Hello'lar karsilikli gorulunce komsuluk 2-Way'e, DBD degisimiyle ExStart/Exchange'e, "
                  "LSR/LSU/LSAck ile Loading ve ardindan Full durumuna gecer. DR ve BDR alanlarinin 0.0.0.0 olmasi "
                  "arayuzun `ip ospf network point-to-point` oldugunu (DR secimi yok) dogrular.\n")

    # ---------------- GRE ----------------
    gre = [(t - t0, p) for t, _, p in packets if p.haslayer(GRE)]
    if gre:
        md.append("## 6. GRE tuneli (IP protokol 47)\n")
        outer = Counter((p[IP].src, p[IP].dst) for _, p in gre)
        md.append(table(["Dis kaynak", "Dis hedef", "Paket"], [[s, d, n] for (s, d), n in outer.most_common()]))
        inner = Counter()
        for _, p in gre:
            ip_in = p[GRE].payload
            if ip_in.haslayer(OSPF_Hdr):
                kind = "OSPF " + OSPF_TYPES.get(ip_in[OSPF_Hdr].type, "?").split(" ")[0]
            elif ip_in.haslayer(ICMP):
                kind = "ICMP " + ("echo" if ip_in[ICMP].type == 8 else "echo-reply" if ip_in[ICMP].type == 0 else str(ip_in[ICMP].type))
            else:
                kind = ip_in.summary()[:40]
            src = ip_in[IP].src if ip_in.haslayer(IP) else "?"
            dst = ip_in[IP].dst if ip_in.haslayer(IP) else "?"
            inner[(kind, src, dst)] += 1
        md.append("**Tunelin icindeki (ic) paketler:**\n")
        md.append(table(["Ic paket", "Ic kaynak", "Ic hedef", "Adet"], [[k, s, d, n] for (k, s, d), n in inner.most_common(12)]))
        sizes = [len(p) for _, p in gre]
        md.append(f"GRE ek yuku: dis IP basligi 20 bayt + GRE 4 bayt = 24 bayt. Yakalanan en buyuk cerceve {max(sizes)} bayt. "
                  "Tunelde `ip mtu 1400` ve `ip tcp adjust-mss 1360` bu ek yuk yuzunden parcalanmayi onlemek icindir.\n")
        nat = Counter((p[IP].src, p[IP].dst) for _, _, p in packets
                      if p.haslayer(ICMP) and not p.haslayer(GRE) and p.haslayer(IP) and p[ICMP].type == 8)
        if nat:
            md.append("**Tunel disi ICMP echo (NAT kaniti):**\n")
            md.append(table(["Kaynak", "Hedef", "Paket"], [[s, d, n] for (s, d), n in nat.most_common()]))
            md.append("Yorum: Tesis LAN'indan (172.18.10.1) internete giden paket tunelin icinde ozel adresle gelir, "
                      "SNR-RTR'da PAT ile 198.51.100.1 kaynak adresine cevrilip tunel disinda ISS'e gider.\n")

    # ---------------- DHCP ----------------
    dhcp = [(t - t0, p) for t, _, p in packets if p.haslayer(BOOTP) and p.haslayer(DHCP)]
    if dhcp:
        md.append("## 7. DHCP (UDP 67/68)\n")
        names = {1: "Discover", 2: "Offer", 3: "Request", 5: "ACK", 6: "NAK", 7: "Release", 8: "Inform"}
        rows = []
        for t, p in dhcp:
            mtype = next((v for k, v in (o for o in p[DHCP].options if isinstance(o, tuple)) if k == "message-type"), None)
            ip = p[BOOTP].underlayer.underlayer            # BOOTP'yi tasiyan IP basligi (GRE icindeyse ic baslik)
            rows.append([f"{t:.1f} sn", names.get(mtype, mtype), ip.src, ip.dst, p[BOOTP].giaddr, p[BOOTP].yiaddr,
                         "evet" if p.haslayer(GRE) else "hayir"])
        # Fabrika ayarindaki IOSv acilista her arayuzden cevapsiz Discover yollar (autoinstall); bunlar ozetlenir
        noise = [r for r in rows if r[1] == "Discover" and r[4] == "0.0.0.0" and r[6] == "hayir"]
        shown = [r for r in rows if r not in noise] or rows
        if len(shown) != len(rows):
            md.append(f"{len(noise)} adet relay'siz Discover (cihaz acilisindaki autoinstall denemeleri ve istemcinin "
                      "ilk yayinlari) tabloda gosterilmedi." + chr(10))
        md.append(table(["Zaman", "Mesaj", "Kaynak IP", "Hedef IP", "giaddr (relay)", "yiaddr (verilen)", "GRE icinde"], shown[:16]))
        md.append("Yorum: `giaddr` 0.0.0.0 ise istek sunucuya dogrudan (ayni VLAN'da) ulasmistir. `giaddr` dolu ise "
                  "paket bir relay'den (`ip helper-address`) gecmistir: relay yayini unicast'e cevirir, kendi arayuz "
                  "adresini `giaddr`'a yazar ve sunucu havuzu bu adrese gore secer. Tesis istemcisinin DORA'si "
                  "FAB-RTR (172.18.10.1) -> GRE tuneli -> MRK-DAG1 Loopback0 (172.20.20.3) yolunu izler.\n")

    return "\n".join(md)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcap", nargs="+")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()
    files = sorted(f for pattern in args.pcap for f in (glob.glob(pattern) or [pattern]))
    report = analyze(files)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Rapor yazildi: {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(report)


if __name__ == "__main__":
    main()
