#!/usr/bin/env python3
"""GNS3 olmadan mini laboratuvar: IOSv / IOSvL2 imajlarini dogrudan QEMU ile calistirir.

Konsol portlari ve kablolama yol haritasindaki (Bolum 3.3) ile aynidir; konsol 127.0.0.1:<port>.
Her dugum taban imajin ustunde kendi qcow2 katmanini kullanir (taban imaj degismez).

    python lab.py start MRK-DAG1 MRK-ERS-SAT     # baslat (katman yoksa sifirdan olusturur)
    python lab.py stop [ISIM ...]                # durdur (isim yoksa hepsi)
    python lab.py reset ISIM ...                 # durdur + katmani sil (fabrika ayari)
    python lab.py status
"""
import json
import os
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
QEMU = Path(r"C:\Program Files\qemu\qemu-system-x86_64.exe")
QIMG = Path(r"C:\Program Files\qemu\qemu-img.exe")
STATE = LAB / "state.json"

# isim: (tip, konsol portu)   tip: l2 = IOSvL2 (16 port, 768 MB), l3 = IOSv (4 port, 512 MB)
NODES = {
    "MRK-DAG1": ("l2", 5000), "MRK-DAG2": ("l2", 5002), "MRK-CORE1": ("l2", 5004), "MRK-CORE2": ("l2", 5006),
    "MRK-ERS-SAT": ("l2", 5008), "MRK-ERS-PER": ("l2", 5010), "MRK-ERS-YNT": ("l2", 5012),
    "MRK-ERS-SRV": ("l2", 5014), "MRK-ERS-BIS": ("l2", 5016), "FAB-ERS-1": ("l2", 5018),
    "SNR-RTR": ("l3", 5020), "ISS-RTR": ("l3", 5022), "FAB-RTR": ("l3", 5024),
}
KIND = {"l2": dict(image="iosvl2.qcow2", ram=768, nics=16), "l3": dict(image="iosv.qcow2", ram=512, nics=4)}

# IOS-IOS linkleri: yol haritasi L01-L13, L15-L24  (A, portA, B, portB)
LINKS = [
    ("MRK-CORE1", "0/0", "MRK-CORE2", "0/0"), ("MRK-CORE1", "0/1", "MRK-CORE2", "0/1"),
    ("MRK-CORE1", "0/2", "MRK-DAG1", "0/0"), ("MRK-CORE1", "0/3", "MRK-DAG1", "0/1"),
    ("MRK-CORE2", "0/2", "MRK-DAG2", "0/0"), ("MRK-CORE2", "0/3", "MRK-DAG2", "0/1"),
    ("MRK-DAG1", "0/2", "MRK-DAG2", "0/2"), ("MRK-DAG1", "0/3", "MRK-DAG2", "0/3"),
    ("MRK-CORE1", "1/0", "SNR-RTR", "0/0"), ("MRK-CORE2", "1/0", "SNR-RTR", "0/1"),
    ("SNR-RTR", "0/2", "ISS-RTR", "0/0"), ("ISS-RTR", "0/1", "FAB-RTR", "0/0"),
    ("FAB-RTR", "0/1", "FAB-ERS-1", "0/0"),
    ("MRK-DAG1", "1/0", "MRK-ERS-SAT", "0/0"), ("MRK-DAG2", "1/2", "MRK-ERS-SAT", "0/1"),
    ("MRK-DAG1", "1/1", "MRK-ERS-BIS", "0/0"), ("MRK-DAG2", "1/3", "MRK-ERS-BIS", "0/1"),
    ("MRK-DAG1", "1/2", "MRK-ERS-SRV", "0/0"), ("MRK-DAG2", "2/0", "MRK-ERS-SRV", "0/1"),
    ("MRK-DAG2", "1/0", "MRK-ERS-PER", "0/0"), ("MRK-DAG1", "1/3", "MRK-ERS-PER", "0/1"),
    ("MRK-DAG2", "1/1", "MRK-ERS-YNT", "0/0"), ("MRK-DAG1", "2/0", "MRK-ERS-YNT", "0/1"),
]


# Uc cihazlar (asil projede VPCS): isim -> (switch, port, VLAN, statik IP ya da None = DHCP)
# Port numaralari project.gns3'teki adaptor numaralariyla aynidir. Bu uclari lab/hosts.py canlandirir.
ENDPOINTS = {
    "SAT-PC1": ("MRK-ERS-SAT", "0/2", 10, "172.16.10.11"), "SAT-PC2": ("MRK-ERS-SAT", "0/3", 10, None),
    "PER-PC1": ("MRK-ERS-PER", "0/2", 20, "172.16.20.11"), "PER-PC2": ("MRK-ERS-PER", "0/3", 20, None),
    "BIS-PC1": ("MRK-ERS-BIS", "0/2", 30, "172.16.30.11"), "BIS-PC2": ("MRK-ERS-BIS", "0/3", 30, None),
    "BIS-YAZICI1": ("MRK-ERS-BIS", "1/0", 30, "172.16.30.5"), "KAP-1": ("MRK-ERS-BIS", "1/1", 90, "172.16.90.16"),
    "MSF-DZ1": ("MRK-ERS-BIS", "1/2", 60, None),
    "YNT-PC1": ("MRK-ERS-YNT", "0/2", 40, None), "YNT-TEL1": ("MRK-ERS-YNT", "0/3", 40, None),
    "SNC-DHCP": ("MRK-ERS-SRV", "0/2", 50, "172.16.50.10"), "SNC-DNS": ("MRK-ERS-SRV", "0/3", 50, "172.16.50.11"),
    "SNC-WEB": ("MRK-ERS-SRV", "1/0", 50, "172.16.50.12"), "SNC-POSTA": ("MRK-ERS-SRV", "1/1", 50, "172.16.50.13"),
    "SNC-DOSYA": ("MRK-ERS-SRV", "1/2", 50, "172.16.50.14"),
    "FAB-PC1": ("FAB-ERS-1", "0/1", 110, None),
}
MGMT_NIC = {"l2": 15, "l3": 3}        # bant disi yonetim portu (Gi3/3, Gi0/3): QEMU user-net, 10.0.2.15


