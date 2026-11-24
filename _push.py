"""Kucuk yardimci: python _push.py CIHAZ "satir1" "satir2" ...  (deploy.push ile konsoldan config basar)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "network-automation-project" / "core" / "scripts"))
import deploy
deploy.load_dotenv()
dev = next(d for d in deploy.load_inventory() if d["name"] == sys.argv[1])
print(sys.argv[1], sys.argv[2:], "hatalar:", deploy.push(dev, sys.argv[2:])[1])
