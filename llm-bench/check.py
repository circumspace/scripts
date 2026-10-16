import json
import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(sys.argv[1])
results = {}


def check(name, fn):
    try:
        results[name] = bool(fn())
    except Exception:
        results[name] = False


def sources():
    return {p: p.read_text() for p in root.rglob("*.py")}


check("tests_pass", lambda: subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=root, capture_output=True, timeout=120).returncode == 0)
check("module_renamed", lambda: (root / "inventory/repository.py").exists() and not (root / "inventory/store.py").exists())
check("test_file_renamed", lambda: (root / "tests/test_repository.py").exists() and not (root / "tests/test_store.py").exists())
check("no_old_name", lambda: not any(re.search(r"\bStore\b|inventory\.store", s) for s in sources().values()))
check("tests_cover_total_value", lambda: any("total_value" in s for p, s in sources().items() if p.parts[-2] == "tests"))

PROBE = """
from inventory import Repository
from inventory.models import Item
r = Repository([Item("A1", "Anvil", 3, 120.0, ["heavy", "metal"]), Item("B2", "Bolt", 400, 0.15, ["metal"]), Item("C3", "Cable", 12, 4.5, ["electrical"])])
assert r.total_value() == 474.0, r.total_value()
assert r.total_value("METAL") == 420.0, r.total_value("METAL")
assert r.total_value("nope") == 0, r.total_value("nope")
print("ok")
"""
check("total_value_correct", lambda: subprocess.run([sys.executable, "-c", PROBE], cwd=root, capture_output=True, text=True, timeout=60).stdout.strip() == "ok")


def cli_value():
    data = [{"sku": "A1", "name": "Anvil", "quantity": 3, "unit_price": 120.0, "tags": ["metal"]},
            {"sku": "B2", "name": "Bolt", "quantity": 400, "unit_price": 0.15, "tags": []}]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f)
    total = subprocess.run([sys.executable, "-m", "inventory.cli", f.name, "value"], cwd=root, capture_output=True, text=True, timeout=60).stdout
    tagged = subprocess.run([sys.executable, "-m", "inventory.cli", f.name, "value", "--tag", "metal"], cwd=root, capture_output=True, text=True, timeout=60).stdout
    return "420.00" in total and "360.00" in tagged


check("cli_value", cli_value)
print(json.dumps({"score": sum(results.values()), "max": len(results), **results}))
