"""A sub can be on a project once.

Two entries are the same sub when their names clean to the same string with the matcher's own clean_name()
(case, punctuation, LLC/Inc/Co, "The", "&"/"and"), and they're in the same state. Trade words count, so
ABC Roofing and ABC Electric stay two subs. The city doesn't: a typo'd city ("Brunell" for Bunnell)
shouldn't let the same company in twice.
"""
from __future__ import annotations

from ssi.store import warehouse


def name_keys(names: list[str]) -> list[str]:
    """clean_name() of each name, in one warehouse query (the same macro the matcher uses)."""
    if not names:
        return []
    return warehouse.one("SELECT list_transform(?::VARCHAR[], x -> clean_name(x)) AS k", [names])["k"]


def find(new: list[dict], existing: list[dict]) -> list[dict]:
    """Rows of `new` ({name, key, state}, in order) that repeat a sub already on the project (`existing`:
    {sub_id, name, key, state}) or an earlier row of the same batch. Returns {row, name, message} per repeat."""
    seen = {(e["key"], e["state"]): e for e in existing if e["key"]}
    out = []
    for i, r in enumerate(new):
        if not r["key"]:
            continue
        hit = seen.get((r["key"], r["state"]))
        if hit is None:
            seen[(r["key"], r["state"])] = {**r, "sub_id": None}
        elif hit["sub_id"] is None:
            out.append({"row": i, "name": r["name"], "message": f'Same company as "{hit["name"]}" above.'})
        elif hit["name"].strip().upper() == r["name"].strip().upper():
            out.append({"row": i, "name": r["name"], "message": "Already on this project.",
                        "sub_id": str(hit["sub_id"])})
        else:
            out.append({"row": i, "name": r["name"], "message": f'Already on this project as "{hit["name"]}".',
                        "sub_id": str(hit["sub_id"])})
    return out
