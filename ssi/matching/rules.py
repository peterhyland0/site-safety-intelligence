"""Matching rules: sort a candidate establishment into MATCHED / UNCERTAIN / EXCLUDED for a GC's sub.

Pure functions (no I/O) so every rule is unit-tested. Ordered; first hit wins. Conservative by design:
a wrong split costs a little review, a wrong merge attaches someone else's history to the sub.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import jellyfish

from ssi.matching.trades import trade_conflict

MATCHED, UNCERTAIN, EXCLUDED = "matched", "uncertain", "excluded"

GENERIC_TOKENS: frozenset[str] = frozenset()  # filled from the warehouse macro at runtime (see run.py)


# A record filed as a branch or division of the sub ("BARNHART CRANE RIGGING OKLAHOMA CITY BRANCH")
BRANCH_WORDS = frozenset({"BRANCH", "DIVISION", "DIV", "OFFICE", "REGION", "REGIONAL", "DISTRICT"})
# A generation suffix tells a father from a son (SERGIO CAZARES vs SERGIO CAZARES SR)
GENERATIONS = frozenset({"JR", "SR", "II", "III", "IV"})


def jw(a: str, b: str) -> float:
    return jellyfish.jaro_winkler_similarity(a or "", b or "")


@dataclass
class Query:
    clean: str
    core: str
    state: str | None
    city: str | None
    trade: str | None
    tier: str  # 'distinctive' | 'medium' | 'generic' | 'person'
    initials_only: bool
    sibling: str | None
    aliases: set[str] = field(default_factory=set)
    incorporated: bool = False  # a person's name typed with a legal form (ROBERT J DEVEREAUX CORP); set by run.match
    # the sub's other names (legal name, DBA, licence names), each described on its own: a record that matches
    # only one of them is judged by that name's distinctiveness
    alias_queries: dict[str, Query] = field(default_factory=dict)


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
    related_only: bool = False  # a facility in scope only by company name (not coded as construction)
    is_jv: bool = False  # a joint venture (entity.establishment.is_jv)
    incorporated: bool = False  # one of its raw names has a legal form; set by run.match for a person's name


@dataclass
class Decision:
    bucket: str
    rule_id: str
    reason: str


_CITY_ABBREV = (("SAINT ", "ST "), ("MOUNT ", "MT "), ("FORT ", "FT "), ("SAINTE ", "STE "))


def norm_city(city: str | None) -> str:
    """LaFollette = LA FOLLETTE, St. Louis = Saint Louis, San José = SAN JOSE: compare cities without spaces,
    punctuation or accents."""
    folded = "".join(ch for ch in unicodedata.normalize("NFKD", city or "") if not unicodedata.combining(ch))
    c = " " + folded.upper().strip() + " "
    for long, short in _CITY_ABBREV:
        c = c.replace(" " + long, " " + short)
    return "".join(ch for ch in c if ch.isalnum())


def tokens(s: str | None) -> list[str]:
    return [t for t in (s or "").split(" ") if t]


def near_spelling(x: str, y: str) -> bool:
    """Two words a slip apart: similar, and about one letter apart in length (COLMEX vs COLE is not)."""
    return jw(x, y) >= 0.9 and abs(len(x) - len(y)) <= 1


def typo_equal(a: str, b: str) -> bool:
    """Cores that differ only by spelling slips (GORIE/GORRIE, BRASFIEL/BRASFIELD)."""
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = tokens(a), tokens(b)
    # a slip changes a word by about one letter: COLMEX vs COLE (two letters short) is another name
    if len(ta) == len(tb) and all(near_spelling(x, y) for x, y in zip(ta, tb)):
        return True
    return jw(a, b) >= 0.94 and abs(len(a) - len(b)) <= 1


def one_slip(a: str, b: str) -> bool:
    """A typing slip safe to search by when a city backs it up: one letter dropped or added, or two
    neighbours swapped (MCKENNYS / MCKENNEYS), past the first three letters of a name of 7+ letters.
    A replaced letter is not one: in licence data BORA / KORA and MEND / MEAD are usually other companies.
    Nor are digits (G6 / G2) or spacing (PLUM LINE / PLUMBLINE)."""
    if a == b or any(ch.isdigit() for ch in a + b) or min(len(a.replace(" ", "")), len(b.replace(" ", ""))) < 7:
        return False
    if len(a) == len(b):  # a swap of two neighbours
        d = [i for i in range(len(a)) if a[i] != b[i]]
        if not (len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]):
            return False
        pos, chars = d[0], a[d[0]] + a[d[1]]
    elif abs(len(a) - len(b)) == 1:  # a dropped or added letter
        s, long_ = sorted((a, b), key=len)
        pos = next((i for i in range(len(s)) if s[i] != long_[i]), len(s))
        if s != long_[:pos] + long_[pos + 1:]:
            return False
        chars = long_[pos]
    else:
        return False
    return pos >= 3 and " " not in chars


def is_jv_name(clean: str) -> bool:
    """A joint venture's name; the is_jv macro."""
    return bool(re.search(r"\b(JV|JOINT VENTURE)\b", clean or ""))


