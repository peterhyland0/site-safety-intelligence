"""Check that the configured LLM endpoint works for this app: one plain call, one structured-JSON call,
and one tool call (the foreman needs tool calling). Reads the same env vars as the app.

    uv run python -m scripts.check_llm
"""
from __future__ import annotations

from ssi.llm import client as llm
from ssi.llm.base import ToolSpec


def main() -> None:
    for role in llm.ROLES:
        check(role)


def check(role: str) -> None:
    if not llm.available(role):
        raise SystemExit(f"No LLM configured for {role}. See .env.example (SSI_LLM_{role.upper()}_BASE_URL, "
                         "SSI_LLM_MODAL_KEY, SSI_LLM_MODAL_SECRET).")
    p = llm.get(role)
    print(f"\n[{role}] provider={llm.provider_name()} model={p.model}")
    data, usage = p.structured("Answer in JSON.", "Is 7 a prime number?",
                               {"type": "object", "properties": {"prime": {"type": "boolean"}}, "required": ["prime"],
                                "additionalProperties": False}, max_tokens=200)
    print("structured:", data, f"({usage.input_tokens} in / {usage.output_tokens} out)")
    tool = ToolSpec("get_inspection_count", "Number of OSHA inspections for a sub",
                    {"type": "object", "properties": {"sub_id": {"type": "string", "enum": ["s1", "s2"]}},
                     "required": ["sub_id"], "additionalProperties": False})
    reply = p.chat("You answer using tools.", [p.user_message("How many inspections does sub s1 have? Use the tool.")], [tool])
    print("tool call:", [(c.name, c.input) for c in reply.tool_calls] or "NONE (the endpoint may not support tool calling)")


if __name__ == "__main__":
    main()
