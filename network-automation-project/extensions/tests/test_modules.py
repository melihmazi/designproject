"""Genisletme modullerinin cevrimdisi testleri: IPv6 sablonlari, izleme alarm mantigi, Ansible envanteri.

Cihaz gerektirmez.   pytest extensions/tests/test_modules.py
"""
import importlib.util
import ipaddress
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "core" / "scripts"))
import deploy  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, PROJECT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def devices():
    return deploy.load_inventory()


# ------------------------------------------------------------------ IPv6
@pytest.fixture(scope="module")
def v6():
    return load("extensions/ipv6/ipv6.py", "ipv6mod")


def test_ipv6_yalniz_l3_cihazlara_uretilir(v6, devices):
    from jinja2 import TemplateNotFound
    made = []
    for d in devices:
        try:
            v6.render(d)
            made.append(d["name"])
        except TemplateNotFound:
            assert d["role"] in ("access", "branch_sw")
    assert sorted(made) == ["FAB-RTR", "ISS-RTR", "MRK-CORE1", "MRK-CORE2", "MRK-DAG1", "MRK-DAG2", "SNR-RTR"]


def test_ipv6_adresleri_gecerli_ve_benzersiz(v6, devices):
    seen = {}
    for d in devices:
        if d["role"] in ("access", "branch_sw"):
            continue
        for line in v6.render(d):
            if line.strip().startswith("ipv6 address "):
                iface = ipaddress.IPv6Interface(line.split()[2])
                assert iface.ip not in seen, f"{iface.ip}: {d['name']} ve {seen[iface.ip]}"
                seen[iface.ip] = d["name"]
                assert iface.ip in ipaddress.IPv6Network("2001:db8::/32")
    assert len(seen) == 6 + 14 + 3 + 1          # 6 loopback + 2x7 SVI + WAN iki uc ve internet + FAB LAN


def test_ipv6_stub_alan_tunelden_once(v6, devices):
    """IPv4'te gorulen 'Area 300 is being deleted' hatasinin IPv6 karsiligi icin ayni sira kurali."""
    for d in devices:
        if d["role"] in ("snr", "fab"):
            lines = [l.strip() for l in v6.render(d)]
            assert next(i for i, l in enumerate(lines) if l.startswith("area 300 stub")) < lines.index("interface Tunnel0")


def test_ipv6_acl_komsu_kesfine_izin_verir(v6, devices):
    """Acik 'deny' satirlari ND'yi keserse ag gecidi cozulemez; her ACL once nd-ns / nd-na izni vermeli."""
    for d in devices:
        if d["role"] not in ("dag", "fab"):
            continue
        lines = [l.strip() for l in v6.render(d)]
        for i, l in enumerate(lines):
            if l.startswith("ipv6 access-list"):
                body = []
                for x in lines[i + 1:]:
                    if not x.startswith(("permit", "deny")):
                        break
                    body.append(x)
                first_deny = next(k for k, x in enumerate(body) if x.startswith("deny"))
                assert "permit icmp any any nd-ns" in body[:first_deny] and "permit icmp any any nd-na" in body[:first_deny], l


def test_ipv6_geri_alma_her_satiri_karsilar(v6, devices):
    """Basilan her 'ipv6 address' ve 'ipv6 ospf' satirinin geri alma sablonunda 'no' karsiligi olmali."""
    for d in devices:
        if d["role"] in ("access", "branch_sw"):
            continue
        fwd = [l.strip() for l in v6.render(d)]
        back = [l.strip() for l in v6.render(d, rollback=True)]
        for l in fwd:
            if l.startswith(("ipv6 address", "ipv6 ospf 1 area", "ipv6 traffic-filter", "ipv6 route")):
                assert "no " + l in back, f"{d['name']}: {l}"


def test_ipv6_ra_tercihi_hsrp_active_ile_ayni(v6, devices):
    for d in devices:
        if d["role"] != "dag":
            continue
        lines, current, high = v6.render(d), None, set()
        for l in lines:
            if l.startswith("interface Vlan"):
                current = int(l.split("Vlan")[1])
            elif l.strip() == "ipv6 nd router-preference High":
                high.add(current)
        assert high == {s["vlan"] for s in d["net"]["svis"] if s["active"] == d["name"]}


# ------------------------------------------------------------------ izleme
@pytest.fixture(scope="module")
def mon():
    return load("extensions/monitoring/monitor.py", "monmod")


