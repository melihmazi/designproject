#!/usr/bin/env python3
"""Konsol portlarini GNS3'ten okuyup core/inventory/consoles.yaml uretir.

Dugum silinip yeniden eklenirse konsol portu degisir; elle duzeltmek yerine bunu calistir.

    python core/scripts/gen_inventory.py --api                         # calisan GNS3 sunucusundan (REST v2)
    python core/scripts/gen_inventory.py --file yol/project.gns3       # proje dosyasindan
    python core/scripts/gen_inventory.py --file yol/X.gns3project.zip  # disa aktarilmis arsivden
"""
import argparse
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import yaml

CORE = Path(__file__).resolve().parents[1]
INVENTORY = CORE / "inventory" / "devices.yaml"
CONSOLES = CORE / "inventory" / "consoles.yaml"


def nodes_from_file(path):
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            data = json.loads(z.read("project.gns3").decode("utf-8"))
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
    return data["topology"]["nodes"]


def nodes_from_api(base, project_name):
    def get(url):
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    projects = get(f"{base}/v2/projects")
    proj = next((p for p in projects if p["name"] == project_name), None)
    if proj is None:
        sys.exit(f"Proje bulunamadi: {project_name}. Mevcut: {[p['name'] for p in projects]}")
    return get(f"{base}/v2/projects/{proj['project_id']}/nodes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--api", action="store_true", help="GNS3 REST API'sinden oku")
    src.add_argument("--file", help=".gns3 dosyasi veya .gns3project arsivi")
    ap.add_argument("--server", default="http://192.168.130.128:80", help="GNS3 sunucu adresi (--api icin)")
    ap.add_argument("--project", default="DesignProject")
    args = ap.parse_args()

    nodes = nodes_from_api(args.server, args.project) if args.api else nodes_from_file(args.file)
    by_name = {n["name"]: n.get("console") for n in nodes}

    inv = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    wanted = [d["name"] for d in inv["devices"]]
    missing = [n for n in wanted if by_name.get(n) is None]
    consoles = {n: by_name[n] for n in wanted if by_name.get(n) is not None}
    endpoints = {n: p for n, p in sorted(by_name.items()) if n not in wanted and p is not None}

    out = {"consoles": consoles, "endpoints": endpoints}
    header = "# gen_inventory.py tarafindan uretildi - elle duzenleme, yeniden uret.\n"
    CONSOLES.write_text(header + yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"{CONSOLES} yazildi: {len(consoles)}/{len(wanted)} IOS cihazi, {len(endpoints)} uc dugum")
    for name in wanted:
        print(f"  {name:12} {by_name.get(name)}")
    if missing:
        sys.exit(f"EKSIK (GNS3'te bu isimde dugum yok): {', '.join(missing)}")


if __name__ == "__main__":
    main()
