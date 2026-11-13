import ast
import operator
import re
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal, DecimalException, localcontext

REGISTRY: dict[str, Callable[[str], str]] = {}

_BINARY_OPERATIONS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


class ToolError(Exception):
    """A tool call failed."""


def tool(fn: Callable[[str], str]) -> Callable[[str], str]:
    REGISTRY[fn.__name__] = fn
    return fn


def dispatch(name: str, arg: str) -> str:
    try:
        fn = REGISTRY[name]
    except KeyError as exc:
        raise ToolError(f"Unknown tool: {name}") from exc

    try:
        return fn(arg)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"{name} failed: {exc}") from exc


def _calculate(node: ast.expr, expression: str) -> Decimal:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        literal = ast.get_source_segment(expression, node)
        if literal is None:
            raise ToolError("Missing numeric literal")
        return Decimal(literal)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _calculate(node.operand, expression).copy_negate()

    if isinstance(node, ast.BinOp):
        operation = _BINARY_OPERATIONS.get(type(node.op))
        if operation is not None:
            left = _calculate(node.left, expression)
            right = _calculate(node.right, expression)
            return operation(left, right)

    raise ToolError("Unsupported arithmetic expression")


@tool
def calc(arg: str) -> str:
    expression = " ".join(arg.split())
    if not re.fullmatch(r"[0-9.+*/() -]+", expression):
        raise ToolError("Use numbers, +, -, *, /, and parentheses only")

    try:
        tree = ast.parse(expression, mode="eval")
        with localcontext() as context:
            context.prec = 28
            result = _calculate(tree.body, expression)
    except (SyntaxError, DecimalException, RecursionError) as exc:
        raise ToolError("Invalid expression or division by zero") from exc

    if result.is_zero():
        return "0"

    text = format(result, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@tool
def word_count(arg: str) -> str:
    return str(len(arg.split()))


@tool
def utc_now(arg: str) -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
