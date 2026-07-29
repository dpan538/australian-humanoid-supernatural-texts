#!/usr/bin/env python3
"""Verify or create frontend release sidecar loader integration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.post_release_site import SIDECAR_FILES, read_json, write_markdown


LOADER_TEMPLATE = """import type { FrontendData } from "@/lib/types";

export const FRONTEND_DATA_URL = process.env.NEXT_PUBLIC_FRONTEND_DATA_URL || "/data/frontend-data.json";
export const RELEASE_COUNT_CONTRACT_URL = "/data/release-count-contract.json";
export const RELEASE_MAP_OVERLAYS_URL = "/data/frontend-map-overlays.release-candidate.json";
export const RELEASE_COVERAGE_URL = "/data/release-coverage.release-candidate.json";
export const RELEASE_SOURCE_INTELLIGENCE_URL = "/data/source-intelligence.release-candidate.json";
export const RELEASE_REDIRECTS_URL = "/data/frontend-redirects.release-candidate.json";
export const RELEASE_CARDS_URL = "/data/release-cards.json";
export const RELEASE_CHARTS_URL = "/data/release-charts.json";

export type ReleaseSiteData = {
  countContract: Record<string, unknown> | null;
  mapOverlays: Record<string, unknown> | null;
  releaseCoverage: Record<string, unknown> | null;
  sourceIntelligence: Record<string, unknown> | null;
  redirects: Record<string, unknown> | null;
};

async function loadJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      if (process.env.NODE_ENV === "development") {
        console.warn(`Release sidecar missing: ${url} (${response.status})`);
      }
      return null;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn(`Release sidecar could not be loaded: ${url}`, error);
    }
    return null;
  }
}

export function loadAcceptedFrontendData(): Promise<FrontendData | null> {
  return loadJson<FrontendData>(FRONTEND_DATA_URL);
}

export function loadReleaseCountContract() {
  return loadJson<Record<string, unknown>>(RELEASE_COUNT_CONTRACT_URL);
}

export function loadMapOverlays() {
  return loadJson<Record<string, unknown>>(RELEASE_MAP_OVERLAYS_URL);
}

export function loadReleaseCoverage() {
  return loadJson<Record<string, unknown>>(RELEASE_COVERAGE_URL);
}

export function loadSourceIntelligence() {
  return loadJson<Record<string, unknown>>(RELEASE_SOURCE_INTELLIGENCE_URL);
}

export function loadRedirects() {
  return loadJson<Record<string, unknown>>(RELEASE_REDIRECTS_URL);
}
"""


REQUIRED_LOADER_NAMES = [
    "loadAcceptedFrontendData",
    "loadReleaseCountContract",
    "loadMapOverlays",
    "loadReleaseCoverage",
    "loadSourceIntelligence",
    "loadRedirects",
]


def integrate(repo_root: Path, release_package: Path, count_contract: Path, execute: bool) -> dict[str, object]:
    out_dir = repo_root / "data" / "processed" / "v2" / "post_release_site_integration"
    out_dir.mkdir(parents=True, exist_ok=True)
    modified: list[dict[str, str]] = []
    warnings: list[str] = []
    missing_sidecars = [name for name in SIDECAR_FILES if not (release_package / name).exists()]
    public_missing = [name for name in SIDECAR_FILES if name != "release-disclaimer.md" and not (repo_root / "public" / "data" / name).exists()]
    if not count_contract.exists():
        warnings.append(f"missing count contract {count_contract}")
    if missing_sidecars:
        warnings.append(f"missing package sidecars: {', '.join(missing_sidecars)}")
    if public_missing:
        warnings.append(f"missing public sidecars: {', '.join(public_missing)}")

    loader = repo_root / "lib" / "release-data.ts"
    loader_text = loader.read_text(encoding="utf-8") if loader.exists() else ""
    missing_loader_names = [name for name in REQUIRED_LOADER_NAMES if name not in loader_text]
    if missing_loader_names and execute:
        loader.parent.mkdir(parents=True, exist_ok=True)
        loader.write_text(LOADER_TEMPLATE, encoding="utf-8")
        modified.append({"file": str(loader.relative_to(repo_root)), "action": "created_or_replaced_release_loader"})
    elif missing_loader_names:
        modified.append({"file": str(loader.relative_to(repo_root)), "action": "would_create_release_loader"})

    expected_refs = {
        "components/archive-terminal.tsx": ["loadReleaseSiteData", "ReleaseLayerStrip", "ReleaseMapOverlayPanel"],
        "components/source/source-view.tsx": ["ReleaseSiteData", "RESEARCH LAYERS"],
        "app/about/page.tsx": ["loadReleaseContractForAbout", "METADATA-ONLY GAP ITEMS"],
    }
    for rel, tokens in expected_refs.items():
        path = repo_root / rel
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        missing = [token for token in tokens if token not in text]
        if missing:
            warnings.append(f"{rel} missing release integration tokens: {', '.join(missing)}")

    write_csv(out_dir / "files_modified.csv", modified, ["file", "action"])
    write_markdown(
        out_dir / "integration_plan.md",
        [
            "# Release Sidecar Integration Plan",
            "",
            f"- Generated: `{now_iso()}`",
            "- Accepted public data remains in `public/data/frontend-data.json`.",
            "- Release sidecars remain separate and are loaded through `lib/release-data.ts`.",
            "- Metadata-only items and research leads remain labelled as not public records.",
            "- Map overlays remain labelled as not accepted public map points.",
        ],
    )
    status = "PASS" if not warnings else "WARN"
    write_markdown(
        out_dir / "integration_apply_report.md",
        [
            "# Release Sidecar Integration Apply Report",
            "",
            f"- Generated: `{now_iso()}`",
            f"- Mode: `{'execute' if execute else 'dry-run'}`",
            f"- Status: `{status}`",
            f"- Loader utility present: `{'yes' if loader.exists() else 'no'}`",
            f"- Missing package sidecars: `{len(missing_sidecars)}`",
            f"- Missing public sidecars: `{len(public_missing)}`",
            f"- Files modified by script: `{len(modified) if execute else 0}`",
            "- DB mutated: `no`",
            "- Leads promoted: `no`",
            "- Public map flags changed: `no`",
            "",
            "## Warnings",
            *(f"- {warning}" for warning in warnings),
        ],
    )
    return {"status": status, "warnings": warnings, "files_modified": len(modified) if execute else 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--release-package", required=True)
    parser.add_argument("--count-contract", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = integrate(Path(args.repo_root), Path(args.release_package), Path(args.count_contract), args.execute)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
