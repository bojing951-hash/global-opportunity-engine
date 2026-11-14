# V1 FREEZE — 2026-11-14

- Commit: `1f2b341b1bc148777663d2b2fec4e98f4adc62c6`
- Tag: `v1-frozen-1f2b341`
- Branch before V2: `fix/autonomous-audit-remediation`
- Tests: 157 offline passed; 9 network deselected.
- Data snapshot: `data/goe.db` scan `scan-20261114T092442Z-5ef9b9`, as_of 2026-11-13;
  1,506 anomalies; 11 candidates = 2 watch / 3 low_priority / 2 invalidated / 4 excluded;
  0 deep_research; research queue = 2 (OPP-0002 DXY, OPP-0003 N225).
- config_hash: `7d4d8ae1a7ca110204f522359f57e8c627c89cdec753eea29b51af4a486fc187`
- data_hash: `9ddd93ef2a456ee16e94985b1918a820e8415c72596dba8117662287207b39ef`
- Replay artifact: `reports/validation_cases_20261114T092812Z.md` (7/7 strict case-entity).
- V1 blind evaluation: engine 1.188 < anomaly 1.521 < max-price 1.312 (n=12/method).
- V1 forward: engine +7.12%, ex-top +2.45%, class-relative +2.99%, beat-class 42%.
- Handoff: real run refused (`unmapped`), task `not_completed:refused`, exit 2; no ok_valid.

V1 is frozen for comparison. V2 work happens on `architecture/research-v2`; V1 code/scoring is not overwritten.
