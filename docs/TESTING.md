# Test taxonomy and commands

| Layer | Location / marker | Default? | Data |
|---|---|---|---|
| unit | `tests/test_*.py` (no marker) | yes | synthetic in-memory/tmp_path |
| contract | `tests/test_contracts.py` | yes | synthetic records, no `data/goe.db` |
| integration | `tests/test_pipeline_e2e.py`, readiness/handoff | yes | tmp_path SQLite fixture |
| network | `@pytest.mark.network` | no (`-m 'not network and not realdata'`) | live sources |
| real-data | `@pytest.mark.realdata` + `GOE_SLOW=1` | no | explicit prepared DB/artifacts |
| slow | `@pytest.mark.slow` | optional | long windows |

Commands:
```bash
pytest tests -q                         # required offline suite, clean checkout
pytest tests -o addopts="" -q           # same, with explicit summary count
pytest tests -q -m network              # only network tests (needs connectivity)
GOE_SLOW=1 pytest tests -q -m realdata  # prepared real DB/artifacts
```
No default test may create/read `data/goe.db`; real-data tests must point at an explicit
`GOE_TEST_DB`/fixture and are never silently skipped as a substitute for a required test.
