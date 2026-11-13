"""Run a model and its tools with a bounded, logged loop."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

from .model import FakeModel
from .tools import ToolError, dispatch


@dataclass
class Message:
    role: str
    content: str


def _open_log(log_dir: str | Path) -> TextIO:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    while True:
        filename = timestamp.strftime("%Y%m%dT%H%M%S_%fZ.jsonl")
        try:
            return (directory / filename).open("x", encoding="utf-8")
        except FileExistsError:
            timestamp += timedelta(microseconds=1)


def _write_log(log: TextIO, step: int, event: str, **fields: str) -> None:
    entry = {"step": step, "type": event, **fields}
    log.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _parse_reply(raw: str) -> dict[str, str]:
    if not isinstance(raw, str):
        raise ToolError("Model must return a JSON string")
    try:
        reply = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise ToolError("Model returned invalid JSON") from exc

    if not isinstance(reply, dict) or reply.keys() not in ({"final"}, {"tool", "arg"}):
        raise ToolError("Expected a final reply or a tool call")
    if not all(isinstance(value, str) for value in reply.values()):
        raise ToolError("Model reply values must be strings")
    return reply


def run(
    task: str,
    model: Callable[[list[Message]], str] | None = None,
    max_steps: int = 5,
    log_dir: str | Path = "runs",
) -> str:
    """Return the final model reply and log every model call."""
    if model is None:
        model = FakeModel()
    history = [Message("user", task)]

    with _open_log(log_dir) as log:
        for step in range(1, max_steps + 1):
            try:
                raw = model(history)
            except Exception as exc:
                _write_log(log, step, "error", message=str(exc))
                raise ToolError(f"Model failed: {exc}") from exc

            try:
                reply = _parse_reply(raw)
            except ToolError as exc:
                _write_log(log, step, "error", message=str(exc))
                raise

            if "final" in reply:
                answer = reply["final"]
                _write_log(log, step, "final", answer=answer)
                return answer

            name, arg = reply["tool"], reply["arg"]
            event = "tool"
            try:
                result = dispatch(name, arg)
            except ToolError as exc:
                result = f"ERROR: {exc}"
                event = "error"

            _write_log(log, step, event, tool=name, arg=arg, result=result)
            history.append(Message("tool", result))

        message = f"No final reply within {max_steps} model calls"
        _write_log(log, max(0, max_steps), "error", message=message)
        raise ToolError(message)
