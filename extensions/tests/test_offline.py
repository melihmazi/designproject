"""Cevrimdisi testler: cihaz gerektirmez. Envanter tutarliligi, sablon uretimi ve ACL politika matrisi."""
import ipaddress
import re
from collections import Counter
from pathlib import Path

import pytest

import deploy

PROJECT = Path(__file__).resolve().parents[2]
PHASES = (1, 2, 3)


# ------------------------------------------------------------------ envanter
def test_on_uc_ios_cihazi(devices):
    assert len(devices) == 13
    assert Counter(d["role"] for d in devices) == {"core": 2, "dag": 2, "access": 5, "branch_sw": 1,
                                                   "snr": 1, "iss": 1, "fab": 1}


def test_konsol_portlari_tanimli_ve_benzersiz(devices):
    ports = [d["console_port"] for d in devices]
    assert None not in ports, "consoles.yaml eksik: gen_inventory.py calistir"
    assert len(set(ports)) == len(ports)


def test_router_id_benzersiz(devices):
    rids = [d["router_id"] for d in devices if d.get("router_id")]
    assert len(rids) == 6 and len(set(rids)) == 6


def test_link_portlari_cakismiyor(inventory):
    ends = [(a, pa) for a, pa, b, pb in inventory["links"]] + [(b, pb) for a, pa, b, pb in inventory["links"]]
    dup = [e for e, n in Counter(ends).items() if n > 1]
    assert not dup, f"ayni port iki linkte: {dup}"
    assert len(inventory["links"]) == 23


def test_hsrp_yuk_dagilimi_4_3(inventory):
    active = Counter(s["active"] for s in inventory["network"]["svis"])
    assert active == {"MRK-DAG1": 4, "MRK-DAG2": 3}


def test_ospf_beklentisi_simetrik_ve_14_giris(inventory):
    ospf = inventory["expected"]["ospf"]
    assert sum(len(v) for v in ospf.values()) == 14
    for dev, peers in ospf.items():
        for p in peers:
            assert any(q["peer"] == dev for q in ospf[p["peer"]]), f"{dev}->{p['peer']} tek yonlu"


def test_stp_koku_hsrp_active_ile_ayni(inventory, devices):
    """Yol haritasi Bolum 5.5: bir VLAN'in STP koku = o VLAN'in HSRP active'i."""
    for d in devices:
        if d["role"] != "dag":
            continue
        root = {int(v) for v in str(d["stp_root_vlans"]).split(",")}
        mine = {s["vlan"] for s in inventory["network"]["svis"] if s["active"] == d["name"]}
        assert mine <= root, f"{d['name']}: HSRP active {mine} ama STP kok {root}"


# ------------------------------------------------------------------ sablonlar
def render_all(devices):
    out = {}
    for d in devices:
        lines = []
        for ph in PHASES:
            try:
                lines += deploy.render(d, ph)
            except deploy.TemplateNotFound:
                pass
        out[d["name"]] = lines
    return out


def test_her_cihaz_icin_config_uretiliyor(devices):
    rendered = render_all(devices)
    for name, lines in rendered.items():
        assert len(lines) >= 10, f"{name}: yalniz {len(lines)} satir"
        assert not [l for l in lines if "{{" in l or "None" in l], f"{name}: doldurulmamis degisken"


def test_ip_adresleri_benzersiz(devices):
    seen = Counter()
    for name, lines in render_all(devices).items():
        for l in lines:
            m = re.match(r"\s*ip address (\d+\.\d+\.\d+\.\d+) ", l)
            if m:
                seen[m.group(1)] += 1
    assert not [ip for ip, n in seen.items() if n > 1]


def test_p2p_linklerin_iki_ucu_ayni_alt_agda(devices):
    """Her /30 alt agi tam iki cihazda gorunmeli (Bolum 5.2)."""
    nets = Counter()
    for name, lines in render_all(devices).items():
        for l in lines:
            m = re.match(r"\s*ip address (\S+) (255\.255\.255\.252)", l)
            if m:
                nets[ipaddress.ip_interface(f"{m.group(1)}/{m.group(2)}").network] += 1
    assert nets and all(n == 2 for n in nets.values()), {str(k): v for k, v in nets.items() if v != 2}


