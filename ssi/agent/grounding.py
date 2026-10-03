"""Grounding check: every figure, date and inspection ID in an answer must come from the tool results
(or the question). Numbers are quoted, never computed, so this check is exact."""
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


def allowed_numbers(tool_outputs: list, extra_text: str = "") -> set[str]:
    """Every number that appears anywhere in the tool outputs, plus common renderings of it."""
    texts: list[str] = []
    _values_text(tool_outputs, texts)
    blob = " ".join(texts) + " " + extra_text
    out: set[str] = set(CONSTANTS)
    for raw in re.findall(r"\d+(?:\.\d+)?", blob):  # unsigned: the "-11" in "2025-11-13" is a month, not -11
        n = _norm(raw)
        out.add(n)
        f = float(n)
        out.add(str(int(f)) if f == int(f) else n)
        for d in (0, 1, 2):  # rounded renderings of decimals
            out.add(f"{f:.{d}f}")
        if 0 < f <= 1:  # shares quoted as percentages
            out.add(f"{f * 100:.0f}")
            out.add(f"{f * 100:.1f}")
    for y, m, d in DATE_RE.findall(blob):  # "2025-11-03" may be written "November 3, 2025"
        out.update({y, m, d, str(int(m)), str(int(d))})
    _list_lengths(tool_outputs, out)
    return out


def check(answer: str, tool_outputs: list, question: str = "") -> list[str]:
    """Return the ungrounded number tokens in the answer (empty list = grounded)."""
    allowed = allowed_numbers(tool_outputs, question)
    # an ID the question or an earlier turn names counts, as numbers there do; a chip still needs a tool result.
    # Inspection IDs have 6+ digits; a shorter "#1" ("the #1 hazard") is checked like any other number.
    ids = known_ids(tool_outputs) | {str(int(x)) for x in re.findall(r"\d+", question)}
    bad = [f"#{x}" for x in dict.fromkeys(HASH_ID_RE.findall(answer))
           if str(int(x)) not in (ids if len(x) >= 6 else allowed)]
    for tok in NUM_RE.findall(answer):
        n = _norm(tok)
        if not n or n in allowed:
            continue
        try:
            f = float(n)
            if f == int(f) and str(int(f)) in allowed:
                continue
        except ValueError:
            pass
        bad.append(tok)
    return bad


def cited_ids(answer: str, tool_outputs: list) -> list[int]:
    """Inspection IDs in the answer that a tool returned (exact match: 3485576 is not 348557646)."""
    ids = known_ids(tool_outputs)
    return [int(x) for x in dict.fromkeys(ID_RE.findall(answer)) if str(int(x)) in ids]
