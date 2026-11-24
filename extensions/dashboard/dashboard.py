#!/usr/bin/env python3
"""Minimal web panosu: en son Ag Saglik Raporu (ve varsa sapma raporu) tarayicida.

    python extensions/dashboard/dashboard.py              # reports/dashboard.html uretir
    python extensions/dashboard/dashboard.py --serve      # http://localhost:5000 (her istekte en son rapor)
    python extensions/dashboard/dashboard.py --serve --refresh   # her istekte once validate.py calistirir

Yol haritasinda Flask onerilmisti; tek sayfalik salt-okunur pano icin Python standart kutuphanesi yeterli
oldugundan ek bagimlilik eklenmedi. Girdi yalnizca reports/*.json dosyalaridir (cekirdege dokunmaz).
"""
import argparse
import html
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
REPORTS = PROJECT / "reports"

CSS = """
:root{--bg:#f4f5f7;--card:#fff;--ink:#1b1f24;--muted:#5b6470;--line:#d9dde3;--ok:#1a7f4b;--okbg:#e3f4ea;
--bad:#b3261e;--badbg:#fbe6e4;--skip:#6b7280;--accent:#1f4e79}
@media(prefers-color-scheme:dark){:root{--bg:#14171b;--card:#1d2127;--ink:#e8eaed;--muted:#9aa3ad;--line:#333a44;
--ok:#5fd08f;--okbg:#173524;--bad:#ff8a80;--badbg:#3d1c19;--skip:#9aa3ad;--accent:#8fc1ee}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);margin-bottom:20px}.stats{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 18px;min-width:130px}
.stat b{display:block;font-size:26px;font-variant-numeric:tabular-nums}.stat span{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.dev{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--ok);border-radius:10px;padding:12px 14px}
.dev.bad{border-left-color:var(--bad)}.dev h2{font-size:16px;margin:0 0 2px}.badge{font-size:12px;font-weight:600;
padding:2px 8px;border-radius:99px;background:var(--okbg);color:var(--ok)}.bad .badge{background:var(--badbg);color:var(--bad)}
.counts{color:var(--muted);font-size:13px;margin:6px 0}details{margin-top:6px}summary{cursor:pointer;color:var(--accent);font-size:13px}
table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:6px}td{padding:3px 4px;border-top:1px solid var(--line);
vertical-align:top;word-break:break-word}.HATA td:first-child{color:var(--bad);font-weight:600}.ATLANDI td{color:var(--skip)}
h3{margin:28px 0 10px;font-size:17px}.drift{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
code{font-family:ui-monospace,Consolas,monospace;font-size:12.5px}
"""