def test_faz1_ip_silmiyor(devices):
    """Faz 2'den sonra Faz 1 yeniden basilirsa IP'ler silinmemeli."""
    for d in devices:
        try:
            assert "no ip address" not in [l.strip() for l in deploy.render(d, 1)], d["name"]
        except deploy.TemplateNotFound:
            pass


def test_aciklama_no_switchporttan_sonra(devices):
    """IOS 'no switchport' ile description'i siler (canli testte goruldu); sira korunmali."""
    for d in devices:
        if d["role"] not in ("core", "dag"):
            continue
        lines = [l.strip() for l in deploy.render(d, 1)]
        for i, l in enumerate(lines):
            if l == "no switchport" and lines[i - 1].startswith("interface Port-channel"):
                assert lines[i + 1].startswith("description"), d["name"]


# ------------------------------------------------------------------ ACL politika matrisi
def parse_acls(lines):
    acls, bindings, cur, intf = {}, {}, None, None
    for raw in lines:
        l = raw.strip()
        if l.startswith("ip access-list extended"):
            cur, intf = l.split()[-1], None
            acls[cur] = []
        elif l.startswith("interface"):
            cur, intf = None, l.split()[1]
        elif cur and l.split()[0] in ("permit", "deny"):
            acls[cur].append(l.split())
        elif intf and l.startswith("ip access-group"):
            bindings[(intf, l.split()[3])] = l.split()[2]
        elif not raw.startswith(" "):
            cur = intf = None
    return acls, bindings


def take_addr(tok):
    if tok[0] == "any":
        return ipaddress.ip_network("0.0.0.0/0"), tok[1:]
    if tok[0] == "host":
        return ipaddress.ip_network(tok[1] + "/32"), tok[2:]
    wild = int(ipaddress.ip_address(tok[1]))
    return ipaddress.ip_network(f"{tok[0]}/{32 - bin(wild).count('1')}"), tok[2:]


PORTS = {"bootpc": 68, "bootps": 67}


def take_port(tok):
    if tok and tok[0] == "eq":
        return PORTS.get(tok[1]) or int(tok[1]), tok[2:]
    return None, tok


def acl_permits(entries, pkt):
    for e in entries:
        action, proto, rest = e[0], e[1], e[2:]
        src, rest = take_addr(rest)
        sport, rest = take_port(rest)
        dst, rest = take_addr(rest)
        dport, rest = take_port(rest)
        if proto != "ip" and proto != pkt["proto"]:
            continue
        if ipaddress.ip_address(pkt["src"]) not in src or ipaddress.ip_address(pkt["dst"]) not in dst:
            continue
        if sport is not None and sport != pkt.get("sport"):
            continue
        if dport is not None and dport != pkt.get("dport"):
            continue
        if "established" in rest and not pkt.get("reply"):
            continue
        if proto == "icmp" and rest and rest[0] in ("echo", "echo-reply") and rest[0] != pkt.get("icmp"):
            continue
        return action == "permit"
    return False


def forward(pkt, rules):
    """Paket kaynak SVI/arayuz giris ACL'inden ve hedef SVI cikis ACL'inden gecer mi?"""
    for net, direction, entries in rules:
        ip = pkt["src"] if direction == "in" else pkt["dst"]
        if ipaddress.ip_address(ip) in net and not acl_permits(entries, pkt):
            return False
    return True


def flow_ok(src, dst, proto, dport, rules):
    if proto == "icmp":
        req = dict(src=src, dst=dst, proto="icmp", icmp="echo")
        rep = dict(src=dst, dst=src, proto="icmp", icmp="echo-reply")
    else:
        req = dict(src=src, dst=dst, proto=proto, sport=40000, dport=dport)
        rep = dict(src=dst, dst=src, proto=proto, sport=dport, dport=40000, reply=True)
    return forward(req, rules) and forward(rep, rules)


@pytest.fixture(scope="module")
def rules(devices, inventory):
    by_name = {d["name"]: d for d in devices}
    out = []
    acls, bind = parse_acls(deploy.render(by_name["MRK-DAG1"], 3))
    for s in inventory["network"]["svis"]:
        net = ipaddress.ip_network(s["prefix"] + ".0/24")
        for direction in ("in", "out"):
            name = bind.get((f"Vlan{s['vlan']}", direction))
            if name:
                out.append((net, direction, acls[name]))
    acls, bind = parse_acls(deploy.render(by_name["FAB-RTR"], 3))
    out.append((ipaddress.ip_network("172.18.10.0/24"), "in", acls[bind[("GigabitEthernet0/1", "in")]]))
    return out


