#!/usr/bin/env python3
"""Probe no-credential access-platform endpoints as discovery/decomposition only."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from mine_noauth_access_platforms_for_gap import mine


def run(db: Path, registry: Path, run_id: str, out_dir: Path, execute: bool) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = mine(db, registry, run_id, out_dir, execute)
    source_report = out_dir / "access_platform_gap_mining_report.md"
    endpoint_report = out_dir / "access_platform_endpoint_report.md"
    if source_report.exists():
        shutil.copyfile(source_report, endpoint_report)
    else:
        endpoint_report.write_text(
            "\n".join(
                [
                    "# Access Platform Endpoint Report",
                    "",
                    f"- Generated: `{now_iso()}`",
                    f"- Run ID: `{run_id}`",
                    f"- Execute: `{str(execute).lower()}`",
                    "- Access platforms are evidence by default: `no`",
                    "- Public records mutated: `no`",
                    "- Map flags mutated: `no`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    return {**summary, "report": str(endpoint_report), "public_mutation": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--run-id", default="noauth_structured_endpoint_access_001")
    parser.add_argument("--out-dir", default="data/processed/v2/autoharvest/structured_endpoints/access_platforms")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(Path(args.db), Path(args.registry), args.run_id, Path(args.out_dir), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
