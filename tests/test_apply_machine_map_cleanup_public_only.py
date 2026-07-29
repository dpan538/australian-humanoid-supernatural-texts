import csv
import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_cleanup():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "apply_machine_map_cleanup.py"
    spec = importlib.util.spec_from_file_location("apply_machine_map_cleanup", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_refuses_old_red_bucket():
    cleanup = load_cleanup()
    eligible, reason = cleanup.auto_apply_eligible(
        {"machine_bucket": "RED_DEMOTE_ELIGIBLE", "machine_confidence": "0.99", "hard_fail_reasons": "invalid_location_role"},
        0.95,
    )
    assert eligible is False
    assert reason == "refuse_legacy_red_bucket_requires_public_prefixed_rescore"


def test_refuses_nonpublic_ignore():
    cleanup = load_cleanup()
    eligible, reason = cleanup.auto_apply_eligible(
        {"machine_bucket": "NONPUBLIC_IGNORE", "machine_confidence": "0.99", "hard_fail_reasons": ""},
        0.95,
    )
    assert eligible is False
    assert reason == "refuse_nonpublic_or_unknown_population"


def test_applies_only_public_red_when_resolved_execute_and_backup():
    cleanup = load_cleanup()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "test.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE narrative_locations (narrative_location_id TEXT, review_status TEXT)")
        conn.execute("INSERT INTO narrative_locations VALUES ('nl1', 'reviewed')")
        conn.commit()
        conn.close()
        scores = tmp_path / "scores.csv"
        fields = ["record_id", "narrative_unit_id", "legacy_map_id", "machine_bucket", "machine_confidence", "hard_fail_reasons", "ethics_flags_json"]
        with scores.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "record_id": "r1",
                    "narrative_unit_id": "n1",
                    "legacy_map_id": "nl1",
                    "machine_bucket": "RED_PUBLIC_DEMOTE_ELIGIBLE",
                    "machine_confidence": "0.98",
                    "hard_fail_reasons": "invalid_location_role:publication_location",
                    "ethics_flags_json": "{}",
                }
            )
        reconciliation = tmp_path / "canonical_count_reconciliation.md"
        reconciliation.write_text("- count_conflict_resolved: `true`\n", encoding="utf-8")
        (tmp_path / "frontend_map_manifest.json").write_text(json.dumps({"frontend_map_count": 1}), encoding="utf-8")
        summary = cleanup.run_cleanup(
            db_path,
            scores,
            reconciliation,
            "run1",
            tmp_path / "applied.csv",
            tmp_path / "report.md",
            True,
            tmp_path / "backups",
            0.95,
        )
        assert summary["blocked"] is False
        conn = sqlite3.connect(db_path)
        status = conn.execute("SELECT review_status FROM narrative_locations WHERE narrative_location_id = 'nl1'").fetchone()[0]
        conn.close()
        assert status == "machine_demoted_unmapped"
