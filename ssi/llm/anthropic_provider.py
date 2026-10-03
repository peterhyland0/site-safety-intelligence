"""Claude via the official Anthropic SDK.

Claude Sonnet 5.5 specifics (per the Claude API reference): thinking is on by default (left unset);
forced tool_choice is rejected, so tools are `strict` with tool_choice auto and the prompt steers; JSON
answers use structured outputs (output_config.format); refusals are checked via stop_reason before
reading content; server-side fallbacks ("default" form) re-run a declined request on another model."""
from __future__ import annotations

import json

import anthropic

from ssi import config
from ssi.llm.base import Reply, ToolCall, ToolSpec, Usage

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, effort: str = "low"):
        self.model = model
        self.effort = effort
        client = anthropic.Anthropic(max_retries=2, timeout=60.0)
        if config.TRACING:
            from langsmith.wrappers import wrap_anthropic
            client = wrap_anthropic(client)
        self.client = client

    def _create(self, **kw):
        return self.client.beta.messages.create(
            model=self.model, betas=[FALLBACK_BETA], fallbacks="default", **kw)

    def structured(self, system: str, user: str, schema: dict, max_tokens: int = 1024) -> tuple[dict | None, Usage]:
        resp = self._create(
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
        )
        usage = Usage(resp.usage.input_tokens, resp.usage.output_tokens, 1)
        if resp.stop_reason == "refusal":
            return None, usage
        text = next((b.text for b in resp.content if b.type == "text"), None)
        try:
            return (json.loads(text) if text else None), usage
        except json.JSONDecodeError:
            return None, usage

    def chat(self, system: str, messages: list, tools: list[ToolSpec], max_tokens: int = 4000) -> Reply:
        resp = self._create(
            max_tokens=max_tokens,
            system=system,
            tools=[{"name": t.name, "description": t.description, "input_schema": t.parameters, "strict": True}
                   for t in tools],
            tool_choice={"type": "auto"},
            output_config={"effort": self.effort},
            cache_control={"type": "ephemeral"},  # tools + system are stable: cache the prefix
            messages=messages,
        )
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in resp.content if b.type == "tool_use"]
        text = "".join(b.text for b in resp.content if b.type == "text")
        # append the full content (not just text) so tool_use ids and thinking blocks stay intact
        return Reply(text=text, tool_calls=calls, assistant_message={"role": "assistant", "content": resp.content},
                     stop_reason=resp.stop_reason or "end_turn", input_tokens=resp.usage.input_tokens,
                     output_tokens=resp.usage.output_tokens)

    def user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> list:
        # all results for one turn go back in ONE user message (keeps parallel tool use working)
        return [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": call.id, "content": body, **({"is_error": True} if err else {})}
            for call, body, err in results]}]
