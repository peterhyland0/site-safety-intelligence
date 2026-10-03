"""Provider-neutral interface used by the adjudicator and the foreman. Each provider lives in its own
module (anthropic_provider.py for Claude, openai_compat_provider.py for an OpenAI-compatible endpoint
such as a self-hosted GLM on Modal)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall]
    assistant_message: Any          # provider-native message to append to the conversation
    stop_reason: str                # 'end_turn' | 'tool_use' | 'refusal' | 'max_tokens' | ...
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict                # JSON schema (object, additionalProperties false)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    extra: dict = field(default_factory=dict)


class Provider(Protocol):
    name: str
    model: str

    def structured(self, system: str, user: str, schema: dict, max_tokens: int = 1024) -> tuple[dict | None, Usage]:
        """One call returning JSON matching `schema` (None on refusal/failure)."""

    def chat(self, system: str, messages: list, tools: list[ToolSpec], max_tokens: int = 4000) -> Reply:
        """One model turn with tools available (tool_choice auto)."""

    def user_message(self, text: str) -> Any:
        """Provider-native user message."""

    def tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> list:
        """Provider-native message(s) carrying tool results (call, json_text, is_error)."""
