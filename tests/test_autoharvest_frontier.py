import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(name, scripts / rel)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_priority_states_score_above_lower_priority_states():
    eng = load("autoharvest_engine_frontier", Path("lib/autoharvest_engine.py"))
    cfg = eng.HarvestConfig({"priority": {"states": {"WA": 60, "NSW": 15}, "route_families": {"local_history_serial": 55}}})
    route = {"route_family": "local_history_serial", "source_tier": "A"}
    assert eng.frontier_priority({**route, "state": "WA"}, cfg, "WA") > eng.frontier_priority({**route, "state": "NSW"}, cfg, "NSW")


def test_discovered_route_is_candidate_before_frontier():
    eng = load("autoharvest_engine_frontier_discovery", Path("lib/autoharvest_engine.py"))
    rows = eng.extract_route_candidates("<a href='https://example.test/archive'>Local archives</a>", "https://example.test/", {"route_id": "seed", "state": "WA"}, "run")
    assert rows
    assert rows[0]["status"] in {"frontier_eligible", "route_candidate"}
    assert rows[0]["route_family_guess"] == "state_archive_catalogue"


def test_high_confidence_discovered_route_can_enter_frontier():
    eng = load("autoharvest_engine_frontier_promote", Path("lib/autoharvest_engine.py"))
    mig = load("migrate_autoharvest_v1_frontier_promote", Path("migrate_autoharvest_v1.py"))
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            row = {
                "discovered_route_id": "d1",
                "run_id": "run",
                "discovered_from_route_id": "seed",
                "discovered_from_url": "https://example.test/",
                "candidate_source_name": "Local archives",
                "candidate_url": "https://example.test/archive",
                "state_guess": "WA",
                "route_family_guess": "state_archive_catalogue",
                "source_tier_guess": "B",
                "collection_mode_guess": "static_html_metadata",
                "evidence_or_discovery_guess": "evidence_possible",
                "confidence": 0.85,
                "status": "frontier_eligible",
                "reason_discovered": "trusted",
                "robots_status": "not_checked",
                "created_at": "now",
                "updated_at": "now",
            }
            eng.insert_discovered_routes(conn, [row])
            promoted = eng.promote_discovered_routes_to_frontier(conn, "run", eng.HarvestConfig({"priority": {"states": {"WA": 60}, "route_families": {"state_archive_catalogue": 50}}}))
            assert promoted == 1
            assert conn.execute("SELECT COUNT(*) FROM harvest_frontier WHERE route_id='d1'").fetchone()[0] == 1


def test_low_yield_noise_route_is_paused_by_rebalance():
    mig = load("migrate_autoharvest_v1_frontier", Path("migrate_autoharvest_v1.py"))
    reb = load("autoharvest_build_next_frontier_test", Path("autoharvest_build_next_frontier.py"))
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO harvest_frontier(frontier_id, run_id, route_id, url, status, priority_score, discovered_at) VALUES ('f','run','noisy','https://example.test','queued',1,'now')")
            conn.execute("INSERT INTO harvest_route_stats(run_id, route_id, candidates_seen, noise, updated_at) VALUES ('run','noisy',10,9,'now')")
            conn.commit()
        reb.rebalance(db, "run", ROOT / "config" / "autoharvest.yml", Path(temp) / "report.md")
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT status FROM harvest_frontier WHERE frontier_id='f'").fetchone()[0] == "paused"
