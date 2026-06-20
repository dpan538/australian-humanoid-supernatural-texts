export type DateBand = {
  id: string;
  label: string;
  start: number;
  end: number | null;
  role: string;
  record_count: number;
  planned_query_count: number;
};

export type Summary = {
  record_count: number;
  figure_count: number;
  query_count: number;
  source_count: number;
  location_count: number;
  precise_point_count: number;
  broad_location_count: number;
  map_cluster_count?: number;
  map_flag_count?: number;
  earliest_year: number | null;
  latest_year: number | null;
  state_record_counts: Record<string, number>;
  records_by_figure: Record<string, number>;
  records_by_year: Record<string, number>;
  ontology_counts: Record<string, number>;
  ethics_counts: Record<string, number>;
  source_type_counts: Record<string, number>;
  source_rollup: Record<string, { record_count: number; query_count: number }>;
};

export type RecordItem = {
  record_id: number;
  source_id: number;
  query_id: number | null;
  figure_id: number | null;
  external_id: string | null;
  title: string | null;
  publication: string | null;
  author: string | null;
  date_published: string | null;
  year: number | null;
  url: string | null;
  snippet: string | null;
  publicness_level: string | null;
  ingestion_status: string | null;
  source_name: string | null;
  source_type: string | null;
  canonical_figure: string | null;
  cluster: string | null;
  tier: string | null;
  include_status: string | null;
  figure_humanoid_degree: string | null;
  ontology_default: string | null;
  involves_indigenous_knowledge: number | boolean | null;
  canonical_figure_guess: string | null;
  figure_name_as_printed: string | null;
  ontology_code: string | null;
  humanoid_degree_code: string | null;
  source_voice: string | null;
  genre: string | null;
  publicness_code: string | null;
  relevance_code: string | null;
  ethics_flag: string | null;
  coding_notes: string | null;
  date_band: string;
  location_summary: string;
};

export type LocationItem = {
  record_id: number;
  relation_type: string | null;
  evidence_text: string | null;
  confidence: string | null;
  notes: string | null;
  place_name: string;
  region: string | null;
  state_territory: string | null;
  country: string | null;
  latitude: number | null;
  longitude: number | null;
  location_type: string | null;
  geocode_source: string | null;
  verification_status: string | null;
  year: number | null;
  title: string | null;
  canonical_figure: string | null;
  date_band: string;
  source_name?: string | null;
  source_type?: string | null;
  publication?: string | null;
  url?: string | null;
  ingestion_status?: string | null;
};

export type MapClusterItem = {
  cluster_id: string;
  cluster_type: string;
  state_territory: string;
  label: string;
  record_count: number;
  representative_record_id: number | null;
  location_role: string;
  location_precision: string;
  display_note: string;
};

export type MapFlagItem = {
  flag_id: string;
  record_id: number;
  state_territory: string;
  x: number;
  y: number;
  stem_dx: number;
  stem_dy: number;
  display_precision: string;
  source_location_type: string | null;
  confidence: string | null;
  title: string | null;
  year: number | null;
  canonical_figure: string | null;
};

export type FigureItem = {
  figure_id: number;
  canonical_name: string;
  cluster: string;
  tier: string;
  include_status: string;
  humanoid_degree: string | null;
  ontology_default: string | null;
  involves_indigenous_knowledge: boolean;
  sensitivity_notes: string | null;
  description: string | null;
  aliases: Array<{
    alias_id: number;
    alias: string;
    alias_type: string;
    search_priority: number;
    notes: string | null;
  }>;
  record_count: number;
  earliest_year: number | null;
  latest_year: number | null;
};

export type QueryItem = {
  query_id: number;
  figure_id: number | null;
  source_id: number;
  query_string: string;
  query_type: string;
  date_start: string | null;
  date_end: string | null;
  expected_noise_level: string | null;
  status: string | null;
  notes: string | null;
  source_name: string;
  source_type: string;
  canonical_name: string | null;
  date_band: string;
};

export type SourceItem = {
  source_id: number;
  source_name: string;
  source_type: string;
  base_url: string | null;
  access_method: string | null;
  publicness_level: string | null;
  ethics_notes: string | null;
};

export type FrontendData = {
  schema_version: string;
  generated_at: string;
  scope: {
    country: string;
    public_only: boolean;
    visual_mode: string;
    ethical_note: string;
  };
  summary: Summary;
  date_bands: DateBand[];
  records: RecordItem[];
  locations: LocationItem[];
  map_points: LocationItem[];
  map_clusters?: MapClusterItem[];
  map_flags?: MapFlagItem[];
  broad_locations: LocationItem[];
  figures: FigureItem[];
  queries: QueryItem[];
  sources: SourceItem[];
  attention_series: unknown[];
};
