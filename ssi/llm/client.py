"""Pick the LLM provider from env vars and enforce a daily token budget."""
from __future__ import annotations

import os
from datetime import date

from ssi import config
from ssi.llm.base import Provider

_provider: Provider | None = None


def provider_name() -> str:
    return os.environ.get("SSI_LLM_PROVIDER", "anthropic")


def available() -> bool:
    if provider_name() == "openai_compat":
        return bool(os.environ.get("SSI_LLM_BASE_URL"))
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def get() -> Provider:
    global _provider
    if _provider is None:
        if provider_name() == "openai_compat":
            from ssi.llm.openai_compat_provider import OpenAICompatProvider
            _provider = OpenAICompatProvider(os.environ.get("SSI_LLM_MODEL", "glm-5.3"), os.environ["SSI_LLM_BASE_URL"])
        else:
            from ssi.llm.anthropic_provider import AnthropicProvider
            _provider = AnthropicProvider(config.MODEL, effort=os.environ.get("SSI_LLM_EFFORT", "low"))
    return _provider


def model_label() -> str:
    return f"{provider_name()}:{get().model}" if available() else "none"


def budget_ok() -> bool:
    from ssi.store import pg
    with pg.conn() as c:
        r = c.execute("SELECT input_tokens + output_tokens AS t FROM app.llm_usage_daily WHERE day = %s",
                      [date.today()]).fetchone()
    return (r["t"] if r else 0) < config.DAILY_TOKEN_BUDGET


def record_usage(input_tokens: int, output_tokens: int) -> None:
    from ssi.store import pg
    with pg.conn() as c:
        c.execute("""INSERT INTO app.llm_usage_daily (day, input_tokens, output_tokens) VALUES (%s, %s, %s)
                     ON CONFLICT (day) DO UPDATE SET input_tokens = app.llm_usage_daily.input_tokens + EXCLUDED.input_tokens,
                                                    output_tokens = app.llm_usage_daily.output_tokens + EXCLUDED.output_tokens""",
                  [date.today(), input_tokens, output_tokens])
