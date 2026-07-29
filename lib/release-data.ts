import type { FrontendData } from "@/lib/types";

export const FRONTEND_DATA_URL = process.env.NEXT_PUBLIC_FRONTEND_DATA_URL || "/data/frontend-interactive.json";
export const RELEASE_COUNT_CONTRACT_URL = "/data/release-count-contract.json";
export const RELEASE_MAP_OVERLAYS_URL = "/data/frontend-map-overlays.release-candidate.json";
export const RELEASE_COVERAGE_URL = "/data/release-coverage.release-candidate.json";
export const RELEASE_SOURCE_INTELLIGENCE_URL = "/data/source-intelligence.release-candidate.json";
export const RELEASE_REDIRECTS_URL = "/data/frontend-redirects.release-candidate.json";
export const RELEASE_CARDS_URL = "/data/release-cards.json";
export const RELEASE_CHARTS_URL = "/data/release-charts.json";

export type ReleaseCountContract = {
  generated_at: string;
  release_id: string;
  counts: {
    accepted_public_records: number;
    accepted_public_map_points: number;
    metadata_gap_items: number;
    lead_overlay_items: number;
    coverage_items_1926_2011: number;
    critical_hard_gaps_1926_2011: number;
    display_hard_gaps_1926_2011: number;
    id_redirects: number;
    url_redirects: number;
  };
  labels: Record<string, string>;
  rules: {
    metadata_items_are_public_records: boolean;
    lead_items_are_public_records: boolean;
    map_overlays_are_accepted_map_points: boolean;
  };
  status?: string;
  warnings?: string[];
  failures?: string[];
};

export type ReleaseMapOverlayItem = {
  overlay_id: string;
  source_table: string;
  source_row_id: string;
  title: string;
  target_state: string | null;
  target_locality: string | null;
  place_signal: string | null;
  display_label: string;
  map_display_status: string;
};

export type ReleaseMapOverlays = {
  accepted_public_map_count: number;
  generated_at: string;
  metadata_place_overlay: ReleaseMapOverlayItem[];
  lead_place_overlay: ReleaseMapOverlayItem[];
  unmapped_gap_items: ReleaseMapOverlayItem[];
};

export type ReleaseCoverageBand = {
  band: string;
  start_year: number;
  end_year: number;
  accepted_public_records: number;
  public_map_records: number;
  provisional_records: number;
  metadata_only_gap_layer: number;
  target_gap_leads: number;
  auxiliary_source_intelligence: number;
  visible_coverage_items: number;
  total_items: number;
};

export type ReleaseCoverage = {
  coverage: ReleaseCoverageBand[];
};

export type ReleaseRedirects = {
  id_redirects: Array<Record<string, string | number>>;
  url_redirects: Array<Record<string, string | number>>;
};

export type ReleaseSourceIntelligence = {
  source_layer_counts: Array<{ layer: string; count: number }>;
};

export type ReleaseSiteData = {
  countContract: ReleaseCountContract | null;
  mapOverlays: ReleaseMapOverlays | null;
  releaseCoverage: ReleaseCoverage | null;
  sourceIntelligence: ReleaseSourceIntelligence | null;
  redirects: ReleaseRedirects | null;
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

export function loadReleaseCountContract(): Promise<ReleaseCountContract | null> {
  return loadJson<ReleaseCountContract>(RELEASE_COUNT_CONTRACT_URL);
}

export function loadMapOverlays(): Promise<ReleaseMapOverlays | null> {
  return loadJson<ReleaseMapOverlays>(RELEASE_MAP_OVERLAYS_URL);
}

export function loadReleaseCoverage(): Promise<ReleaseCoverage | null> {
  return loadJson<ReleaseCoverage>(RELEASE_COVERAGE_URL);
}

export function loadSourceIntelligence(): Promise<ReleaseSourceIntelligence | null> {
  return loadJson<ReleaseSourceIntelligence>(RELEASE_SOURCE_INTELLIGENCE_URL);
}

export function loadRedirects(): Promise<ReleaseRedirects | null> {
  return loadJson<ReleaseRedirects>(RELEASE_REDIRECTS_URL);
}

export async function loadReleaseSiteData(): Promise<ReleaseSiteData> {
  const [countContract, mapOverlays, releaseCoverage, sourceIntelligence, redirects] = await Promise.all([
    loadReleaseCountContract(),
    loadMapOverlays(),
    loadReleaseCoverage(),
    loadSourceIntelligence(),
    loadRedirects(),
  ]);
  return { countContract, mapOverlays, releaseCoverage, sourceIntelligence, redirects };
}

export function resolveCanonicalId(id: string, redirects: ReleaseRedirects | null | undefined): string {
  if (!redirects?.id_redirects?.length) {
    return id;
  }
  const row = redirects.id_redirects.find((item) => String(item.from_id ?? "") === id);
  return row?.to_id ? String(row.to_id) : id;
}
