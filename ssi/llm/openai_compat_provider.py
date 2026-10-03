"""An OpenAI-compatible chat endpoint (e.g. a self-hosted GLM served on Modal behind proxy auth).
Configured entirely by env vars; nothing here is Claude-specific."""
from __future__ import annotations

import json
import os
import re

from openai import OpenAI

from ssi.llm.base import Reply, ToolCall, ToolSpec, Usage


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, model: str, base_url: str):
        self.model = model
        headers = {}
        if os.environ.get("SSI_LLM_MODAL_KEY") and os.environ.get("SSI_LLM_MODAL_SECRET"):
            headers = {"Modal-Key": os.environ["SSI_LLM_MODAL_KEY"], "Modal-Secret": os.environ["SSI_LLM_MODAL_SECRET"]}
        client = OpenAI(base_url=base_url, api_key=os.environ.get("SSI_LLM_API_KEY", "unused"),
                        default_headers=headers, timeout=90.0, max_retries=2)
        if os.environ.get("LANGSMITH_API_KEY"):
            from langsmith.wrappers import wrap_openai
            client = wrap_openai(client)
        self.client = client

    def structured(self, system: str, user: str, schema: dict, max_tokens: int = 1024) -> tuple[dict | None, Usage]:
        prompt = f"{user}\n\nReply with ONLY a JSON object matching this schema:\n{json.dumps(schema)}"
        resp = self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        u = resp.usage
        usage = Usage(getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0, 1)
        text = resp.choices[0].message.content or ""
        m = re.search(r"\{.*\}", text, re.S)
        try:
            return (json.loads(m.group(0)) if m else None), usage
        except json.JSONDecodeError:
            return None, usage

    def chat(self, system: str, messages: list, tools: list[ToolSpec], max_tokens: int = 4000) -> Reply:
        resp = self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens, tool_choice="auto",
            tools=[{"type": "function", "function": {"name": t.name, "description": t.description,
                                                      "parameters": t.parameters}} for t in tools],
            messages=[{"role": "system", "content": system}, *messages])
        choice = resp.choices[0]
        msg = choice.message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(tc.id, tc.function.name, args))
        u = resp.usage
        return Reply(text=msg.content or "", tool_calls=calls, assistant_message=msg.model_dump(exclude_none=True),
                     stop_reason="tool_use" if calls else (choice.finish_reason or "end_turn"),
                     input_tokens=getattr(u, "prompt_tokens", 0) or 0, output_tokens=getattr(u, "completion_tokens", 0) or 0)

    def user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> list:
        return [{"role": "tool", "tool_call_id": call.id, "content": body} for call, body, _ in results]
