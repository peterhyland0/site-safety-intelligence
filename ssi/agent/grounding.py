"""Grounding check: every figure, date and inspection ID in an answer must come from the tool results
(or the question). Numbers are quoted, never computed, so this check is exact."""
from __future__ import annotations

import json
import re

NUM_RE = re.compile(r"(?<![\w#])\$?\d[\d,]*(?:\.\d+)?%?")
ID_RE = re.compile(r"\b\d{6,10}\b")


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


def allowed_numbers(tool_outputs: list, extra_text: str = "") -> set[str]:
    """Every number that appears anywhere in the tool outputs, plus common renderings of it."""
    blob = json.dumps(tool_outputs, default=str, ensure_ascii=False) + " " + extra_text
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
    bad = []
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
    blob = json.dumps(tool_outputs, default=str, ensure_ascii=False)
    return [int(x) for x in dict.fromkeys(ID_RE.findall(answer)) if x in blob]
