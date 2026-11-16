"""Connect real market-data revisions to research re-activation."""
from __future__ import annotations

from typing import Any

from .db import Store


def candidate_price_fingerprints(store: Store) -> dict[str, str]:
    ids = set()
    for r in store.conn.execute("SELECT payload_json FROM research_v2_candidates"):
        import json
        try:
            p = json.loads(r["payload_json"] or "{}")
            ids.update(str(x) for x in (p.get("instruments") or []))
        except Exception:
            continue
    return {iid: store.instrument_price_fingerprint(iid) for iid in sorted(ids)}


def notify_price_changes(store: Store, before: dict[str, str], after: dict[str, str],
                         reason: str = "price data revised") -> list[dict[str, Any]]:
    created = []
    for iid, old in before.items():
        new = after.get(iid, old)
        if new == old:
            continue
        for rid in store.research_ids_for_instrument(iid):
            key = f"price:{iid}:{new}"
            uid = store.enqueue_research_update(rid, "price_revision", key, reason)
            if uid:
                store.set_research_workflow_state(rid, "PLANNED")
                store.add_research_event(rid, "research:evidence_update", reason,
                                         payload={"update_id": uid, "instrument": iid,
                                                  "before": old, "after": new})
                created.append({"research_id": rid, "update_id": uid, "instrument": iid})
    return created