def _ifs(**oper):
    return {k: {"admin": 1, "oper": v} for k, v in oper.items()}


def test_izleme_kritik_portlar(mon, devices):
    import yaml
    data = yaml.safe_load((PROJECT / "core" / "inventory" / "devices.yaml").read_text(encoding="utf-8"))
    crit = mon.critical_ports(devices, data)
    assert {"Gi0/0", "Gi0/1", "Gi0/2", "Gi0/3", "Gi1/0", "Po1", "Po2"} <= crit["MRK-CORE1"]
    assert "Tu0" in crit["SNR-RTR"] and "Tu0" in crit["FAB-RTR"]
    assert crit["MRK-ERS-SAT"] == {"Gi0/0", "Gi0/1"}


def test_izleme_link_alarmi_ve_olay(mon):
    crit = {"SW": {"Gi0/0", "Gi0/1"}}
    before, _ = mon.evaluate({"SW": {"uptime_sn": 100, "sysname": "SW", "cpu": 3, "arayuzler": _ifs(**{"Gi0/0": 1, "Gi0/1": 1})}}, crit, {})
    assert before["cihazlar"]["SW"]["durum"] == "OK" and not before["alarmlar"]
    after, events = mon.evaluate({"SW": {"uptime_sn": 130, "sysname": "SW", "cpu": 3, "arayuzler": _ifs(**{"Gi0/0": 2, "Gi0/1": 1})}}, crit, before["cihazlar"])
    assert after["cihazlar"]["SW"]["durum"] == "ALARM"
    assert after["alarmlar"] == [{"cihaz": "SW", "tur": "LINK", "ayrinti": "Gi0/0 up degil"}]
    assert [e["olay"] for e in events] == ["Gi0/0 up -> down"]


def test_izleme_erisilemeyen_cihaz(mon):
    prev = {"SW": {"durum": "OK", "arayuzler": {}}}
    rep, events = mon.evaluate({"SW": {"hata": "zaman asimi"}}, {"SW": set()}, prev)
    assert rep["cihazlar"]["SW"]["durum"] == "ERISILEMIYOR"
    assert rep["alarmlar"][0]["tur"] == "ERISILEMIYOR" and events[0]["olay"] == "cihaz erisilemez oldu"


def test_izleme_varsayilan_hedefler(mon, devices):
    targets = {d["name"]: mon.default_target(d) for d in devices}
    assert targets["MRK-DAG1"] == "172.20.20.3:161" and targets["MRK-ERS-SAT"] == "172.16.90.11:161"
    assert len(set(targets.values())) == 13


# ------------------------------------------------------------------ Ansible envanteri
def test_ansible_envanteri(devices):
    out = subprocess.run([sys.executable, str(PROJECT / "extensions" / "ansible" / "inventory.py"), "--list"],
                         capture_output=True, text=True, check=True).stdout
    inv = json.loads(out)
    hosts = [h for g, v in inv.items() if g not in ("_meta", "all") for h in v["hosts"]]
    assert sorted(hosts) == sorted(d["name"] for d in devices)
    hv = inv["_meta"]["hostvars"]
    assert len(hv["MRK-ERS-BIS"]["access_port_list"]) == 5
    assert {s["vlan"]: s["priority"] for s in hv["MRK-DAG1"]["svi_list"]} == {10: 110, 20: 90, 30: 110, 40: 90, 50: 110, 60: 90, 90: 110}
    assert all(v["ansible_port"] == 22 for v in hv.values())


# ------------------------------------------------------------------ sertlestirme geri alma
def test_geri_alma_genel_komutlardan_once_arayuzden_cikar(devices):
    """Canli testte gorulen hata: arayuz kipindeyken 'no ip dhcp snooping' arayuz komutu sanilir ve reddedilir."""
    hard = load("extensions/security-hardening/harden.py", "hardmod")
    for d in devices:
        if d["role"] not in ("access", "branch_sw"):
            continue
        lines = hard.render(d, rollback=True)
        first_global = next(i for i, l in enumerate(lines) if l.startswith("no ip dhcp snooping"))
        assert lines[first_global - 1].strip() == "exit", d["name"]


def test_confcheck_no_switchport_port_security():
    import confcheck
    assert confcheck.satisfied("no switchport port-security maximum 2", ["switchport mode access"])
    assert not confcheck.satisfied("no switchport", ["switchport mode access"])
