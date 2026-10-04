"""Candidate search in the warehouse (DuckDB has no trigram index, so: exact alias, same core, and
token blocking on the query's rarest words, typo-tolerant via Jaro-Winkler on the token vocabulary)."""
from __future__ import annotations

import csv
import re
from functools import cache

from ssi import config
from ssi.store import warehouse

EST_COLS = """e.establishment_key, e.clean_name, e.name_core, e.legal_name, e.dba_name, e.display_name,
              e.name_variants, e.address, e.city, e.state, e.zip5, e.addr_key, e.primary_naics4, e.primary_sic4,
              e.first_seen::VARCHAR AS first_seen, e.last_seen::VARCHAR AS last_seen, e.insp_n, e.insp_conducted_n,
              e.sibling_suffix,
              e.is_jv, initials_only(e.clean_name) AS initials_only, coalesce(e.related_only, false) AS related_only"""

MAX_CANDIDATES = 400


def describe_query(name: str) -> dict:
    # clean_name once: each call is a large expression to bind (7 calls took 160 ms, one takes 10)
    return warehouse.one(
        """SELECT clean, name_core(clean) AS core, initials_only(clean) AS initials_only, sibling_suffix(clean) AS sibling,
                  legal_part(clean) AS legal, dba_part(clean) AS dba, is_placeholder(clean) AS placeholder
           FROM (SELECT clean_name(?) AS clean)""",
        [name],
    )


def describe_clean(clean: str) -> dict:
    """describe_query for a name that is already clean (one of the sub's aliases)."""
    return warehouse.one("SELECT name_core(?) AS core, initials_only(?) AS initials_only, sibling_suffix(?) AS sibling",
                         [clean] * 3)


def _ref_names(file: str) -> frozenset[str]:
    path = config.REF_DIR / file
    if not path.exists():
        return frozenset()
    with path.open() as f:
        return frozenset(r["name"].strip().upper() for r in csv.DictReader(f) if r["name"].strip())


@cache
def given_names() -> frozenset[str]:
    return _ref_names("given_name.csv")


@cache
def surnames() -> frozenset[str]:
    return _ref_names("surname.csv")


# First words of place names: SAN ANTONIO, ST GEORGE and FORT WAYNE end in a given name but are companies' names.
# The same list as the ssi_place_prefixes() macro.
PLACE_PREFIXES = frozenset({"SAN", "SANTA", "SANTO", "ST", "SAINT", "FORT", "FT", "MOUNT", "MT", "PORT", "LOS", "LAS",
                            "LAKE", "CAPE"})


def is_person_core(core: str) -> bool:
    """A name core that is a person's name: "JUAN GARCIA", "JOSE A HERNANDEZ" (core JOSE HERNANDEZ), "HERNANDEZ JOSE",
    "MORALES JAVIER M", "J LOPEZ". Sole proprietors appear in OSHA's data under the owner's name, and the same name
    is usually many different people. Mirrors the is_person_name macro (entity.core_stats.is_person)."""
    t = core.split()
    if not 2 <= len(t) <= 4 or not re.fullmatch(r"[A-Z]+( [A-Z]+)*", core):
        return False
    g = given_names()
    if t[0] in g:
        return True
    if t[0] not in PLACE_PREFIXES and t[1] in g and (len(t) == 2 or (len(t) == 3 and len(t[2]) == 1)):
        return True
    return len(t) == 2 and len(t[0]) == 1 and t[1] in surnames()


def core_tier(core: str, initials: bool) -> str:
    if not core or initials:
        return "generic"
    if is_person_core(core):
        return "person"
    r = warehouse.one("SELECT tier FROM entity.core_stats WHERE name_core = ?", [core])
    return r["tier"] if r else "distinctive"  # a core never seen in OSHA data is, by definition, rare


def generic_tokens() -> frozenset[str]:
    return frozenset(warehouse.one("SELECT ssi_generic_tokens() AS t")["t"])


def descriptor_tokens() -> frozenset[str]:
    try:
        return frozenset(warehouse.one("SELECT ssi_descriptor_tokens() AS t")["t"])
    except Exception:  # warehouse built before descriptor words existed
        from ssi.cleaning import install_macros
        return frozenset({"GENERAL", "CONTRACTOR", "CONTRACTORS", "CONTRACTING", "CONSTRUCTION", "SERVICES", "GROUP"})


def search(clean: str, core: str, state: str | None, aliases: list[str]) -> list[dict]:
    """Candidate establishments for a cleaned query name."""
    return warehouse.rows(
        f"""
        WITH qt AS (SELECT unnest(string_split(?, ' ')) AS qtok),
        qtok AS (SELECT qtok FROM qt WHERE length(qtok) >= 2 AND NOT list_contains(ssi_generic_tokens(), qtok)),
        -- typo-tolerant token variants, then keep the two rarest query words
        variants AS (
          SELECT q.qtok, t.token, t.df
          FROM qtok q JOIN entity.token_df t
            ON left(t.token, 1) = left(q.qtok, 1) AND jaro_winkler_similarity(t.token, q.qtok) >= 0.92
        ),
        rarest AS (
          SELECT qtok FROM variants GROUP BY qtok ORDER BY sum(df) ASC LIMIT 2
        ),
        blocked AS (
          SELECT DISTINCT nt.establishment_key
          FROM entity.name_token nt JOIN variants v ON v.token = nt.token
          WHERE v.qtok IN (SELECT qtok FROM rarest)
        ),
        hits AS (
          SELECT establishment_key, 'alias' AS src FROM entity.establishment_alias WHERE list_contains(?::VARCHAR[], alias)
          UNION ALL
          SELECT establishment_key, 'core' FROM entity.establishment WHERE ? <> '' AND name_core = ?
          UNION ALL
          SELECT establishment_key, 'token' FROM blocked
        )
        , agg AS (SELECT establishment_key, list(DISTINCT src) AS srcs FROM hits GROUP BY 1)
        SELECT {EST_COLS},
               jaro_winkler_similarity(e.clean_name, ?) AS sim,
               a.srcs
        FROM agg a JOIN entity.establishment e USING (establishment_key)
        WHERE NOT e.is_placeholder
          AND (list_contains(a.srcs, 'alias') OR list_contains(a.srcs, 'core')
               OR jaro_winkler_similarity(e.clean_name, ?) >= 0.80)
        ORDER BY (e.state IS NOT DISTINCT FROM ?) DESC, sim DESC, e.insp_n DESC
        LIMIT {MAX_CANDIDATES}
        """,
        [clean, aliases, core, core, clean, clean, state],
    )


