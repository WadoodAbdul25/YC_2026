from __future__ import annotations

import json
import os
import re
from typing import Any, Optional


class LLMError(RuntimeError):
    pass


def get_client() -> Any:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI  # type: ignore

        return OpenAI(api_key=api_key)
    except Exception:
        try:
            import openai  # type: ignore

            openai.api_key = api_key
            return openai
        except Exception:
            return None


def _extract_json(text: str) -> Any:
    text = text.strip()
    if not text:
        raise LLMError("Empty response from LLM")

    if text[0] in "[{":
        return json.loads(text)

    match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
    if not match:
        raise LLMError("No JSON found in LLM response")
    return json.loads(match.group(1))


def generate_json(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> Optional[Any]:
    client = get_client()
    if client is None:
        return None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
            except Exception:
                response = client.chat.completions.create(model=model, messages=messages)

            content = response.choices[0].message.content
            return _extract_json(content or "")

        if hasattr(client, "ChatCompletion"):
            response = client.ChatCompletion.create(model=model, messages=messages)
            content = response["choices"][0]["message"]["content"]
            return _extract_json(content or "")
    except Exception as exc:
        raise LLMError(str(exc)) from exc

    return None
