"""Connect real market-data revisions to research re-activation.

Dependencies include the candidate asset plus every peer actually used by the
latest findings (SPY/VIX/IEF/DXY/gold etc.), evaluated only up to the research
decision as-of. Unrelated assets and post-cutoff data do not trigger a revision.
"""
from __future__ import annotations

import json
from typing import Any

from .db import Store


def research_snapshots(store: Store) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for r in store.conn.execute("SELECT research_id FROM research_v2_candidates"):
        rid = str(r["research_id"])
        as_of_row = store.conn.execute(
            "SELECT as_of FROM research_v2_candidates WHERE research_id=?", (rid,)).fetchone()
        as_of = str(as_of_row["as_of"] if as_of_row else "")
        deps = store.research_dependencies(rid, as_of)
        out[rid] = {iid: store.instrument_price_fingerprint(iid, as_of) for iid in deps}
    return out


def notify_price_changes(store: Store, before: dict[str, dict[str, str]],
                         after: dict[str, dict[str, str]],
                         reason: str = "price data revised",
                         batch: int | str | None = None) -> list[dict[str, Any]]:
    """One occurrence batch distinguishes duplicate delivery from a later repeat.

    A caller delivering the same update twice passes the same batch. A later
    ingestion/transition allocates a new batch even if the content returns to a
    previous value (B→C→B→C).
    """
    batch = batch if batch is not None else store.next_update_batch()
    created = []
    for rid, old_deps in before.items():
        new_deps = after.get(rid, {})
        for iid, old in old_deps.items():
            new = new_deps.get(iid, old)
            if new == old:
                continue
            # A->B->A creates a new transition key, so the final A is not swallowed.
            key = f"price:{iid}:{old[:12]}->{new[:12]}:b{batch}"
            uid = store.enqueue_research_update(rid, "price_revision", key, reason)
            if uid:
                store.set_research_workflow_state(rid, "PLANNED")
                store.add_research_event(rid, "research:evidence_update", reason,
                                         payload={"update_id": uid, "instrument": iid,
                                                  "before": old[:12], "after": new[:12]})
                created.append({"research_id": rid, "update_id": uid, "instrument": iid})
    return created
