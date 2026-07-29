#!/usr/bin/env python3
"""Audit frontend display files for stale counts and release-layer label misuse."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.post_release_site import read_json, write_markdown


SEARCH_DIRS = ["frontend", "src", "public", "app", "pages", "components", "lib"]
TEXT_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".css"}
STALE_COUNTS = ["1,593", "1593", "4,393", "4393", "37,964", "37964", "25,000", "25000", "11,343", "11343", "2,646", "2646", "551"]
STALE_IMPORT_PATTERNS = [
    "frontend-data.experimental-4000",
    "frontend-data.gap-public-web",
    "frontend-data.live-crawl",
    "frontend-data.1926-1976-gap",
]
ALLOWED_GENERATED = {
    "public/data/release-count-contract.json",
    "public/data/release-counts.json",
    "public/data/release-coverage.release-candidate.json",
    "public/data/frontend-map-overlays.release-candidate.json",
    "public/data/frontend-redirects.release-candidate.json",
    "public/data/source-intelligence.release-candidate.json",
    "public/data/release-cards.json",
    "public/data/release-charts.json",
}


def iter_frontend_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for name in SEARCH_DIRS:
        root = repo_root / name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
                continue
            if "node_modules" in path.parts or ".next" in path.parts:
                continue
            files.append(path)
    return sorted(set(files))


def is_allowed_count_hit(rel: str, text: str) -> bool:
    if rel in ALLOWED_GENERATED:
        return True
    if rel.startswith("public/data/"):
        return True
    if rel == "lib/au-map-data.ts":
        return True
    if "release-count-contract" in text or "loadReleaseCountContract" in text or "RELEASE_COUNT_CONTRACT_URL" in text:
        return True
    if "accepted public map count must remain 1,593" in text.lower():
        return True
    return False


def count_contextual_line(line: str) -> bool:
    normalized = line.lower()
    return any(token in normalized for token in ["record", "map", "coverage", "lead", "metadata", "gap", "redirect", "count"])


def audit(repo_root: Path, count_contract: Path, out_dir: Path) -> dict[str, object]:
    contract = read_json(count_contract, {}) or {}
    count_hits: list[dict[str, object]] = []
    stale_imports: list[dict[str, object]] = []
    label_misuse: list[dict[str, object]] = []
    dependency_map: list[dict[str, object]] = []
    files_to_update: list[dict[str, object]] = []

    for path in iter_frontend_files(repo_root):
        rel = str(path.relative_to(repo_root))
        text = path.read_text(encoding="utf-8", errors="ignore")
        deps = []
        for token in [
            "frontend-data.json",
            "release-count-contract",
            "release-cards",
            "release-charts",
            "frontend-map-overlays",
            "frontend-redirects",
            "release-coverage",
            "source-intelligence",
            "loadReleaseCountContract",
            "loadMapOverlays",
            "loadReleaseCoverage",
            "loadRedirects",
        ]:
            if token in text:
                deps.append(token)
        if deps:
            dependency_map.append({"file": rel, "dependencies": ";".join(sorted(set(deps)))})

        file_issues = 0
        allowed_counts = is_allowed_count_hit(rel, text)
        for line_no, line in enumerate(text.splitlines(), 1):
            for count in STALE_COUNTS:
                if count in line and count_contextual_line(line) and not allowed_counts:
                    count_hits.append({"file": rel, "line": line_no, "count": count, "context": line.strip()[:220]})
                    file_issues += 1
            for pattern in STALE_IMPORT_PATTERNS:
                if pattern in line:
                    stale_imports.append({"file": rel, "line": line_no, "import": pattern, "context": line.strip()[:220]})
                    file_issues += 1
            normalized = re.sub(r"\s+", " ", line.strip().lower())
            if rel.startswith("public/data/"):
                continue
            if re.search(r"\b(leads?|metadata-only|metadata only)\b.{0,80}\b(accepted\s+)?public\s+records?\b", normalized):
                if "not a public record" not in normalized and "not public records" not in normalized and "are not accepted public records" not in normalized:
                    label_misuse.append({"file": rel, "line": line_no, "issue": "research_layer_called_record", "context": line.strip()[:220]})
                    file_issues += 1
            if re.search(r"\bmap overlays?\b.{0,80}\baccepted\s+map", normalized) and "not" not in normalized:
                label_misuse.append({"file": rel, "line": line_no, "issue": "overlay_called_accepted_map", "context": line.strip()[:220]})
                file_issues += 1
        if file_issues:
            files_to_update.append({"file": rel, "issue_count": file_issues})

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "hardcoded_count_hits.csv", count_hits, ["file", "line", "count", "context"])
    write_csv(out_dir / "stale_data_imports.csv", stale_imports, ["file", "line", "import", "context"])
    write_csv(out_dir / "label_misuse.csv", label_misuse, ["file", "line", "issue", "context"])
    write_csv(out_dir / "page_data_dependency_map.csv", dependency_map, ["file", "dependencies"])
    write_csv(out_dir / "frontend_files_to_update.csv", files_to_update, ["file", "issue_count"])

    status = "FAIL" if label_misuse else "WARN" if count_hits or stale_imports else "PASS"
    lines = [
        "# Frontend Display Contract Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Status: `{status}`",
        f"- Count contract: `{count_contract}`",
        f"- Accepted public map points in contract: `{contract.get('counts', {}).get('accepted_public_map_points', 0)}`",
        f"- Hardcoded count hits: `{len(count_hits)}`",
        f"- Stale data imports: `{len(stale_imports)}`",
        f"- Label misuse hits: `{len(label_misuse)}`",
        f"- Files with update signals: `{len(files_to_update)}`",
        "",
        "## Interpretation",
        "- PASS means frontend/source text currently references the release contract or sidecar loaders for release-layer displays.",
        "- WARN means stale count/import cleanup is recommended.",
        "- FAIL means a page appears to call metadata-only items or research leads accepted public records.",
    ]
    write_markdown(out_dir / "frontend_display_audit.md", lines)
    return {
        "status": status,
        "hardcoded_count_hits": len(count_hits),
        "stale_data_imports": len(stale_imports),
        "label_misuse": len(label_misuse),
        "files_to_update": len(files_to_update),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--count-contract", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    result = audit(Path(args.repo_root), Path(args.count_contract), Path(args.out_dir))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
