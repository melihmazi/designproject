"""Kucuk yardimci: python _show.py CIHAZ "komut1" "komut2" ...  (enable modunda calistirir, ciktiyi yazar)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "network-automation-project" / "core" / "scripts"))
import deploy
from validate import collect
deploy.load_dotenv()
dev = next(d for d in deploy.load_inventory() if d["name"] == sys.argv[1])
out = collect(dev, sys.argv[2:])
for c in sys.argv[2:]:
    print(f"===== {sys.argv[1]}# {c}")
    print(out[c])