def trade_swap(a: str, b: str, generic: frozenset[str], descriptors: frozenset[str]) -> list[str]:
    """The trade words of two names when each has one the other lacks (EENIGENBURG FRAMING vs EENIGENBURG ROOFING):
    usually sister companies, as in U3. Forms of one word (PAINTING / PAINTERS, ROOF / ROOFING) are not a swap,
    and neither is a name with a trade word added (SMITH ROOFING SIDING). [] when there is no swap."""
    ta, tb = set(tokens(a)), set(tokens(b))
    trade = generic - descriptors
    xa, xb = sorted(t for t in ta - tb if t in trade), sorted(t for t in tb - ta if t in trade)
    if xa and xb and not any(x[:4] == y[:4] for x in xa for y in xb):
        return xa + xb
    return []


def different_people(a: str, b: str, given: frozenset[str]) -> bool:
    """Two people's names that can't be one person: another generation (SERGIO CAZARES vs SERGIO CAZARES SR) or
    no given name in common (MARIO vs MAURICIO CONTRERAS), unless the given names are one spelt or shortened
    differently (MARCOS / MARCUS, STEVE / STEVEN)."""
    ta, tb = tokens(a), tokens(b)
    if set(ta) & GENERATIONS != set(tb) & GENERATIONS:
        return True
    ga, gb = {t for t in ta if t in given}, {t for t in tb if t in given}
    return bool(ga) and bool(gb) and not any(x == y or near_spelling(x, y) or x.startswith(y) or y.startswith(x)
                                             for x in ga for y in gb)


# Generic words that are part of a person's own name or join two names, so they don't make it a company's
NAME_JOINS = frozenset({"DE", "DBA", "OF", "AT"})


def named_company(clean: str, core: str, generic: frozenset[str]) -> bool:
    """A person's name plus a trade or company word: a company named after a person (DAVID E HARVEY BUILDERS, FRED
    CHRISTEN SONS), not a sole proprietor's bare name (JOSE A HERNANDEZ, JOSE DE JESUS JUAREZ). In the warehouse 8%
    of bare person names recur in another city, up to 36 cities for JOSE GARCIA; 3% of these do, mostly real
    companies with offices (DAVID WEEKLEY HOMES, STANLEY MARTIN HOMES)."""
    own = set(tokens(core))
    return any(len(t) > 1 and t in generic and t not in NAME_JOINS and t not in own for t in tokens(clean))


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


def added_words(name: str, bases: set[str]) -> list[str]:
    """The words a name adds after one of the sub's names (PORTLAND in DR HORTON PORTLAND, after DR HORTON); []
    when it doesn't start with one."""
    return next((name[len(b):].split() for b in bases if b and name.startswith(b + " ")), [])


def without_suffix(core: str, suffix: str | None, generic: frozenset[str]) -> str:
    """The core without its sibling suffix's place or project words (HOFFMAN OREGON + " OF OREGON" -> HOFFMAN):
    OF and AT are generic, but the place word stays in the core."""
    words = [t for t in tokens(suffix) if t not in generic]
    ct = tokens(core)
    if words and len(ct) > len(words) and ct[-len(words):] == words:
        return " ".join(ct[:-len(words)])
    return core