# The suite/unit at the end of an address ("4450 OLD CANTON RD STE 208" -> "208"); '' when there is none
_UNIT_RE = r"\b(STE|SUITE|UNIT|APT|FL|FLOOR|RM|ROOM|BLDG|#)\s*#?\s*([A-Z0-9-]+)\s*$"


def _unit_sql(col: str) -> str:
    return f"regexp_extract(upper(coalesce({col}, '')), '{_UNIT_RE}', 2)"


def _at(m_sql: str, params: list, limit: int, order: str = "") -> list[dict]:
    """Establishments at the addresses in CTE m (addr_key, zip3, unit): the same building and zip3 (tolerates zip
    typos), the same suite or a suite on one side only, never placeholders, never shared offices."""
    return warehouse.rows(
        f"""
        WITH m AS ({m_sql})
        SELECT {EST_COLS}, NULL::DOUBLE AS sim, ['address'] AS srcs
        FROM entity.establishment e JOIN m ON e.addr_key = m.addr_key AND left(e.zip5, 3) = m.zip3
        LEFT JOIN entity.address_stats s ON s.addr_key = e.addr_key AND s.zip5 = e.zip5
        WHERE NOT e.is_placeholder AND NOT coalesce(s.is_shared_office, false)
          AND (m.unit = '' OR {_unit_sql('e.address')} IN ('', m.unit))  -- same suite, or a suite on one side only
        QUALIFY row_number() OVER (PARTITION BY e.establishment_key) = 1
        {order}
        LIMIT {int(limit)}
        """,
        params,
    )


def at_addresses(keys: list[str], exclude: set[str]) -> list[dict]:
    """Other establishments at the addresses of matched ones (address key + zip3 tolerates zip typos),
    skipping shared offices, which must never pull records into a match. The address key is the building
    (house number + street), so different suites are different tenants: Brasfield & Gorrie's Jackson office
    (Ste 208) and Neel-Schaffer (Ste 100) are not "the same address"."""
    if not keys:
        return []
    found = _at(f"""SELECT DISTINCT addr_key, left(zip5, 3) AS zip3, {_unit_sql('address')} AS unit FROM entity.establishment
                    WHERE establishment_key IN (SELECT unnest(?::VARCHAR[])) AND addr_key IS NOT NULL AND zip5 IS NOT NULL""",
                [keys], 500)
    return [r for r in found if r["establishment_key"] not in exclude]


def at_listed_addresses(addresses: list[dict], exclude: set[str], limit: int = 20) -> list[dict]:
    """Establishments, under any name, at addresses a company profile lists ({address, addr_key, zip}), by the
    same rules as at_addresses; the most inspected first, capped. Locations without a street or zip are skipped."""
    rows = [(a["addr_key"], a["zip"][:3], m.group(2) if (m := re.search(_UNIT_RE, (a.get("address") or "").upper())) else "")
            for a in addresses if a.get("addr_key") and a.get("zip")]
    if not rows:
        return []
    keys, zips, units = (list(x) for x in zip(*rows))
    found = _at("SELECT unnest(?::VARCHAR[]) AS addr_key, unnest(?::VARCHAR[]) AS zip3, unnest(?::VARCHAR[]) AS unit",
                [keys, zips, units], limit + len(exclude), order="ORDER BY e.insp_n DESC, e.establishment_key")
    return [r for r in found if r["establishment_key"] not in exclude][:limit]


def red_flag_counts(keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    rs = warehouse.rows(
        "SELECT establishment_key, count(*) AS n FROM mart.red_flag WHERE establishment_key IN (SELECT unnest(?::VARCHAR[])) GROUP BY 1",
        [keys],
    )
    return {r["establishment_key"]: r["n"] for r in rs}


def members(keys: list[str]) -> dict[str, list[int]]:
    """{establishment_key: its inspections' activity numbers}. OSHA's activity numbers never change, so a decision
    stored with them can find its record again after a cleaning change gives the record a new key (remap.py)."""
    if not keys:
        return {}
    rs = warehouse.rows("""SELECT establishment_key, list(activity_nr ORDER BY activity_nr) AS nrs
                           FROM entity.establishment_member WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))
                           GROUP BY 1""", [keys])
    return {r["establishment_key"]: list(r["nrs"]) for r in rs}


def establishments(keys: list[str]) -> list[dict]:
    if not keys:
        return []
    return warehouse.rows(f"""SELECT {EST_COLS}, NULL::DOUBLE AS sim, ['licence'] AS srcs FROM entity.establishment e
                             WHERE e.establishment_key IN (SELECT unnest(?::VARCHAR[]))""", [keys])
