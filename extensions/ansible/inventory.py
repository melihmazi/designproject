#!/usr/bin/env python3
"""Dinamik Ansible envanteri: cekirdegin devices.yaml dosyasini okur (tek dogru kaynak ayni kalir).

    ansible-inventory --list            (ansible.cfg bu betigi envanter olarak kullanir)

Gruplar: role gore (core, dag, access, branch_sw, snr, iss, fab). Her cihazin envanter alanlari hostvars olur;
playbook yalin kalsin diye birkac turetilmis alan eklenir (acik port listesi, SVI oncelikleri).
Adres: varsayilan olarak yonetim IP (Loopback0 / yonetim SVI) port 22. Baska bir yol icin
ANSIBLE_NET_MAP=dosya.yaml  ({cihaz: "adres:port"}); laboratuvar bant disi SSH portlarini boyle verir.
"""
import json
import os
import re
import sys
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parents[2]


def expand(rng):
    m = re.match(r"(\D+)(\d+)/(\d+)(?:\s*-\s*(\d+))?$", rng.strip())
    return [f"{m.group(1)}{m.group(2)}/{n}" for n in range(int(m.group(3)), int(m.group(4) or m.group(3)) + 1)]


def main():
    data = yaml.safe_load((PROJECT / "core" / "inventory" / "devices.yaml").read_text(encoding="utf-8"))
    net = data["network"]
    override = {}
    if os.getenv("ANSIBLE_NET_MAP"):
        override = yaml.safe_load(Path(os.environ["ANSIBLE_NET_MAP"]).read_text(encoding="utf-8"))
    inv = {"_meta": {"hostvars": {}}, "all": {"vars": {"net": net}}}
    for d in data["devices"]:
        name = d["name"]
        hv = dict(d)
        target = override.get(name) or f"{d.get('router_id') or d.get('mgmt_ip') or net['wan']['iss_to_snr']}:22"
        hv["ansible_host"], port = target.rsplit(":", 1)
        hv["ansible_port"] = int(port)
        if d["role"] == "access":
            hv["access_port_list"] = [{"name": p, "vlan": a["vlan"], "description": a["description"]}
                                      for a in d["access_ports"] for p in expand(a["range"])]
        if d["role"] == "dag":
            hv["svi_list"] = [dict(s, priority=110 if s["active"] == name else 90) for s in net["svis"]]
        if d["role"] == "core":
            hv["l3_ports"] = ([{"name": f"Port-channel{po['id']}", "ip": po["ip"]} for po in d["port_channels"]]
                              + [{"name": p["name"], "ip": p["ip"]} for p in d["routed_ports"]])
        if d["role"] == "snr":
            hv["l3_ports"] = [{"name": l["name"], "ip": l["ip"]} for l in d["core_links"]]
        inv["_meta"]["hostvars"][name] = hv
        inv.setdefault(d["role"], {"hosts": []})["hosts"].append(name)
    print(json.dumps(inv, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--host":
        print("{}")
    else:
        main()
