#!/usr/bin/env python3
"""Asil GNS3 projesinin (portable export) icindeki IOS disklerinden kayitli startup-config'leri cikarir.

Cihazlari calistirmaz, parola gerektirmez: her dugumun qcow2 katmani taban imaja baglanip ham diske cevrilir,
NVRAM'daki config diskten okunur (IOSv: duz metin, IOSvL2: unix compress ile sikistirilmis).
Cikti: lab/gns3_export/saved/<isim>.cfg     Onkosul: zip lab/gns3_export/ altina acilmis olmali.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import unlzw3

LAB = Path(__file__).resolve().parent
EXP = LAB / "gns3_export"
QIMG = r"C:\Program Files\qemu\qemu-img.exe"
OUT = EXP / "saved"
TMP = EXP / "tmp"
PLAIN = re.compile(rb"\n!\n(?:! Last configuration[^\n]*\n(?:![^\n]*\n)*)?version 1\d\.\d\n")
PACKED = re.compile(rb"\xab\xcd\x00\x02.{32}\x1f\x9d", re.S)


def configs(data):
    found = []
    for m in PLAIN.finditer(data):
        end = data.find(b"\nend\n", m.start())
        if 0 < end - m.start() < 200000:
            found.append(data[m.start():end + 5].lstrip(b"\n"))
    for m in PACKED.finditer(data):
        clen = int.from_bytes(data[m.start() + 16:m.start() + 20], "big")
        try:
            text = unlzw3.unlzw(data[m.end() - 2:m.end() - 2 + clen])
        except Exception as e:
            print("   acilamadi:", e)
            continue
        if b"hostname" in text:
            found.append(text[:text.rfind(b"\nend") + 5].lstrip(b"\n"))
    return found


def main():
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    proj = json.loads((EXP / "project.gns3").read_text(encoding="utf-8"))
    for node in proj["topology"]["nodes"]:
        if node["node_type"] != "qemu":
            continue
        name, nid = node["name"], node["node_id"]
        img = node["properties"].get("hda_disk_image", "")
        base = LAB / "images" / ("iosvl2.qcow2" if "l2" in img.lower() else "iosv.qcow2")
        work, raw = TMP / f"{name}.qcow2", TMP / f"{name}.raw"
        shutil.copy(EXP / "project-files" / "qemu" / nid / "hda_disk.qcow2", work)
        subprocess.run([QIMG, "rebase", "-u", "-f", "qcow2", "-F", "qcow2", "-b", str(base), str(work)], check=True)
        subprocess.run([QIMG, "convert", "-O", "raw", str(work), str(raw)], check=True)
        found = configs(raw.read_bytes())
        raw.unlink()
        work.unlink()
        print(f"{name:14} config adayi={len(found)} boyut={[len(f) for f in found]}")
        if found:
            (OUT / f"{name}.cfg").write_bytes(max(found, key=len))


if __name__ == "__main__":
    main()
