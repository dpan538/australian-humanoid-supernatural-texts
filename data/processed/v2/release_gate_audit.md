# Release Gate Audit

- Generated: `2026-07-04T15:44:29+00:00`

| gate_name | gate_status | observed_value | threshold_value | details |
| --- | --- | --- | --- | --- |
| temporal_1930_1969_share | WARN | 1.23 | >=5% | 1930-1969 share should not remain near-empty. |
| non_ayr_gap_accepted_records | WARN | 29 | >=300 | Gap records should not rely on AYR or access platforms alone. |
| discovery_only_accepted_leakage | PASS | 0 | 0 | Discovery-only sources must not be accepted as evidence. |
| mapped_records_missing_required_place_evidence | FAIL | 2911 | 0 | Mapped public flags need place text, role, coordinates, and review status. |
| single_evidence_source_org_share | PASS | 0.1984 | 0.2 | One evidence source organisation should not dominate the corpus. |
| single_access_platform_share_without_originals | PASS | 0.7824 | 0.35 | Access-platform dominance is risky when original source names are missing. |
| nsw_qld_vic_mapped_share | PASS | 52.15 | <=80% | Map balance should improve outside NSW/QLD/VIC. |
| act_new_mapped_candidate_floor | WARN | 0 | 20 | State-first target floor after collection run. |
| nt_new_mapped_candidate_floor | WARN | 0 | 50 | State-first target floor after collection run. |
| sa_new_mapped_candidate_floor | WARN | 0 | 70 | State-first target floor after collection run. |
| tas_new_mapped_candidate_floor | WARN | 0 | 40 | State-first target floor after collection run. |
| wa_new_mapped_candidate_floor | WARN | 0 | 80 | State-first target floor after collection run. |
