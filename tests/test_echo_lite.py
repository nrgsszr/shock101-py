import pytest

from echo_lite.tools import REGISTRY, ToolError, dispatch


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