# M3 guard (run.match): in the M3 audit (eval/m3_audit/review.md) the wrong cross-state matches were small firms whose
# names collide, mostly "<word> CONSTRUCTION" or "<word> ELECTRIC" under a trade code the sub's own records don't
# have: 10 of 21 wrong matches looked like that, against 1 of 35 right ones.
COLLIDING_TRADE_WORDS = ("CONSTRUCTION", "ELECTRIC")


def m3_collides(clean_name: str, naics4: str | None, sub_naics: set[str]) -> bool:
    """A same-name record in another state that M3 shouldn't match outright: a two-word "<word> CONSTRUCTION|ELECTRIC"
    name, and a trade code none of the sub's in-state matched records have (both codes known)."""
    words = (clean_name or "").split()
    return (len(words) == 2 and words[1] in COLLIDING_TRADE_WORDS and bool(naics4) and bool(sub_naics)
            and naics4 not in sub_naics)


def decide(q: Query, c: Candidate, generic: frozenset[str], descriptors: frozenset[str] | None = None) -> Decision:
    if c.clean_name != q.clean and c.clean_name in q.aliases and c.clean_name in q.alias_queries:
        # the record carries one of the sub's other names: judge it as that name. "QORVANEX HOLDINGS DBA QUALITY
        # ROOFING" is distinctive, but a record named QUALITY ROOFING in another state is another company
        q = q.alias_queries[c.clean_name]
    same_full = c.clean_name == q.clean or c.clean_name in q.aliases or q.clean in {c.legal_name, c.dba_name}
    core_equal = bool(q.core) and c.name_core == q.core
    same_state = bool(q.state) and c.state == q.state
    same_city = bool(q.city) and bool(c.city) and norm_city(c.city) == norm_city(q.city)
    distinctive = q.tier == "distinctive"
    generic_diff = core_equal and only_generic_difference(c.clean_name, q.clean, generic)
    descriptor_diff = core_equal and only_descriptor_difference(c.clean_name, q.clean, descriptors)
    conflict = trade_conflict(q.trade, c.primary_naics4)

    # S1: "… OF OREGON" vs "… OF AMERICA", "… AT ELAN" vs "… AT MERIDIAN": usually sibling companies. The cores
    # are compared without the suffix (HOFFMAN, not HOFFMAN OREGON); a common name or a person's only in the
    # same state, as with the same name in another state (X4, X5)
    if (q.sibling or c.sibling_suffix) and q.sibling != c.sibling_suffix:
        qb, cb = without_suffix(q.core, q.sibling, generic), without_suffix(c.name_core, c.sibling_suffix, generic)
        if core_equal or same_full or typo_equal(q.core, c.name_core) or (
                typo_equal(qb, cb) and (q.tier in ("distinctive", "medium") or same_state)):
            return Decision(UNCERTAIN, "S1", "Names differ only by a location/project suffix, which usually means a sibling company")

    # S2: the sub's full name plus a branch/division suffix: likely the same company, never "different"
    rest = added_words(c.clean_name, {q.clean, *q.aliases})
    if rest and BRANCH_WORDS & set(rest):
        return Decision(UNCERTAIN, "S2", "Looks like a branch or division of the same company (" + " ".join(rest[:4]) + ")")

    def matched(rule: str, reason: str) -> Decision:
        if conflict:
            return Decision(UNCERTAIN, rule + "_trade", reason + ", but OSHA lists a different trade")
        if c.related_only and not c.at_matched_address:
            # N1: a plant/yard/shop not coded as construction, linked by name only: confirm before counting
            return Decision(UNCERTAIN, "N1", reason + ", but this facility isn't coded as construction")
        return Decision(MATCHED, rule, reason)

    if same_full and same_state and (distinctive or same_city):
        return matched("M1", "Same name in the same state" + ("" if distinctive else " and city"))
    if descriptor_diff and same_state and distinctive:
        return matched("M1b", "Same distinctive name, differing only by words like GENERAL or CONTRACTORS, in the same state")
    if c.at_matched_address and (same_full or descriptor_diff or jw(q.clean, c.clean_name) >= 0.93
                                 or (typo_equal(q.core, c.name_core) and only_generic_difference(c.clean_name, q.clean, generic)
                                     and not core_equal)):
        # the address ties the record to the company, but a similar name isn't always the same company or person
        if is_jv_name(q.clean) != c.is_jv:
            return Decision(UNCERTAIN, "J1", "A joint venture at an address this company uses; a JV is its own company")
        if not (same_full or descriptor_diff):
            if swap := trade_swap(q.clean, c.clean_name, generic,
                                   descriptors if descriptors is not None else DESCRIPTORS):
                return Decision(UNCERTAIN, "U3", "Same address as a matched record but a different trade ("
                                + ", ".join(swap[:4]) + "); often a sister company")
            from ssi.matching.candidates import given_names, is_person_core
            if (q.tier == "person" or is_person_core(c.name_core)) and different_people(q.clean, c.clean_name, given_names()):
                return Decision(UNCERTAIN, "P2", "Same address as a matched record but another person's name "
                                f"({c.clean_name.title()}): a relative, or the same person?")
        return matched("M2", "Same address as a matched record; name differs only by spelling")
    # S3: the sub's name plus a real word, at an address the sub uses. D R HORTON INC PORTLAND (17 inspections at
    # D.R. Horton's head office) scored 0.88 against DR HORTON, short of M2's 0.93, and X1 excluded it as another
    # company. The address says it's this company or a sister: a question, never "different"
    added = [t for t in rest or added_words(c.name_core, {q.core}) if t not in generic]
    if c.at_matched_address and added:
        if is_jv_name(q.clean) != c.is_jv:
            return Decision(UNCERTAIN, "J1", "A joint venture at an address this company uses; a JV is its own company")
        return Decision(UNCERTAIN, "S3", "Same address as a matched record, under the sub's name plus "
                        + " ".join(added[:4]) + ": a division or a sister company")
    # P1 / X5: a person's name (a sole proprietor) is usually many different people; only a place ties it
    if q.tier == "person" and (same_full or core_equal):
        other_state = bool(q.state and c.state and not same_state)
        if ((other_state or (q.city and c.city and not same_city)) and (same_full or descriptor_diff)
                and ((named_company(q.clean, q.core, generic) and named_company(c.clean_name, c.name_core, generic))
                     or (q.incorporated and c.incorporated))):
            # P3: the same company name built on a person's, with a trade or company word (DAVID E HARVEY BUILDERS in
            # Bethesda and in Houston) or a legal form on both sides (ROBERT J DEVEREAUX CORP in Boston and Malden),
            # is usually the company's other office: X5 excluded the sub's own records in all 24 labelled cases in the
            # rules eval. Unsure, not matched: a few such names are several people's (JOSE GARCIA CONSTRUCTION)
            where = f"another state ({c.state})" if other_state else f"another city ({c.city.title()})"
            return Decision(UNCERTAIN, "P3", f"A company named after a person, in {where}: "
                                             "maybe its other office, maybe another person's business")
        if q.state and c.state and not same_state:
            return Decision(EXCLUDED, "X5", f"A person's name in another state ({c.state}): usually a different person")
        if q.city and c.city and not same_city:
            if jw(norm_city(q.city), norm_city(c.city)) >= 0.9:  # "heuston": maybe a typo, maybe a nearby town
                return Decision(UNCERTAIN, "P1", f"A person's name; the city is spelled differently ({c.city.title()})")
            return Decision(EXCLUDED, "X5", f"A person's name in a different city ({c.city.title()}): usually a different person")
        return Decision(UNCERTAIN, "P1", "A person's name: a city or address is needed to tell people apart")
    if (same_full or descriptor_diff) and not same_state and distinctive:
        return matched("M3", f"Same distinctive name, another state ({c.state or 'unknown'})")
    if generic_diff and not descriptor_diff and distinctive:
        return Decision(UNCERTAIN, "U3", "Same family name but a different trade; often a sister company")
    if q.core and c.name_core and not core_equal and not typo_equal(q.core, c.name_core):
        # do the cores differ on a real (non-generic) word that has no near-spelling on the other side?
        qa, ca = set(tokens(q.core)), set(tokens(c.name_core))
        unmatched = [t for t in qa ^ ca if t not in generic and not any(near_spelling(t, u) for u in (ca if t in qa else qa))]
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
