"""Run Echo from the terminal."""

import argparse
import sys

from .agent import run
from .tools import ToolError


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a task with Echo Lite.")
    parser.add_argument("task", help="A task for Echo Lite")
    args = parser.parse_args()

    try:
        print(run(args.task))
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
