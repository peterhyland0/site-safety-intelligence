"""Matching rules: sort a candidate establishment into MATCHED / UNCERTAIN / EXCLUDED for a GC's sub.

Pure functions (no I/O) so every rule is unit-tested. Ordered; first hit wins. Conservative by design:
a wrong split costs a little review, a wrong merge attaches someone else's history to the sub.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import jellyfish

from ssi.matching.trades import trade_conflict

MATCHED, UNCERTAIN, EXCLUDED = "matched", "uncertain", "excluded"

GENERIC_TOKENS: frozenset[str] = frozenset()  # filled from the warehouse macro at runtime (see run.py)


def jw(a: str, b: str) -> float:
    return jellyfish.jaro_winkler_similarity(a or "", b or "")


@dataclass
class Query:
    clean: str
    core: str
    state: str | None
    city: str | None
    trade: str | None
    tier: str  # 'distinctive' | 'medium' | 'generic'
    initials_only: bool
    sibling: str | None
    aliases: set[str] = field(default_factory=set)


@dataclass
class Candidate:
    establishment_key: str
    clean_name: str
    name_core: str
    legal_name: str | None
    dba_name: str | None
    state: str | None
    city: str | None
    zip5: str | None
    addr_key: str | None
    primary_naics4: str | None
    sibling_suffix: str | None
    initials_only: bool
    at_matched_address: bool = False  # filled by the address-expansion pass


@dataclass
class Decision:
    bucket: str
    rule_id: str
    reason: str


def tokens(s: str | None) -> list[str]:
    return [t for t in (s or "").split(" ") if t]


def typo_equal(a: str, b: str) -> bool:
    """Cores that differ only by spelling slips (GORIE/GORRIE, BRASFIEL/BRASFIELD)."""
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = tokens(a), tokens(b)
    if len(ta) == len(tb) and all(jw(x, y) >= 0.9 for x, y in zip(ta, tb)):
        return True
    return jw(a, b) >= 0.94


def only_generic_difference(a: str, b: str, generic: frozenset[str]) -> bool:
    diff = set(tokens(a)) ^ set(tokens(b))
    return all(t in generic for t in diff)


DESCRIPTORS: frozenset[str] = frozenset()  # set from the warehouse macro ssi_descriptor_tokens() (see run.py)


def only_descriptor_difference(a: str, b: str, descriptors: frozenset[str] | None = None) -> bool:
    """True when two names differ only by descriptor words (GENERAL, CONTRACTORS, SERVICES…), not by a
    trade word (HOMES vs TILE): the eval showed trade-word differences are usually sister companies."""
    d = descriptors if descriptors is not None else DESCRIPTORS
    diff = set(tokens(a)) ^ set(tokens(b))
    return all(t in d for t in diff)


def decide(q: Query, c: Candidate, generic: frozenset[str], descriptors: frozenset[str] | None = None) -> Decision:
    same_full = c.clean_name == q.clean or c.clean_name in q.aliases or q.clean in {c.legal_name, c.dba_name}
    core_equal = bool(q.core) and c.name_core == q.core
    same_state = bool(q.state) and c.state == q.state
    same_city = bool(q.city) and bool(c.city) and c.city.upper() == q.city.upper()
    distinctive = q.tier == "distinctive"
    generic_diff = core_equal and only_generic_difference(c.clean_name, q.clean, generic)
    descriptor_diff = core_equal and only_descriptor_difference(c.clean_name, q.clean, descriptors)
    conflict = trade_conflict(q.trade, c.primary_naics4)

    # S1: "… OF OREGON" vs "… OF AMERICA", "… AT ELAN" vs "… AT MERIDIAN": usually sibling companies
    if (q.sibling or c.sibling_suffix) and q.sibling != c.sibling_suffix and (core_equal or same_full or typo_equal(q.core, c.name_core)):
        return Decision(UNCERTAIN, "S1", "Names differ only by a location/project suffix, which usually means a sibling company")

    def matched(rule: str, reason: str) -> Decision:
        if conflict:
            return Decision(UNCERTAIN, rule + "_trade", reason + ", but OSHA lists a different trade")
        return Decision(MATCHED, rule, reason)

    if same_full and same_state and (distinctive or same_city):
        return matched("M1", "Same name in the same state" + ("" if distinctive else " and city"))
    if descriptor_diff and same_state and distinctive:
        return matched("M1b", "Same distinctive name, differing only by words like GENERAL or CONTRACTORS, in the same state")
    if c.at_matched_address and (same_full or descriptor_diff or jw(q.clean, c.clean_name) >= 0.93
                                 or (typo_equal(q.core, c.name_core) and only_generic_difference(c.clean_name, q.clean, generic)
                                     and not core_equal)):
        return matched("M2", "Same address as a matched record; name differs only by spelling")
    if (same_full or descriptor_diff) and not same_state and distinctive:
        return matched("M3", f"Same distinctive name, another state ({c.state or 'unknown'})")
    if generic_diff and not descriptor_diff and distinctive:
        return Decision(UNCERTAIN, "U3", "Same family name but a different trade; often a sister company")
    if q.core and c.name_core and not core_equal and not typo_equal(q.core, c.name_core):
        # do the cores differ on a real (non-generic) word that has no near-spelling on the other side?
        qa, ca = set(tokens(q.core)), set(tokens(c.name_core))
        unmatched = [t for t in qa ^ ca if t not in generic and not any(jw(t, u) >= 0.9 for u in (ca if t in qa else qa))]
        if unmatched:
            return Decision(EXCLUDED, "X1", "Different company name (" + ", ".join(sorted(unmatched)[:3]) + ")")
    if not q.core and not c.name_core and not same_full:
        return Decision(EXCLUDED, "X2", "Different generic name")
    if not q.core and same_full and q.state and c.state and not same_state and not c.at_matched_address:
        # a name made only of common words (QUALITY ROOFING) in another state is almost always another company
        return Decision(EXCLUDED, "X4", f"Common name, different state ({c.state})")
    if not distinctive and not same_full:
        # a common name (CLARK, ABC) plus different trade words: only a same-city record could be related
        if same_state and (same_city or c.at_matched_address):
            return Decision(UNCERTAIN, "U2", "Related name in the same city; could be a sister company")
        return Decision(EXCLUDED, "X3", "Different company sharing a common name")
    if q.initials_only or c.initials_only:
        return Decision(UNCERTAIN, "G1", "Initials-only names are easily confused")
    return Decision(UNCERTAIN, "U", "Could be the same company; needs more evidence")
