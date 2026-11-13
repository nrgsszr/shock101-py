# Echo Lite

I built Echo Lite for the SHOCK 101 Python mini-project to learn how a terminal agent works. A rule-based model reads the user's request and asks for a tool using JSON. The agent runs the tool, sends the result back to the model, and records each step. The app uses only Python's standard library at runtime.

## Run the project

You need Python 3.11 or newer and `uv`. From the project directory, run:

```bash
uv sync
uv run python -m echo_lite "what is 12*7 and the time in UTC?"
uv run python -m echo_lite "word count: hello from echo"
uv run python -m echo_lite -- "-(2+3)"
```

The first command that runs Echo Lite prints `12*7 = 84` along with the current UTC time. The word-count example prints `Word count: 3`. Use `--` before an expression that starts with a minus sign so the command-line parser treats it as the task.

## How it works

1. The agent starts the message history with the user's task and passes it to `FakeModel`.
2. The model looks for an arithmetic expression, a request for the time in UTC, or a word-count request. It returns a JSON string such as `{"tool": "calc", "arg": "12*7"}`.
3. The agent finds the tool in the registry and runs it. It appends the result as a message with the role `tool`. If the tool fails, the agent sends the model a result that starts with `ERROR`.
4. The loop continues until the model returns a final reply such as `{"final": "12*7 = 84"}`. The default limit is five model calls.

To try a different model, pass a callable to `run(task, model=None, max_steps=5, log_dir="runs")`. The callable receives the message history and returns a JSON string in one of the two formats above.

Each run creates a separate JSON Lines file in `runs/`. The filename uses a UTC timestamp with microseconds. Each line includes a step number and an event type, so you can follow the order of tool calls, errors, and the final reply.

## Project structure

| File | What it does |
| --- | --- |
| `echo_lite/tools.py` | Registers tools with `@tool` and runs them through `dispatch`. Includes a calculator, a word counter, and a UTC clock. |
| `echo_lite/model.py` | Chooses tools and builds the final reply with `FakeModel`. |
| `echo_lite/agent.py` | Manages message history, runs the loop, handles errors, and writes logs. |
| `echo_lite/__main__.py` | Reads the task from the command line and prints the answer. |
| `tests/test_echo_lite.py` | Tests the tools, model protocol, step limit, and run logs. |

## Run the tests

```bash
uv run python -m pytest -q
uv run python -m pytest -v
uv run python -m pytest -q -k max_steps
```

`pytest` is a development dependency. The tests write their logs to temporary directories.
