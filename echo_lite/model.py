"""A deterministic model that follows the same JSON protocol as a real model."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Message


def _requests(task: str) -> list[tuple[str, str]]:
    """Find a tool plan for the supported task patterns."""
    word_task = re.fullmatch(
        r"\s*(?:word[ _]count\b\s*:?\s*|count the words in\s+)(.*)",
        task,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if word_task is not None:
        return [("word_count", word_task.group(1))]

    requests: list[tuple[str, str]] = []
    for match in re.finditer(r"(?<!\w)[(0-9.\-][0-9.+*/() \t-]*(?!\w)", task):
        expression = match.group().strip()
        has_number = re.search(r"[0-9]", expression)
        has_operator = any(char in expression for char in "+-*/()")
        if has_number and (has_operator or task.strip().rstrip("?") == expression):
            requests.append(("calc", expression))
            break

    if re.search(r"\butc\b", task, flags=re.IGNORECASE):
        requests.append(("utc_now", ""))

    return requests


class FakeModel:
    """Choose a tool or assemble a reply using the message history."""

    def __call__(self, messages: list[Message]) -> str:
        requests = _requests(messages[0].content)
        results = [message.content for message in messages if message.role == "tool"]

        if len(results) < len(requests):
            name, arg = requests[len(results)]
            return json.dumps({"tool": name, "arg": arg})

        if not requests:
            return json.dumps({"final": "Try a calculation, UTC time, or word count: TEXT."})

        parts = []
        for (name, arg), result in zip(requests, results):
            if result.startswith("ERROR"):
                parts.append(result)
            elif name == "calc":
                parts.append(f"{arg} = {result}")
            elif name == "utc_now":
                parts.append(f"UTC time: {result}")
            else:
                parts.append(f"Word count: {result}")
        return json.dumps({"final": "; ".join(parts)}, ensure_ascii=False)