def latest(prefix):
    files = sorted(REPORTS.glob(f"{prefix}_*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def render():
    health, drift = latest("health"), latest("drift")
    e = html.escape
    if health is None:
        return "<p>reports/ altinda health_*.json yok. Once core/scripts/validate.py calistir.</p>"
    o = health["ozet"]
    parts = [f"<h1>Ağ Sağlık Raporu — Anadolu Makina A.Ş.</h1>",
             f"<div class='sub'>Son ölçüm: {e(health['zaman'].replace('T', ' '))}"
             f"{' · kısmi kapsam (' + str(len(health['kapsam'])) + ' cihaz)' if health.get('kismi') else ''}</div>",
             "<div class='stats'>",
             f"<div class='stat'><b>{o['saglikli']}/{o['cihaz']}</b><span>sağlıklı cihaz</span></div>",
             f"<div class='stat'><b>{o['OK']}</b><span>geçen kontrol</span></div>",
             f"<div class='stat'><b>{o['HATA']}</b><span>hatalı kontrol</span></div>",
             f"<div class='stat'><b>{o['ATLANDI']}</b><span>atlanan (kapsam dışı)</span></div>", "</div><div class='grid'>"]
    by_dev = {}
    for c in health["kontroller"]:
        by_dev.setdefault(c["cihaz"], []).append(c)
    for name, checks in by_dev.items():
        n = {s: sum(c["durum"] == s for c in checks) for s in ("OK", "HATA", "ATLANDI")}
        bad = n["HATA"] > 0
        rows = "".join(f"<tr class='{c['durum']}'><td>{e(c['kontrol'])}</td><td>{e(str(c['beklenen']))}</td>"
                       f"<td>{e(str(c['gercek']))}</td></tr>"
                       for c in sorted(checks, key=lambda c: ("HATA", "OK", "ATLANDI").index(c["durum"])))
        parts.append(f"<div class='dev{' bad' if bad else ''}'><h2>{e(name)}</h2>"
                     f"<span class='badge'>{'SORUNLU' if bad else 'SAĞLIKLI'}</span>"
                     f"<div class='counts'>{n['OK']} geçti · {n['HATA']} hata · {n['ATLANDI']} atlandı</div>"
                     f"<details{' open' if bad else ''}><summary>Kontroller</summary>"
                     f"<table><tr><td><b>Kontrol</b></td><td><b>Beklenen</b></td><td><b>Gerçek</b></td></tr>{rows}</table>"
                     f"</details></div>")
    parts.append("</div>")
    parts.append(monitor_section())
    if drift:
        parts.append("<h3>Config sapması (şablon ↔ canlı)</h3><div class='drift'>")
        clean = [r["cihaz"] for r in drift["sonuc"] if not r["eksik"] and not r["fazla"]]
        parts.append(f"<div>{len(clean)}/{len(drift['sonuc'])} cihaz şablonla uyumlu.</div>")
        for r in drift["sonuc"]:
            if r["eksik"] or r["fazla"]:
                items = "".join(f"<tr class='HATA'><td>EKSİK</td><td><code>{e(s)}</code></td><td><code>{e(l)}</code></td></tr>" for s, l in r["eksik"])
                items += "".join(f"<tr class='HATA'><td>FAZLA</td><td><code>{e(s)}</code></td><td><code>{e(l)}</code></td></tr>" for s, l in r["fazla"])
                parts.append(f"<details open><summary>{e(r['cihaz'])}</summary><table>{items}</table></details>")
        parts.append("</div>")
    return "\n".join(parts)


def monitor_section():
    """extensions/monitoring ciktisi (SNMP yoklamasi) varsa: cihaz tablosu + alarmlar + son olaylar."""
    f = REPORTS / "monitor_latest.json"
    if not f.exists():
        return ""
    e = html.escape
    mon = json.loads(f.read_text(encoding="utf-8"))
    rows = []
    for name, d in mon["cihazlar"].items():
        if d["durum"] == "ERISILEMIYOR":
            rows.append(f"<tr class='HATA'><td>{e(name)}</td><td>ERİŞİLEMİYOR</td><td colspan='4'>{e(d['hata'])}</td></tr>")
            continue
        up = f"{d['uptime_sn'] // 3600} sa {d['uptime_sn'] % 3600 // 60} dk"
        cpu = "-" if d["cpu"] is None else f"%{d['cpu']}"
        down = ", ".join(d["kritik_down"]) or "-"
        rows.append(f"<tr class='{'HATA' if d['durum'] != 'OK' else 'OK'}'><td>{e(name)}</td><td>{e(d['durum'])}</td>"
                    f"<td>{e(up)}</td><td>{cpu}</td><td>{d['up']}/{d['toplam']}</td><td>{e(down)}</td></tr>")
    out = [f"<h3>Canlı izleme (SNMP) <span class='sub'>· {e(mon['zaman'].replace('T', ' '))}</span></h3><div class='drift'>",
           f"<div>{sum(1 for d in mon['cihazlar'].values() if d['durum'] == 'OK')}/{len(mon['cihazlar'])} cihaz OK · "
           f"{len(mon['alarmlar'])} alarm</div>",
           "<table><tr><td><b>Cihaz</b></td><td><b>Durum</b></td><td><b>Çalışma süresi</b></td><td><b>CPU</b></td>"
           "<td><b>Arayüz (up/toplam)</b></td><td><b>Kapalı kritik link</b></td></tr>" + "".join(rows) + "</table>"]
    ev = REPORTS / "monitor_events.jsonl"
    if ev.exists():
        last = [json.loads(l) for l in ev.read_text(encoding="utf-8").splitlines()[-8:] if l.strip()]
        if last:
            out.append("<details open><summary>Son olaylar</summary><table>" + "".join(
                f"<tr><td>{e(x['zaman'].replace('T', ' '))}</td><td>{e(x['cihaz'])}</td><td>{e(x['olay'])}</td></tr>" for x in reversed(last)) + "</table></details>")
    out.append("</div>")
    return chr(10).join(out)


def page():
    return (f"<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>Ağ Sağlık Raporu</title>"
            f"<style>{CSS}</style></head><body><main>{render()}</main></body></html>")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--refresh", action="store_true", help="--serve ile: her istekte validate.py calistir")
    args = ap.parse_args()
    if not args.serve:
        out = REPORTS / "dashboard.html"
        out.write_text(page(), encoding="utf-8")
        print(f"Yazildi: {out}")
        return

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            if args.refresh:
                subprocess.run([sys.executable, str(PROJECT / "core" / "scripts" / "validate.py")],
                               cwd=PROJECT, capture_output=True)
            body = page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    print(f"Pano: http://localhost:{args.port}  (Ctrl+C ile kapat)")
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
