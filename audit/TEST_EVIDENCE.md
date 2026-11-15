# TEST EVIDENCE (Phase 1 scan gate)

- Offline suite: **227 passed, 10 deselected** at commit `671f5fa` (scan-evidence v5; 
  test was added; final)).
- New scan-evidence cases: empty DB; fake config/data hash; same-row modified content; wrong as_of;
  stale/failed latest scan; partial ingest; missing report; report/scan-json/pipeline provenance or
  count mismatch; valid real scan.
- Real scan evidence: `scan-20261115T031540Z-4048c8`, as_of 2026-11-13, 358,310 prices,
  159,508 indicators, 1,506 anomalies, 5 transmissions, 11 opportunities; report/reports-json/pipeline
  hashes recorded in the manifest.
- The final proof is generated only after the freeze commit; see `audit/releases/`.
