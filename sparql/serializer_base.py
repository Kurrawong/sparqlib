from enum import Enum, auto
from typing import Any, Callable, NamedTuple, NotRequired, Optional, TypedDict, Union

from lark import Token, Tree


class TraversalPhase(Enum):
    """Phases of tree traversal."""

    ENTER = auto()
    EXIT = auto()
    LEAF = auto()


class TreeHandler(NamedTuple):
    """Handlers for entering and exiting a tree node."""

    enter: Optional[Callable[[Tree, dict[str, Any]], Optional[bool]]] = None
    exit: Optional[Callable[[Tree, dict[str, Any]], None]] = None


class TraversalContext(TypedDict, total=False):
    """Context passed to tree handlers during traversal."""

    indent_inc: bool


def get_prefixed_name(prefixed_name: Tree) -> str:
    """Extracts the value from a prefixed_name node."""
    return prefixed_name.children[0].value


def get_iriref(iriref: Token) -> str:
    """Extracts the value from an iriref token."""
    return iriref.value


def get_rdf_literal(rdf_literal: Tree) -> str:
    """Extracts the string representation of an rdf_literal node."""
    value = rdf_literal.children[0].children[0].value

    if len(rdf_literal.children) > 1:
        langtag_or_datatype = rdf_literal.children[1].children[0]
        if isinstance(langtag_or_datatype, Tree) and langtag_or_datatype.data == "iri":
            value += f"^^{get_iri(langtag_or_datatype)}"
        else:
            value += rdf_literal.children[1].children[0].value

    return value


def get_value(
    tree: Union[Tree, Token], memory: Optional[list[Token]] = None
) -> list[Token]:
    """Iteratively walks a tree and collects all tokens.

    Uses a stack-based approach to avoid RecursionError on deeply nested trees.
    """
    if memory is None:
        memory = []

    stack: list[Union[Tree, Token]] = [tree]

    while stack:
        node = stack.pop()
        if isinstance(node, Token):
            memory.append(node)
        else:
            # Push children in reverse order so they are processed left-to-right
            for child in reversed(node.children):
                stack.append(child)

    return memory


def get_iri(iri: Tree) -> str:
    """Extracts the string representation of an iri node."""
    value = iri.children[0]
    if isinstance(value, Token):
        return get_iriref(value)
    elif isinstance(value, Tree):
        return get_prefixed_name(value)
    else:
        raise ValueError(f"Unexpected iri type: {value.data}")


def get_data_block_value(data_block_value: Tree) -> str:
    """Extracts the string representation of a data_block_value node."""
    value = data_block_value.children[0]

    if value.data == "iri":
        return get_iri(value)
    elif (
        value.data == "rdf_literal"
        or value.data == "numeric_literal"
        or value.data == "boolean_literal"
    ):
        return get_rdf_literal(value)
    elif value.data == "undef":
        return "UNDEF"
    else:
        raise ValueError(f"Unexpected data_block_value type: {value.data}")


def get_var(var: Tree) -> str:
    """Extracts the variable name from a var node."""
    return var.children[0].value


def get_vars(vars_: list[Tree]) -> str:
    """Joins variable names with spaces."""
    result = ""
    for i, var in enumerate(vars_):
        result += get_var(var)
        if i + 1 != len(vars_):
            result += " "

    return result
