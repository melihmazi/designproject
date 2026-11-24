#!/usr/bin/env python3
"""13 cihazin Faz 1-3 config'ini gercek IOSv/IOSvL2 uzerinde TEK TEK dener (RAM az oldugu icin sirayla).

Her cihaz icin: fabrika ayarinda baslat -> bootstrap -> deploy 1 2 3 -> show run al ->
deploy 1 2 3 (ikinci kez) -> show run al -> karsilastir -> durdur.
Komsular kapali oldugu icin bu test SOZDIZIMI + IDEMPOTENTLIK kanitidir, protokol komsulugu degil.

    python validate_all.py [ISIM ...]      # isim verilmezse 13 cihazin hepsi
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
PROJ = LAB.parent / "network-automation-project"
PY = str(PROJ / ".venv" / "Scripts" / "python.exe")
sys.path.insert(0, str(LAB))
from lab import NODES  # noqa: E402

NOISE = re.compile(r"Last configuration|NVRAM config|Current configuration|^!|ntp clock-period|^\*|^\s*$|Building configuration|show running-config")
ENVV = {**os.environ, "NET_CONSOLE_HOST": "127.0.0.1", "PYTHONIOENCODING": "utf-8"}


def run(args, cwd, timeout=1800):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=ENVV,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout + p.stderr)


def show_run(name):
    for _ in range(4):
        time.sleep(6)
        _, out = run([PY, "console.py", "show", name, "show running-config"], LAB, 300)
        lines = [l.rstrip() for l in out.splitlines() if not NOISE.search(l)]
        if "end" in lines:
            return lines[: lines.index("end") + 1]
    return lines


def deploy(name):
    code, out = run([PY, "core/scripts/deploy.py", "--phase", "1", "2", "3", "--only", name], PROJ)
    problems = [l for l in out.splitlines() if "HATA" in l or "UYARI" in l or l.startswith("    ") or "%" in l]
    return code, problems, out


def one(name):
    t0 = time.monotonic()
    res = {"cihaz": name}
    run([PY, "lab.py", "reset", name], LAB)
    run([PY, "lab.py", "start", name], LAB)
    try:
        code, out = run([PY, "console.py", "bootstrap", name], LAB, 2400)
        res["bootstrap"] = out.strip().splitlines()[-1] if out.strip() else f"kod {code}"
        if code != 0:
            res["sonuc"] = "BOOTSTRAP BASARISIZ"
            return res
        c1, p1, o1 = deploy(name)
        run1 = show_run(name)
        c2, p2, o2 = deploy(name)
        run2 = show_run(name)
        (LAB / "logs" / f"{name}_deploy1.log").write_text(o1, encoding="utf-8")
        (LAB / "logs" / f"{name}_deploy2.log").write_text(o2, encoding="utf-8")
        (LAB / "logs" / f"{name}_running.cfg").write_text("\n".join(run2) + "\n", encoding="utf-8")
        res.update(ilk_cikis=c1, ilk_sorun=p1, ikinci_cikis=c2, ikinci_sorun=p2,
                   run_satir=len(run2), idempotent=(run1 == run2 and len(run1) > 30))
        if not res["idempotent"]:
            res["fark"] = [l for l in run2 if l not in run1][:10] + ["---"] + [l for l in run1 if l not in run2][:10]
        res["sonuc"] = "TAMAM" if c1 == 0 and c2 == 0 and res["idempotent"] else "SORUN"
    except Exception as exc:
        res["sonuc"] = f"HATA: {type(exc).__name__}: {exc}"
    finally:
        run([PY, "lab.py", "stop", name], LAB)
        res["sure_sn"] = round(time.monotonic() - t0)
    return res


def main():
    names = sys.argv[1:] or list(NODES)
    out_file = LAB / "logs" / "validate_all.json"
    results = json.loads(out_file.read_text(encoding="utf-8")) if out_file.exists() else {}
    for n in names:
        r = one(n)
        results[n] = r
        out_file.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
