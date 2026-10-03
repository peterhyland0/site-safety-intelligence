"""Map a GC's free-text trade ("roofing", "electrician", "238160") to NAICS 4-digit trade groups."""
from __future__ import annotations

import re

TRADE_KEYWORDS: list[tuple[str, set[str]]] = [
    (r"roof|framing|frame|concrete|foundation|mason|brick|block|steel|structural|iron|glass|glazing|siding|gutter|exterior|curtain wall", {"2381"}),
    (r"electric|plumb|hvac|mechanical|heating|air cond|sprinkler|fire protection|elevator|low voltage|solar", {"2382"}),
    (r"drywall|insulat|plaster|stucco|paint|floor|tile|terrazzo|carpent|finish|millwork|acoustic|ceiling", {"2383"}),
    (r"excavat|site ?work|sitework|grading|earth|demoli|wrecking|landscap|paving|asphalt|drilling|boring", {"2389", "2373"}),
    (r"general contractor|\bgc\b|builder|construction manager|design.?build", {"2362", "2361"}),
    (r"road|highway|bridge|utility|pipeline|sewer|water line|underground|civil", {"2371", "2373", "2379"}),
]

NAICS4_LABELS = {
    "2361": "Residential building construction",
    "2362": "Nonresidential building construction",
    "2371": "Utility system construction",
    "2372": "Land subdivision",
    "2373": "Highway, street and bridge construction",
    "2379": "Other heavy and civil engineering",
    "2381": "Foundation, structure and exterior contractors",
    "2382": "Building equipment contractors",
    "2383": "Building finishing contractors",
    "2389": "Other specialty trade contractors",
}


def trade_naics4(trade: str | None) -> set[str]:
    if not trade:
        return set()
    t = trade.strip().lower()
    if re.fullmatch(r"\d{4,6}", t):
        return {t[:4]}
    out: set[str] = set()
    for pattern, codes in TRADE_KEYWORDS:
        if re.search(pattern, t):
            out |= codes
    return out


def trade_conflict(trade: str | None, naics4: str | None) -> bool:
    """True only when both sides are specialty trades (238x) and they differ, e.g. GC says electrician,
    OSHA's most common code says roofer. Industry codes drift, so anything vaguer is not a conflict."""
    want = trade_naics4(trade)
    if not want or not naics4 or not naics4.startswith("238"):
        return False
    if not all(w.startswith("238") for w in want):
        return False
    return naics4 not in want
