#!/usr/bin/env python3
"""Config karsilastirma cekirdegi: sablondan uretilen satirlar <-> cihazin running-config'i.

Iki yerde kullanilir:
  - deploy.py   : basistan sonra geri okuyup eksik kalan satiri yakalar (ve bir kez daha basar)
  - extensions/drift : zaman icinde olusan sapmayi raporlar

IOS, girilen komutu running-config'te farkli yazabilir (port adi, varsayilanlar, interface range acilimi);
buradaki normalizasyon kurallari 13 gercek cihazin config'iyle ayarlanmistir.
"""
import re

# IOS'un running-config'te isme cevirdigi port numaralari
PORT_NAMES = {"21": "ftp", "25": "smtp", "53": "domain", "67": "bootps", "68": "bootpc", "80": "www", "110": "pop3"}
# Sablonda olup running-config'te gorunmeyen (varsayilan / tek seferlik) satirlar
NOT_SHOWN = re.compile(r"^(no shutdown|switchport$|exit)$")
# Cihazin kendiliginden ekledigi, sapma sayilmayacak satirlar
DEFAULTS = re.compile(r"^(negotiation auto|no ip address|duplex auto|speed auto|media-type rj45|no mop enabled|"
                      r"no mop sysid|ip virtual-reassembly.*|switchport$|tunnel mode gre ip|no ip redirects|"
                      r"standby version 1|ip ospf cost \d+|shutdown|switchport trunk encapsulation .*)$")
SECTION = re.compile(r"^(interface|router|vlan|ip access-list|ip dhcp pool|line)\b")
MANAGED_SECTIONS = ("interface", "ip access-list", "ip dhcp pool", "router")
# Her okumada degisen satirlar (zaman damgasi, boyut)
VOLATILE = re.compile(r"^(Building configuration|Current configuration|! Last configuration|! NVRAM config|ntp clock-period)")


def clean(text):
    """Degisken ve bos satirlari at, son 'end' satirindan sonrasini (cihaz prompt'u) kes."""
    lines = [l.rstrip() for l in text.splitlines() if l.strip() and not VOLATILE.match(l)]
    if "end" in lines:
        lines = lines[: len(lines) - lines[::-1].index("end")]
    return "\n".join(lines) + "\n"


def read_running(conn, tries=5):
    """running-config'i KARARLI okur: iki ardisik okuma birebir ayni olana kadar tekrarlar.

    Neden: yuk altindaki konsolda (9 sanal cihaz) 'show running-config' ciktisi ara sira satir kaybediyor
    (canli testte goruldu: var olan satirlar 'eksik' cikti, yedeklerde bos satirlar olustu). Tek okumaya
    guvenmek yanlis alarm ve bozuk yedek demek. Donus: (metin, kararli_mi)."""
    prev = None
    for _ in range(tries):
        cur = clean(conn.send_command("show running-config", read_timeout=180))
        if prev is not None and cur == prev and cur.rstrip().endswith("end"):
            return cur, True
        prev = cur
    return prev, False


def norm(line):
    line = re.sub(r"\s+", " ", line.strip())
    line = re.sub(r"^spanning-tree portfast$", "spanning-tree portfast edge", line)
    line = re.sub(r"\beq (\d+)\b", lambda m: "eq " + PORT_NAMES.get(m.group(1), m.group(1)), line)
    line = re.sub(r"^(permit|deny) (\S+) (\S+) 0\.0\.0\.0$", r"\1 \2 host \3", line)
    line = re.sub(r"^(ip ospf message-digest-key \d+ md5) .*$", r"\1 <anahtar>", line)   # anahtar/ozet karsilastirilmaz
    return line


def expand_range(header):
    """'interface range GigabitEthernet0/2 - 3' -> iki ayri 'interface ...' basligi"""
    m = re.match(r"interface range (\D+?)(\d+)/(\d+)(?: - (\d+))?$", header)
    if not m:
        return [header]
    name, slot, first, last = m.group(1), m.group(2), int(m.group(3)), int(m.group(4) or m.group(3))
    return [f"interface {name}{slot}/{n}" for n in range(first, last + 1)]


def parse(text):
    """Config metni -> {bolum basligi: [satirlar]}; bolum disi satirlar '' anahtarinda."""
    out, current = {"": []}, [""]
    for raw in text.splitlines():
        if not raw.strip():               # konsol ciktisinda araya giren bos satir: bolumu bitirmez
            continue
        if raw.strip().startswith("!"):
            if not raw.startswith(" "):
                current = [""]
            continue
        line = norm(raw)
        if not raw.startswith(" "):
            if SECTION.match(line):
                current = expand_range(line)
                for c in current:
                    out.setdefault(c, [])
            else:
                current = [""]
                out[""].append(line)
        else:
            for c in current:
                out[c].append(line)
    return out


def merge(texts):
    """Birden cok faz metnini tek 'altin' yapida birlestirir."""
    merged = {}
    for text in texts:
        for section, lines in parse(text).items():
            bucket = merged.setdefault(section, [])
            for l in lines:
                if l not in bucket:
                    bucket.append(l)
    return merged


def satisfied(line, running_lines):
    if NOT_SHOWN.match(line) or line in running_lines:
        return True
    if line == "ip routing":             # IOSvL2'de acikken yazmaz; kapaliysa "no ip routing" yazar
        return "no ip routing" not in running_lines
    if line.startswith("switchport trunk encapsulation"):
        return True
    if line.startswith(("no passive-interface", "no switchport")):
        return False                     # bunlar running-config'te aynen gorunur
    if line.startswith("no "):           # genel "no X": X yoksa istek yerine gelmis demektir
        return line[3:] not in running_lines
    return False


def compare(golden, running_text, report_extra=True):
    """golden: merge() ciktisi. Donus: (eksik, fazla) -> [(bolum, satir), ...]"""
    running = parse(running_text)
    missing, extra = [], []
    for section, lines in golden.items():
        r_lines = running.get(section)
        if r_lines is None:
            if section and any(not NOT_SHOWN.match(l) and not l.startswith("no ") for l in lines):
                missing.append((section, "(bolum yok)"))
            continue
        for l in lines:
            if not satisfied(l, r_lines):
                missing.append((section or "genel", l))
        if report_extra and section.startswith(MANAGED_SECTIONS):
            wanted = set(lines)
            extra += [(section, l) for l in r_lines if l not in wanted and not DEFAULTS.match(l)]
    return missing, extra


def missing_lines(rendered_lines, running_text):
    """deploy icin kisayol: basilan satirlardan cihazda bulunmayanlar."""
    return compare(merge(["\n".join(rendered_lines)]), running_text, report_extra=False)[0]
