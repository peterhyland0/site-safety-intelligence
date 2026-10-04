"""Grounding check: every figure, date and inspection ID in an answer must come from the tool results
(or the question). Numbers are quoted, never computed, so this check is exact. A date is checked whole (a date's day
isn't a figure: "14 willful violations" doesn't pass on 2023-05-14, nor "December 14, 2023"), a percentage needs a
percentage or a share in the results (not a count), numbers written as words are checked too, and what the model
wrote into a tool call and got back (report_unanswerable's reason, lookup_company's query) grounds nothing."""
from __future__ import annotations

import json
import re

NUM_RE = re.compile(r"(?<![\w#])\$?\d[\d,]*(?:\.\d+)?%?")
ID_RE = re.compile(r"\b\d{6,10}\b")
# Inspection IDs as the prompt asks the model to write them: (#1234567). NUM_RE skips these; they are checked
# whole against the IDs the tools returned, so an invented or truncated ID can't pass or become a chip.
HASH_ID_RE = re.compile(r"#\s?(\d+)")
ID_KEYS = {"inspection_id", "inspection_ids", "activity_nr"}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
PERCENTILE_KEY_RE = re.compile(r"(?:^|_)p(\d{2})$")  # trade_p75: "the trade's 75th percentile" quotes the field


def _norm(tok: str) -> str:
    return tok.replace("$", "").replace(",", "").replace("%", "").rstrip(".")


# Figures the instructions themselves use ("OSHA 300 logs", TRIR per 200,000 hours / 100 workers).
CONSTANTS = {"100", "200000", "300", "300A"}
DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
ECHO_KEYS = {"reason", "query"}  # tool results that repeat the model's own arguments back

MONTHS = {m: i for i, ms in enumerate([("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
                                        ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
                                        ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
                                        ("december", "dec")], 1) for m in ms}
_MON = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul" \
       r"|aug|sept|sep|oct|nov|dec)\.?"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
# a date as an answer writes it -> (year, month, day or None)
WRITTEN_DATES = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), lambda g: (int(g[0]), int(g[1]), int(g[2]))),
    (re.compile(rf"\b{_MON}\s+{_DAY},?\s+(\d{{4}})\b", re.IGNORECASE), lambda g: (int(g[2]), MONTHS[g[0].lower()], int(g[1]))),
    (re.compile(rf"\b{_DAY}\s+{_MON},?\s+(\d{{4}})\b", re.IGNORECASE), lambda g: (int(g[2]), MONTHS[g[1].lower()], int(g[0]))),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), lambda g: (int(g[2]), int(g[0]), int(g[1]))),
    (re.compile(rf"\b{_MON},?\s+(\d{{4}})\b", re.IGNORECASE), lambda g: (int(g[1]), MONTHS[g[0].lower()], None)),
]
WORDS = {"zero": 0, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90, "dozen": 12}
ONES = {"one": 1, **{w: n for w, n in WORDS.items() if 2 <= n <= 9}}
# "one" alone is left out: "one of the subs" isn't a figure
WORD_RE = re.compile(r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")(?:[- ](" + "|".join(ONES) + r"))?\b",
                     re.IGNORECASE)
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")


def _word_numbers(text: str) -> list[tuple[str, int]]:
    """Numbers written as words: ("twenty-three", 23)."""
    out = []
    for m in WORD_RE.finditer(text):
        n = WORDS[m.group(1).lower()] + (ONES[m.group(2).lower()] if m.group(2) and WORDS[m.group(1).lower()] >= 20 else 0)
        out.append((m.group(0), n))
    return out


def _list_lengths(obj, out: set[str]) -> None:
    """Counting the rows a tool returned is quoting, not computing: allow every list length."""
    if isinstance(obj, dict):
        for v in obj.values():
            _list_lengths(v, out)
    elif isinstance(obj, list):
        out.add(str(len(obj)))
        for v in obj:
            _list_lengths(v, out)


