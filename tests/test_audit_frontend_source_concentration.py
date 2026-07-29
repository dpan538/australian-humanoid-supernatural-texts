import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_audit():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "audit_frontend_source_concentration.py"
    spec = importlib.util.spec_from_file_location("audit_frontend_source_concentration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ayr_variants_normalize_and_gap_concentration_warns():
    audit = load_audit()
    assert audit.source_family("Australian Yowie Research / AYR Yowie Reports Map") == "AYR_FAMILY"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rows = tmp_path / "map.csv"
        fields = ["record_id", "source_name", "year"]
        with rows.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for i in range(6):
                writer.writerow({"record_id": i, "source_name": "Australian Yowie Research state report indexes", "year": "1940"})
            for i in range(4):
                writer.writerow({"record_id": i + 10, "source_name": "State Library", "year": "1960"})
        output = audit.audit(rows, tmp_path / "out.csv", tmp_path / "report.md")
        ayr = [row for row in output if row["source_family"] == "AYR_FAMILY"][0]
        assert ayr["rows_1926_1976"] == 6
        text = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "AYR > 50 warning: `true`" in text
