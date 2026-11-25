#!/usr/bin/env python3
"""Git tabanli config gecmisi (Modul 4): maskelenmis yedekleri yerel bir git deposuna commit'ler.

    python core/scripts/backup.py --sanitize
    python extensions/config-history/commit_backups.py
    git -C extensions/config-history/repo log -p -- MRK-DAG1.cfg     # bir cihazin degisim gecmisi

Yalnizca backups/<damga>/sanitized/ altindaki dosyalar alinir (parola ozetleri maskeli). Depo yereldir, hicbir
yere push edilmez. Daha once islenmis yedekler atlanir; her yedek klasoru ayri bir commit olur.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
BACKUPS = PROJECT / "backups"
REPO = HERE / "repo"
DONE = REPO / ".islenen_yedekler"


def git(*args, check=True):
    p = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode:
        sys.exit(f"git {' '.join(args)} basarisiz:\n{p.stderr}")
    return p.stdout.strip()


def main():
    if not (REPO / ".git").exists():
        REPO.mkdir(parents=True, exist_ok=True)
        git("init", "-q")
        git("config", "user.name", "Ag Otomasyonu")
        git("config", "user.email", "otomasyon@anadolumakina.local")
    done = set(DONE.read_text(encoding="utf-8").split()) if DONE.exists() else set()
    new = 0
    for d in sorted(p for p in BACKUPS.iterdir() if (p / "sanitized").is_dir()) if BACKUPS.exists() else []:
        if d.name in done:
            continue
        files = sorted((d / "sanitized").glob("*.cfg"))
        for f in files:
            shutil.copy2(f, REPO / f.name)
        done.add(d.name)
        DONE.write_text("\n".join(sorted(done)) + "\n", encoding="utf-8")
        git("add", "-A")
        changed = [l[3:] for l in git("status", "--porcelain").splitlines() if l[3:].endswith(".cfg")]
        date = d.name[:10] + "T" + d.name[11:13] + ":" + d.name[13:15] + ":" + (d.name[15:17] or "00")
        msg = f"yedek {d.name}: {len(changed)} cihazda degisiklik" + (" (" + ", ".join(c[:-4] for c in changed) + ")" if changed else "")
        subprocess.run(["git", "-C", str(REPO), "commit", "-q", "-m", msg, "--date", date], capture_output=True,
                       env={**__import__("os").environ, "GIT_COMMITTER_DATE": date})
        print(msg)
        new += 1
    print(f"{new} yeni yedek islendi. Gecmis: git -C {REPO} log --oneline")


if __name__ == "__main__":
    main()