def _values_text(obj, out: list[str]) -> None:
    """The tool outputs' values as text. Not dict keys ("naics4" doesn't make 4 a figure) except a percentile's
    name, or ids (a sub_id's UUID digits would allow almost any small number)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ECHO_KEYS:
                continue
            if isinstance(k, str) and (m := PERCENTILE_KEY_RE.search(k)):
                out.append(m.group(1))
            _values_text(v, out)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _values_text(v, out)
    elif isinstance(obj, str):
        out.append(UUID_RE.sub(" ", obj))
    elif obj is not None:
        out.append(json.dumps(obj, default=str))


def known_ids(tool_outputs: list) -> set[str]:
    """Every inspection ID the tools returned, exactly."""
    out: set[str] = set()

    def walk(obj, key=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, k)
        elif isinstance(obj, list | tuple):
            for v in obj:
                walk(v, key)
        elif key in ID_KEYS and isinstance(obj, int | str) and str(obj).isdigit():
            out.add(str(int(obj)))

    walk(tool_outputs)
    return out


def _blob(tool_outputs: list, extra_text: str = "") -> str:
    texts: list[str] = []
    _values_text(tool_outputs, texts)
    return " ".join(texts) + " " + extra_text


def known_dates(tool_outputs: list, extra_text: str = "") -> set[tuple]:
    """Every date in the tool outputs, as (year, month, day) and (year, month, None)."""
    out: set[tuple] = set()
    for y, m, d in DATE_RE.findall(_blob(tool_outputs, extra_text)):
        out |= {(int(y), int(m), int(d)), (int(y), int(m), None)}
    return out


def allowed_numbers(tool_outputs: list, extra_text: str = "") -> set[str]:
    """Every number that appears anywhere in the tool outputs, plus common renderings of it. A date gives its year
    only: its month and day aren't figures (dates are checked whole, known_dates)."""
    blob = DATE_RE.sub(lambda m: m.group(1), _blob(tool_outputs, extra_text))
    out: set[str] = set(CONSTANTS)
    for raw in re.findall(r"\d+(?:\.\d+)?", blob):  # unsigned: a leading "-" is punctuation, not a sign
        n = _norm(raw)
        out.add(n)
        f = float(n)
        out.add(str(int(f)) if f == int(f) else n)
        for d in (0, 1, 2):  # rounded renderings of decimals
            out.add(f"{f:.{d}f}")
    out |= {str(n) for _, n in _word_numbers(blob)}  # "the Fatal Four"
    _list_lengths(tool_outputs, out)
    return out


def allowed_percentages(tool_outputs: list, extra_text: str = "") -> set[str]:
    """Figures an answer may write with a %: percentages in the outputs, and shares (0-1) as percentages."""
    blob = DATE_RE.sub(" ", _blob(tool_outputs, extra_text))
    out = {_norm(x) for x in PCT_RE.findall(blob)}
    out |= {str(int(float(x))) for x in out if float(x) == int(float(x))}
    for raw in re.findall(r"\d+(?:\.\d+)?", blob):
        f = float(raw)
        if 0 < f <= 1:
            out |= {f"{f * 100:.0f}", f"{f * 100:.1f}"}
    return out


def check(answer: str, tool_outputs: list, question: str = "") -> list[str]:
    """Return the ungrounded number tokens in the answer (empty list = grounded)."""
    allowed = allowed_numbers(tool_outputs, question)
    # an ID the question or an earlier turn names counts, as numbers there do; a chip still needs a tool result.
    # Inspection IDs have 6+ digits; a shorter "#1" ("the #1 hazard") is checked like any other number.
    ids = known_ids(tool_outputs) | {str(int(x)) for x in re.findall(r"\d+", question)}
    bad = [f"#{x}" for x in dict.fromkeys(HASH_ID_RE.findall(answer))
           if str(int(x)) not in (ids if len(x) >= 6 else allowed)]
    # dates whole, then blanked out so their parts aren't read as figures
    dates = known_dates(tool_outputs, question)
    rest = answer
    for rx, ymd in WRITTEN_DATES:
        for m in rx.finditer(rest):
            try:
                ok = ymd(m.groups()) in dates
            except (KeyError, ValueError):
                ok = False
            if not ok:
                bad.append(m.group(0))
        rest = rx.sub(lambda m: " " * len(m.group(0)), rest)
    pct = allowed_percentages(tool_outputs, question)
    for tok in NUM_RE.findall(rest):
        n = _norm(tok)
        if not n:
            continue
        if tok.endswith("%"):  # a share, not a count: "42% of inspections" doesn't pass on 42 inspections
            if n not in pct and not (float(n) == int(float(n)) and str(int(float(n))) in pct):
                bad.append(tok)
            continue
        if n in allowed:
            continue
        try:
            f = float(n)
            if f == int(f) and str(int(f)) in allowed:
                continue
        except ValueError:
            pass
        bad.append(tok)
    bad += [w for w, n in _word_numbers(rest) if str(n) not in allowed]
    return bad


def cited_ids(answer: str, tool_outputs: list) -> list[int]:
    """Inspection IDs in the answer that a tool returned (exact match: 3485576 is not 348557646)."""
    ids = known_ids(tool_outputs)
    return [int(x) for x in dict.fromkeys(ID_RE.findall(answer)) if str(int(x)) in ids]
