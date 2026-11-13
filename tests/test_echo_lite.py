import json
import re
from pathlib import Path

import pytest

from echo_lite.agent import Message, run
from echo_lite.tools import REGISTRY, ToolError, dispatch, tool


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2+3*4", "14"),
        ("10/4", "2.5"),
        ("8/4", "2"),
        ("-(2+3)", "-5"),
    ],
)
def test_calc(expression: str, expected: str) -> None:
    assert REGISTRY["calc"](expression) == expected


@pytest.mark.parametrize("expression", ["1/0", "2+"])
def test_calc_rejects_bad_input(expression: str) -> None:
    with pytest.raises(ToolError):
        REGISTRY["calc"](expression)


def test_word_count() -> None:
    assert REGISTRY["word_count"]("سلام دنیا hello") == "3"


def test_dispatch_rejects_unknown_tool() -> None:
    with pytest.raises(ToolError):
        dispatch("nope", "x")


def test_utc_time_format() -> None:
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", REGISTRY["utc_now"]("")
    )


def test_decorator_returns_original_function(monkeypatch: pytest.MonkeyPatch) -> None:
    def ping(arg: str) -> str:
        return arg.upper()

    monkeypatch.setattr("echo_lite.tools.REGISTRY", REGISTRY.copy())
    from echo_lite.tools import REGISTRY as isolated_registry

    assert tool(ping) is ping
    assert isolated_registry["ping"] is ping
    assert dispatch("ping", "echo") == "ECHO"


def test_dispatch_wraps_tool_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def crash(arg: str) -> str:
        raise RuntimeError("broken")

    monkeypatch.setitem(REGISTRY, "crash", crash)
    with pytest.raises(ToolError, match="broken"):
        dispatch("crash", "x")


def _read_log(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_model_receives_latest_tool_result_and_run_logs_steps(tmp_path: Path) -> None:
    seen: list[list[Message]] = []

    def model(messages: list[Message]) -> str:
        seen.append(messages.copy())
        if len(seen) == 1:
            return '{"tool": "calc", "arg": "12*7"}'
        return json.dumps({"final": messages[-1].content})

    assert run("12*7?", model=model, max_steps=4, log_dir=tmp_path) == "84"
    assert seen == [
        [Message("user", "12*7?")],
        [Message("user", "12*7?"), Message("tool", "84")],
    ]
    log = _read_log(next(tmp_path.glob("*.jsonl")))
    assert [(row["step"], row["type"]) for row in log] == [(1, "tool"), (2, "final")]


@pytest.mark.parametrize(("name", "arg"), [("nope", "x"), ("calc", "1/0")])
def test_run_can_recover_from_tool_error(tmp_path: Path, name: str, arg: str) -> None:
    def model(messages: list[Message]) -> str:
        if messages[-1].role == "user":
            return json.dumps({"tool": name, "arg": arg})
        assert messages[-1].role == "tool"
        assert messages[-1].content.startswith("ERROR")
        return '{"final": "recovered"}'

    assert run("test", model=model, log_dir=tmp_path) == "recovered"
    log = _read_log(next(tmp_path.glob("*.jsonl")))
    assert [row["type"] for row in log] == ["error", "final"]


@pytest.mark.parametrize(
    "reply",
    [
        "not JSON",
        "[]",
        '{"tool": "calc"}',
        '{"final": 42}',
        '{"tool": "calc", "arg": 5}',
        '{"final": "x", "tool": "calc", "arg": "1+1"}',
    ],
)
def test_run_rejects_invalid_model_reply(tmp_path: Path, reply: str) -> None:
    def model(messages: list[Message]) -> str:
        return reply

    with pytest.raises(ToolError):
        run("test", model=model, log_dir=tmp_path)
    log = _read_log(next(tmp_path.glob("*.jsonl")))
    assert [(row["step"], row["type"]) for row in log] == [(1, "error")]


def test_run_stops_at_max_steps(tmp_path: Path) -> None:
    calls = 0

    def model(messages: list[Message]) -> str:
        nonlocal calls
        calls += 1
        return '{"tool": "calc", "arg": "2+2"}'

    with pytest.raises(ToolError, match="3 model calls"):
        run("test", model=model, max_steps=3, log_dir=tmp_path)
    assert calls == 3
    log = _read_log(next(tmp_path.glob("*.jsonl")))
    assert [row["step"] for row in log if row["type"] == "tool"] == [1, 2, 3]
    assert log[-1]["type"] == "error"


def test_each_run_has_its_own_log_and_default_model_uses_both_tools(tmp_path: Path) -> None:
    reply = run("what is 12*7 and the time in UTC?", log_dir=tmp_path)
    assert re.fullmatch(r"12\*7 = 84; UTC time: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", reply)
    assert run("word count: سلام دنیا hello", log_dir=tmp_path) == "Word count: 3"
    files = sorted(tmp_path.glob("*.jsonl"))
    assert len(files) == 2
    assert all(re.fullmatch(r"\d{8}T\d{6}_\d{6}Z\.jsonl", path.name) for path in files)
    assert [row["type"] for row in _read_log(files[0])] == ["tool", "tool", "final"]
