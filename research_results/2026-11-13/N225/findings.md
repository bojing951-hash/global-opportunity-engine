# Research Finding — N225 2026-11-13

- Event date: 2026-11-06
- Prior US session: 2026-11-05
- Status: INCONCLUSIVE
- Input SHA256: `1ba5745e6816e0050422493759da5d735390c935cabae23664288a77075cfbb9`
- Code commit: `8266fa6c3918c73849762c41ef7e626240c76cc6` / feature v2

## PIT alignment
- Asia same-day; US/FX previous US session; no same-date future US close
- US/FX data date: 2026-11-05; Asia data date: 2026-11-06

## What was acquired
- PIT-aligned same-day Asia returns plus PRIOR US-session returns/VIX/USDJPY
- Source: GOE prices DB

## Tests and results
- **local_asia_test**: pass=True — TOPIX co-move supports a broad Japan/local factor; association only
- **global_lead_test**: pass=True — prior US selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=True — Taiwan/Korea co-move supports regional Asia; tech-specific attribution not identified
- **fx_test**: pass=False — small prior FX move cannot explain a -6% equity move by itself
- **reversal_test**: pass=True — measured only from bars after the event through as-of

## Hypothesis updates
- **H-EQJP-LOCAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Broad co-move; not an independent instrument and not causal proof.
- **H-EQJP-GLOBAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Prior US session sold off and VIX spiked before Asia opened; consistent with transmission. The later same-date US close is not used.
- **H-EQJP-FX**: WEAKENED_BY_EVIDENCE — Small prior FX move cannot explain the equity move by itself.
- **H-EQJP-POLICY**: INSUFFICIENT_DATA — No scheduled event on 2026-11-06 in config/events.yaml; not enough to rule out policy news.
- **H-EQJP-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabricated values.
- **H-EQJP-ASIA-REGIONAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Regional co-move supported; sector/tech channel is not identified.

## What we learned
- On 2026-11-06, N225 returned -5.96%; TOPIX -6.50%.
- Prior US session (2026-11-05) SPY -4.41%, QQQ -6.49%, VIX +69.66%: a US-global lead is consistent, not contradicted. Using the later same-date US close would be lookahead.
- Taiwan -4.51% and Korea -6.02% fell; a North Asia co-move is supported, but tech-specific attribution is unavailable.
- Hong Kong -1.27% and China -1.44% were much smaller, so broad 'Asia' is too strong; the evidence is North Asia/Japan-Taiwan-Korea.
- Prior-session USDJPY -0.07%; too small to be the primary driver.
- Three-session post-event N225 return +6.64%.
- Japan-local and regional Asia explanations both survive; broad indices cannot separate them.
- No scheduled policy event on the date was found in config/events.yaml; that is not proof no policy news occurred.

## Still unknown
- TOPIX sector/constituent breadth
- Asia semiconductor exposure
- consensus/earnings revisions
- CFTC positioning at event
- policy/news calendar coverage on the date

## Next action
Retain in A/watch; acquire TOPIX sector breadth and Asia semiconductor exposure. Do not hand off unsupported deep asset research to B.

DISCOVERY VALUE: NOT VALIDATED