def test_dag1_ve_dag2_ayni_acl(devices):
    by_name = {d["name"]: d for d in devices}
    a = [l for l in deploy.render(by_name["MRK-DAG1"], 3) if "dhcp" not in l and not l.startswith((" network", " default-router", " dns-server", " domain-name"))]
    b = deploy.render(by_name["MRK-DAG2"], 3)
    assert a == b


# Yol haritasi Bolum 12.3 (A1-A12) + A4'un ikinci yarisi
SAT, PER, BIS, MSF, FAB = "172.16.10.11", "172.16.20.11", "172.16.30.11", "172.16.60.11", "172.18.10.11"
MATRIX = [
    ("A1  BIS -> SAT ping", BIS, SAT, "icmp", None, True),
    ("A2  SAT -> PER ping", SAT, PER, "icmp", None, False),
    ("A3  SAT -> SNC-WEB http", SAT, "172.16.50.12", "tcp", 80, True),
    ("A4a SAT -> SNC-DOSYA ping", SAT, "172.16.50.14", "icmp", None, True),
    ("A4b SAT -> SNC-DOSYA ssh (FTP disi port)", SAT, "172.16.50.14", "tcp", 22, False),
    ("A5  SAT -> switch yonetimi", SAT, "172.16.90.11", "icmp", None, False),
    ("A6  BIS -> switch yonetimi", BIS, "172.16.90.11", "icmp", None, True),
    ("A7  MSF -> SNC-DNS udp 53", MSF, "172.16.50.11", "udp", 53, True),
    ("A8  MSF -> SNC-WEB ping", MSF, "172.16.50.12", "icmp", None, False),
    ("A9  MSF -> internet", MSF, "203.0.113.1", "icmp", None, True),
    ("A10 FAB -> SNC-WEB http", FAB, "172.16.50.12", "tcp", 80, True),
    ("A11 FAB -> BIS ping", FAB, BIS, "icmp", None, False),
    ("A12 SAT -> FAB ping", SAT, FAB, "icmp", None, True),
    ("ek  PER -> SAT ping", PER, SAT, "icmp", None, False),
    ("ek  SAT -> internet", SAT, "203.0.113.1", "icmp", None, True),
    ("ek  MSF -> SNC-POSTA smtp", MSF, "172.16.50.13", "tcp", 25, False),
    ("ek  BIS -> SNC-DOSYA ssh (tam erisim)", BIS, "172.16.50.14", "tcp", 22, True),
    ("ek  SAT -> SNC-POSTA imap", SAT, "172.16.50.13", "tcp", 143, True),
]


@pytest.mark.parametrize("label,src,dst,proto,dport,expected", MATRIX, ids=[m[0] for m in MATRIX])
def test_acl_matrisi(rules, label, src, dst, proto, dport, expected):
    assert flow_ok(src, dst, proto, dport, rules) is expected


def test_stub_alan_tanimi_tunelden_once(devices):
    """Canli testte goruldu: tunel yapilandirilirken IOS Area 300 icin "is being deleted, please try later"
    diyerek stub komutunu reddedebiliyor. Alan tanimi tunel arayuzunden once gelmeli."""
    for d in devices:
        if d["role"] not in ("snr", "fab"):
            continue
        lines = [l.strip() for l in deploy.render(d, 3)]
        stub = next(i for i, l in enumerate(lines) if l.startswith("area 300 stub"))
        tunnel = lines.index("interface Tunnel0")
        assert stub < tunnel, d["name"]


def test_stub_bayragi_iki_ucta_var(devices):
    """Stub bayragi uyusmazsa OSPF komsulugu hic kurulmaz."""
    by = {d["name"]: [l.strip() for l in deploy.render(d, 3)] for d in devices if d["role"] in ("snr", "fab")}
    assert "area 300 stub no-summary" in by["SNR-RTR"]
    assert "area 300 stub" in by["FAB-RTR"]
