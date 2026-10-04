"""Pick the LLM provider per role from env vars, and enforce a daily token budget.

Two roles, each with its own model:
  foreman      - plain-English Q&A with tool calls (multi-step; benefits from a strong agentic model)
  adjudicator  - short same/different/unsure judgements on uncertain matches (many calls; a fast model)

For an OpenAI-compatible endpoint (e.g. models served on Modal):
  SSI_LLM_PROVIDER=openai_compat
  SSI_LLM_FOREMAN_BASE_URL / SSI_LLM_FOREMAN_MODEL
  SSI_LLM_ADJUDICATOR_BASE_URL / SSI_LLM_ADJUDICATOR_MODEL
  SSI_LLM_FOREMAN_REASONING_EFFORT / SSI_LLM_ADJUDICATOR_REASONING_EFFORT = low|high|max, passed to the chat
  template (the foreman defaults to low for latency, the adjudicator to the server's default)
  (SSI_LLM_BASE_URL / SSI_LLM_MODEL / SSI_LLM_REASONING_EFFORT are the fallback for either role; a blank model =
  the one the endpoint serves)
  SSI_LLM_MODAL_KEY / SSI_LLM_MODAL_SECRET for Modal proxy auth (shared by both endpoints)
For Claude: ANTHROPIC_API_KEY (+ SSI_MODEL)."""
from __future__ import annotations

import os
from datetime import UTC, datetime

from ssi import config
from ssi.llm.base import Provider

ROLES = ("foreman", "adjudicator")
REASONING_EFFORT_DEFAULT = {"foreman": "low", "adjudicator": None}  # None = whatever the server does
_providers: dict[str, Provider] = {}


def provider_name() -> str:
    return os.environ.get("SSI_LLM_PROVIDER", "anthropic")


def _role_env(role: str, name: str) -> str | None:
    return os.environ.get(f"SSI_LLM_{role.upper()}_{name}") or os.environ.get(f"SSI_LLM_{name}") or None


def reasoning_effort(role: str) -> str | None:
    return (_role_env(role, "REASONING_EFFORT") or "").strip().lower() or REASONING_EFFORT_DEFAULT[role]


def available(role: str = "foreman") -> bool:
    if provider_name() == "openai_compat":
        url = _role_env(role, "BASE_URL")
        if not url:
            return False
        if "modal" in url:
            return bool(os.environ.get("SSI_LLM_MODAL_KEY") and os.environ.get("SSI_LLM_MODAL_SECRET"))
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def get(role: str = "foreman") -> Provider:
    if role not in _providers:
        if provider_name() == "openai_compat":
            from ssi.llm.openai_compat_provider import OpenAICompatProvider
            _providers[role] = OpenAICompatProvider(_role_env(role, "MODEL"), _role_env(role, "BASE_URL"),
                                                    reasoning_effort=reasoning_effort(role))
        else:
            from ssi.llm.anthropic_provider import AnthropicProvider
            _providers[role] = AnthropicProvider(config.MODEL, effort=os.environ.get("SSI_LLM_EFFORT", "low"))
    return _providers[role]


def model_label(role: str = "foreman") -> str:
    return f"{provider_name()}:{get(role).model}" if available(role) else "none"


def budget_ok(share: float = 1.0) -> bool:
    """Whether today's tokens are under `share` of the daily budget (the foreman's is config.FOREMAN_BUDGET_SHARE)."""
    from ssi.store import pg
    with pg.conn() as c:
        r = c.execute("SELECT input_tokens + output_tokens AS t FROM app.llm_usage_daily WHERE day = %s",
                      [datetime.now(UTC).date()]).fetchone()
    return (r["t"] if r else 0) < config.DAILY_TOKEN_BUDGET * share


def record_usage(input_tokens: int, output_tokens: int) -> None:
    from ssi.store import pg
    with pg.conn() as c:
        c.execute("""INSERT INTO app.llm_usage_daily (day, input_tokens, output_tokens) VALUES (%s, %s, %s)
                     ON CONFLICT (day) DO UPDATE SET input_tokens = app.llm_usage_daily.input_tokens + EXCLUDED.input_tokens,
                                                    output_tokens = app.llm_usage_daily.output_tokens + EXCLUDED.output_tokens""",
                  [datetime.now(UTC).date(), input_tokens, output_tokens])
