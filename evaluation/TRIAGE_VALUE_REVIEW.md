# Triage value review — frozen 2026-11-13 candidate window

Rule frozen before review: compare the existing 20-candidate queue against a simple
|1-month return| / anomaly-score ordering. No candidate was added or removed after seeing
the comparison.

| View | Result |
|---|---|
| Simple anomaly/return screen | 20 candidates; no explicit “explained vs unexplained” distinction |
| GOE qualification | 0 research-ready, 4 evidence-to-collect, 16 intelligence-only, plus 1 supplemental data-artifact case |
| User/expert ratings | **not collected** |

GOE’s additional output is not “more opportunities”; it is a reason to stop on 16 items
and a specific missing-evidence request for 4. Whether that saves user review time or picks
better questions cannot be established without the user/independent ratings.

Neutral candidate cards: `evaluation/triage_cards.json`.
Blank rating sheet: `evaluation/triage_scores_template.csv`.
Method mapping (hidden from raters): `evaluation/triage_method_mapping.json`.
The fixed simple baseline and GOE selection sets are in the mapping file; the card file
does not expose GOE class/rating.

**TRIAGE VALUE: NOT VALIDATED.**

## Frozen comparison setup

- Window/as-of: `2026-11-13`; source: the existing 20-candidate artifact.
- Same asset pool, same available facts, maximum **10** output items.
- Simple baseline: absolute 1-month return, then anomaly score (rules frozen before viewing GOE output).
- GOE selection: the pre-existing `watch`/`research` queue (4 items, fewer than 10; not padded).
- Cards are neutral: no GOE class/rating/reason; scoring sheet is blank.
- Mapping of cards to method is separate and must not be shown to raters.
- No ratings have been entered; this is not a user/expert validation.