def endpoint_ports(name):
    """uc cihaz -> (ucun dinledigi UDP portu, switch tarafinin UDP portu)"""
    i = list(ENDPOINTS).index(name)
    return 21001 + 2 * i, 21000 + 2 * i


def mgmt_ports(name):
    """dugum -> (SSH icin yerel TCP portu, SNMP icin yerel UDP portu)"""
    i = list(NODES).index(name)
    return 2200 + i, 16100 + i


def nic_index(port):
    slot, num = (int(x) for x in port.split("/"))
    return slot * 4 + num


def wiring(name):
    """nic indeksi -> (yerel UDP portu, karsi UDP portu)"""
    out = {}
    for i, (a, pa, b, pb) in enumerate(LINKS):
        ua, ub = 20000 + 2 * i, 20001 + 2 * i
        if a == name:
            out[nic_index(pa)] = (ua, ub)
        if b == name:
            out[nic_index(pb)] = (ub, ua)
    for ep, (sw, port, _vlan, _ip) in ENDPOINTS.items():
        if sw == name:
            host_udp, sw_udp = endpoint_ports(ep)
            out[nic_index(port)] = (sw_udp, host_udp)
    return out


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def start(name):
    kind, port = NODES[name]
    k = KIND[kind]
    state = load_state()
    if name in state and alive(state[name]):
        print(f"{name}: zaten calisiyor (pid {state[name]})")
        return
    disk = LAB / "disks" / f"{name}.qcow2"
    if not disk.exists():
        subprocess.run([str(QIMG), "create", "-q", "-f", "qcow2", "-F", "qcow2",
                        "-b", str(LAB / "images" / k["image"]), str(disk)], check=True)
    idx = list(NODES).index(name)
    args = [str(QEMU), "-name", name, "-m", str(k["ram"]), "-smp", "1", "-accel", "tcg,thread=single",
            "-display", "none", "-serial", f"telnet:127.0.0.1:{port},server,nowait",
            "-drive", f"file={disk},if=virtio,format=qcow2"]
    wires = wiring(name)
    for n in range(k["nics"]):
        mac = f"0c:00:{idx:02x}:00:{n:02x}:00"
        if n in wires:
            local, remote = wires[n]
            args += ["-netdev", f"socket,id=n{n},udp=127.0.0.1:{remote},localaddr=127.0.0.1:{local}",
                     "-device", f"e1000,netdev=n{n},mac={mac}"]
            if os.getenv("LAB_CAPTURE"):       # kablolu portlarin trafigini pcap olarak kaydet (Faz 6-B)
                cap = LAB / "captures"
                cap.mkdir(exist_ok=True)
                pcap = (cap / f"{name}_Gi{n // 4}-{n % 4}.pcap").as_posix()
                args += ["-object", f"filter-dump,id=d{n},netdev=n{n},file={pcap}"]
        elif n == MGMT_NIC[kind]:
            ssh, snmp = mgmt_ports(name)
            args += ["-netdev", f"user,id=m0,hostfwd=tcp:127.0.0.1:{ssh}-10.0.2.15:22,"
                                f"hostfwd=udp:127.0.0.1:{snmp}-10.0.2.15:161",
                     "-device", f"e1000,netdev=m0,mac={mac}"]
        else:
            args += ["-device", f"e1000,mac={mac}"]
    log = open(LAB / "logs" / f"{name}.log", "w")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    p = subprocess.Popen(args, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags)
    state[name] = p.pid
    STATE.write_text(json.dumps(state, indent=1))
    print(f"{name}: basladi pid {p.pid}, konsol 127.0.0.1:{port}, {k['ram']} MB")


def stop(name):
    state = load_state()
    pid = state.pop(name, None)
    if pid and alive(pid):
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        print(f"{name}: durduruldu")
    STATE.write_text(json.dumps(state, indent=1))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, names = sys.argv[1], sys.argv[2:]
    unknown = [n for n in names if n not in NODES]
    if unknown:
        sys.exit(f"bilinmeyen dugum: {unknown}")
    if cmd == "start":
        for n in names:
            start(n)
    elif cmd == "stop":
        for n in names or list(load_state()):
            stop(n)
    elif cmd == "reset":
        for n in names:
            stop(n)
            (LAB / "disks" / f"{n}.qcow2").unlink(missing_ok=True)
            print(f"{n}: katman silindi")
    elif cmd == "status":
        for n, pid in load_state().items():
            print(f"{n:12} pid {pid:6} {'CALISIYOR' if alive(pid) else 'olu'}  konsol :{NODES[n][1]}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
