"""pytest ortak ayarlari.

    pytest extensions/tests                      # yalniz cevrimdisi testler (cihaz gerekmez)
    pytest extensions/tests --live               # + canli ag testleri (validate.py'yi calistirir)
    pytest extensions/tests --live --only MRK-DAG1 MRK-DAG2 --partial
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT / "core" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="canli cihazlara baglanan testleri de calistir")
    parser.addoption("--only", nargs="*", default=None, help="canli testlerde yalniz bu cihazlar")
    parser.addoption("--partial", action="store_true", help="secilmeyen cihazlara bakan beklentileri atla")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="canli test: --live ile calistir")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calisan cihazlara baglanir")


@pytest.fixture(scope="session")
def inventory():
    return yaml.safe_load((PROJECT / "core" / "inventory" / "devices.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def devices():
    import deploy
    return deploy.load_inventory()


@pytest.fixture(scope="session")
def health(request):
    """validate.py'yi bir kez calistirir, urettigi JSON raporunu dondurur."""
    cmd = [sys.executable, str(SCRIPTS / "validate.py")]
    only = request.config.getoption("--only")
    if only:
        cmd += ["--only", *only]
    if request.config.getoption("--partial"):
        cmd.append("--partial")
    before = set((PROJECT / "reports").glob("health_*.json"))
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=PROJECT)
    new = sorted(set((PROJECT / "reports").glob("health_*.json")) - before)
    assert new, f"validate.py rapor uretmedi:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(new[-1].read_text(encoding="utf-8"))
