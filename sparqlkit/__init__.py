from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from lark import Token, Tree
from lark.exceptions import LarkError, UnexpectedInput

from sparqlkit.comments import attach_comments, scan_raw_comments
from sparqlkit.parser import (
    sparql_parser,
    sparql_query_parser,
    sparql_update_parser,
)
from sparqlkit.serializer import SparqlSerializer

ParserType = Literal["sparql", "sparql_update"]

__all__ = [
    "format_string",
    "format_string_explicit",
    "format_query",
    "format_update",
    "parse",
    "parse_query",
    "parse_update",
    "serialize",
    "normalize_keyword_tokens",
    "validate",
    "validate_query",
    "validate_update",
    "statement_type",
    "statement_type_from_string",
    "SparqlSyntaxError",
    "SparqlTypeError",
    "SparqlType",
    "QuerySubType",
    "UpdateSubType",
    "SparqlStatementType",
    "ParserType",
]


class SparqlType(Enum):
    """The top-level type of a SPARQL statement."""

    QUERY = "query"
    UPDATE = "update"


class QuerySubType(Enum):
    """Sub-types for SPARQL queries."""

    SELECT = "select"
    CONSTRUCT = "construct"
    DESCRIBE = "describe"
    ASK = "ask"


class UpdateSubType(Enum):
    """Sub-types for SPARQL updates."""

    INSERT_WHERE = "insert_where"
    INSERT_DATA = "insert_data"
    MODIFY = "modify"
    DELETE_WHERE = "delete_where"
    DELETE_DATA = "delete_data"
    DROP = "drop"
    CLEAR = "clear"
    LOAD = "load"
    CREATE = "create"
    ADD = "add"
    MOVE = "move"
    COPY = "copy"


@dataclass
class SparqlStatementType:
    """The type and sub-type of a SPARQL statement."""

    type: SparqlType
    subtype: QuerySubType | UpdateSubType


class SparqlSyntaxError(Exception):
    """Raised when a SPARQL query has a syntax error.

    This exception wraps the underlying parser error to provide a stable
    public interface that doesn't depend on the lark library.

    Attributes:
        message: A description of the syntax error.
        line: The line number where the error occurred (if available).
        column: The column number where the error occurred (if available).
        original_error: The underlying lark exception.
    """

    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.original_error = original_error

    def __str__(self) -> str:
        if self.line is not None and self.column is not None:
            return f"{self.message} (line {self.line}, column {self.column})"
        return self.message


class SparqlTypeError(Exception):
    """Raised when unable to determine the SPARQL statement type."""


def _wrap_lark_error(error: Exception, parser_type: str) -> SparqlSyntaxError:
    """Convert a lark exception to a SparqlSyntaxError."""
    line = getattr(error, "line", None)
    column = getattr(error, "column", None)
    message = f"Failed to parse as {parser_type}: {error}"
    return SparqlSyntaxError(message, line, column, error)


def normalize_keyword_tokens(
    node: Tree[Any] | Token, keyword_set: frozenset[str] | None = None
) -> Tree[Any] | Token:
    """Normalize SPARQL keyword token values to uppercase in a Lark tree."""
    if keyword_set is None:
        keyword_set = SparqlSerializer.KEYWORDS

    def normalize_token(token: Token) -> Token:
        value = token.value
        stripped = value.strip()
        if stripped and stripped.upper() in keyword_set:
            leading = value[: len(value) - len(value.lstrip())]
            trailing = value[len(value.rstrip()) :]
            return Token(token.type, f"{leading}{stripped.upper()}{trailing}")
        return token

    if isinstance(node, Token):
        return normalize_token(node)
    if isinstance(node, Tree):
        stack: list[list[Any]] = [[node, 0, []]]
        while stack:
            current, index, new_children = stack[-1]
            if index < len(current.children):
                child = current.children[index]
                stack[-1][1] += 1
                if isinstance(child, Token):
                    new_children.append(normalize_token(child))
                elif isinstance(child, Tree):
                    stack.append([child, 0, []])
                else:
                    new_children.append(child)
            else:
                normalized_tree = Tree(current.data, new_children)
                stack.pop()
                if stack:
                    stack[-1][2].append(normalized_tree)
                else:
                    return normalized_tree
    return node


def validate(
    query: str,
    parser_type: ParserType | None = None,
) -> bool:
    """Validate a SPARQL query without serializing it.

    This is faster than format_string when you only need to check validity.

    When parser_type is None, a unified grammar is used to parse both queries
    and updates without heuristic guessing.

    It first attempts to parse the query as a SPARQL 1.1 query before
    trying to parse it as a SPARQL 1.1 Update query.

    :param query: Input query string.
    :param parser_type: Optional parser type. If provided, only that parser is used.
    :return: True if the query is valid.
    :raises SparqlSyntaxError: If the query has a syntax error.
    :raises ValueError: If parser_type is not None, "sparql", or "sparql_update".
    """
    if parser_type is None:
        try:
            sparql_parser.parse(query)
            return True
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL query/update") from e

    if parser_type == "sparql":
        try:
            sparql_query_parser.parse(query)
            return True
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL query") from e
    elif parser_type == "sparql_update":
        try:
            sparql_update_parser.parse(query)
            return True
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL update") from e
    else:
        raise ValueError(
            f"Unexpected parser type: {parser_type}. Must be one of {ParserType}"
        )


def format_string(
    query: str,
    parser_type: ParserType | None = None,
    *,
    preserve_comments: bool = True,
    indent: str = "  ",
) -> str:
    """Parse the input string and return a formatted version of it.

    It parses using the unified grammar, which accepts both queries and updates.

    :param query: Input query string.
    :param parser_type: Optional parser type. If provided, only that parser is used.
    :param preserve_comments: Whether to preserve comments in the output.
    :param indent: The string to use for each level of indentation.
    :return: Formatted query.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    if parser_type is not None:
        return format_string_explicit(
            query,
            parser_type=parser_type,
            preserve_comments=preserve_comments,
            indent=indent,
        )

    try:
        if preserve_comments:
            tree = sparql_parser.parse(query)
            attach_comments(tree, scan_raw_comments(query))
        else:
            tree = sparql_parser.parse(query)
    except (LarkError, UnexpectedInput) as e:
        raise _wrap_lark_error(e, "SPARQL query/update") from e

    serializer = SparqlSerializer(preserve_comments=preserve_comments, indent=indent)
    serializer.visit_topdown(tree)
    # Normalize leading/trailing whitespace/newlines so callers get stable output
    # regardless of input surrounding whitespace.
    return serializer.result.strip()


def format_string_explicit(
    query: str,
    parser_type: ParserType = "sparql",
    *,
    preserve_comments: bool = True,
    indent: str = "  ",
) -> str:
    """Parse the input string and return a formatted version of it.

    This is faster than the format_string function if you know the query type
    ahead of time.

    :param query: Input query string.
    :param parser_type: The parser type, either "sparql" or "sparql_update".
    :param preserve_comments: Whether to preserve comments in the output.
    :param indent: The string to use for each level of indentation.
    :return: Formatted query.
    :raises SparqlSyntaxError: If the query has a syntax error.
    :raises ValueError: If parser_type is not "sparql" or "sparql_update".
    """
    if parser_type == "sparql":
        _parser = sparql_query_parser
        context = "SPARQL query"
    elif parser_type == "sparql_update":
        _parser = sparql_update_parser
        context = "SPARQL update"
    else:
        raise ValueError(
            f"Unexpected parser type: {parser_type}. Must be one of {ParserType}"
        )

    try:
        if preserve_comments:
            tree = _parser.parse(query)
            attach_comments(tree, scan_raw_comments(query))
        else:
            tree = _parser.parse(query)
    except (LarkError, UnexpectedInput) as e:
        raise _wrap_lark_error(e, context) from e

    serializer = SparqlSerializer(preserve_comments=preserve_comments, indent=indent)
    serializer.visit_topdown(tree)

    # Normalize leading/trailing whitespace/newlines so callers get stable output
    # regardless of input surrounding whitespace.
    return serializer.result.strip()


def format_query(
    query: str, *, preserve_comments: bool = True, indent: str = "  "
) -> str:
    """Parse and format a SPARQL query.

    This is a convenience function equivalent to
    format_string_explicit(query, "sparql").

    :param query: Input SPARQL query string.
    :param preserve_comments: Whether to preserve comments in the output.
    :param indent: The string to use for each level of indentation.
    :return: Formatted query.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    return format_string_explicit(
        query, parser_type="sparql", preserve_comments=preserve_comments, indent=indent
    )


def format_update(
    query: str, *, preserve_comments: bool = True, indent: str = "  "
) -> str:
    """Parse and format a SPARQL update.

    This is a convenience function equivalent to
    format_string_explicit(query, "sparql_update").

    :param query: Input SPARQL update string.
    :param preserve_comments: Whether to preserve comments in the output.
    :param indent: The string to use for each level of indentation.
    :return: Formatted update.
    :raises SparqlSyntaxError: If the update has a syntax error.
    """
    return format_string_explicit(
        query,
        parser_type="sparql_update",
        preserve_comments=preserve_comments,
        indent=indent,
    )


def validate_query(query: str) -> bool:
    """Validate a SPARQL query without serializing it.

    This is a convenience function equivalent to validate(query, "sparql").

    :param query: Input SPARQL query string.
    :return: True if the query is valid.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    return validate(query, parser_type="sparql")


def validate_update(query: str) -> bool:
    """Validate a SPARQL update without serializing it.

    This is a convenience function equivalent to validate(query, "sparql_update").

    :param query: Input SPARQL update string.
    :return: True if the update is valid.
    :raises SparqlSyntaxError: If the update has a syntax error.
    """
    return validate(query, parser_type="sparql_update")


def parse(
    query: str,
    parser_type: ParserType | None = None,
    *,
    preserve_comments: bool = True,
) -> Tree[Any]:
    """Parse a SPARQL query or update and return the AST.

    This function provides direct access to the parsed abstract syntax tree,
    enabling advanced use cases like query analysis and modification.

    When parser_type is None, a unified grammar is used to parse both queries
    and updates without heuristic guessing.

    :param query: Input SPARQL query or update string.
    :param parser_type: Optional parser type. If None, tries both parsers.
    :return: The parsed AST as a lark.Tree.
    :raises SparqlSyntaxError: If the query has a syntax error.
    :raises ValueError: If parser_type is not None, "sparql", or "sparql_update".
    """
    if parser_type is None:
        try:
            if preserve_comments:
                tree = sparql_parser.parse(query)
                attach_comments(tree, scan_raw_comments(query))
                return tree
            return sparql_parser.parse(query)
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL query/update") from e

    if parser_type == "sparql":
        try:
            if preserve_comments:
                tree = sparql_query_parser.parse(query)
                attach_comments(tree, scan_raw_comments(query))
                return tree
            return sparql_query_parser.parse(query)
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL query") from e
    elif parser_type == "sparql_update":
        try:
            if preserve_comments:
                tree = sparql_update_parser.parse(query)
                attach_comments(tree, scan_raw_comments(query))
                return tree
            return sparql_update_parser.parse(query)
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL update") from e
    else:
        raise ValueError(
            f"Unexpected parser type: {parser_type}. Must be one of {ParserType}"
        )


def parse_query(query: str, *, preserve_comments: bool = True) -> Tree[Any]:
    """Parse a SPARQL query and return the AST.

    This is a convenience function equivalent to parse(query, "sparql").

    :param query: Input SPARQL query string.
    :return: The parsed AST as a lark.Tree.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    return parse(query, parser_type="sparql", preserve_comments=preserve_comments)


def parse_update(query: str, *, preserve_comments: bool = True) -> Tree[Any]:
    """Parse a SPARQL update and return the AST.

    This is a convenience function equivalent to parse(query, "sparql_update").

    :param query: Input SPARQL update string.
    :return: The parsed AST as a lark.Tree.
    :raises SparqlSyntaxError: If the update has a syntax error.
    """
    return parse(
        query, parser_type="sparql_update", preserve_comments=preserve_comments
    )


def serialize(
    tree: Tree[Any], *, preserve_comments: bool = True, indent: str = "  "
) -> str:
    """Serialize a SPARQL AST back to a string.

    This function enables round-tripping: parse a query, modify the AST,
    then serialize it back to a string.

    :param tree: A lark.Tree representing a parsed SPARQL query or update.
    :param preserve_comments: Whether to preserve comments in the output.
    :param indent: The string to use for each level of indentation.
    :return: The serialized SPARQL string.
    """
    serializer = SparqlSerializer(preserve_comments=preserve_comments, indent=indent)
    serializer.visit_topdown(tree)
    # Normalize leading/trailing whitespace/newlines so callers get stable output
    # regardless of input surrounding whitespace.
    return serializer.result.strip()


def _find_child(tree: Tree[Any], *names: str) -> Tree[Any] | None:
    """Find the first child tree with one of the given names."""
    for child in tree.children:
        if isinstance(child, Tree) and child.data in names:
            return child
    return None


def _has_child(tree: Tree[Any], name: str) -> bool:
    """Check if a tree has a child with the given name."""
    return any(
        isinstance(child, Tree) and child.data == name for child in tree.children
    )


_QUERY_SUBTYPE_MAP: dict[str, QuerySubType] = {
    "select_query": QuerySubType.SELECT,
    "construct_query": QuerySubType.CONSTRUCT,
    "describe_query": QuerySubType.DESCRIBE,
    "ask_query": QuerySubType.ASK,
}

_UPDATE_SUBTYPE_MAP: dict[str, UpdateSubType] = {
    "load": UpdateSubType.LOAD,
    "clear": UpdateSubType.CLEAR,
    "drop": UpdateSubType.DROP,
    "add": UpdateSubType.ADD,
    "move": UpdateSubType.MOVE,
    "copy": UpdateSubType.COPY,
    "create": UpdateSubType.CREATE,
    "insert_data": UpdateSubType.INSERT_DATA,
    "delete_data": UpdateSubType.DELETE_DATA,
}


def _get_modify_subtype(modify_tree: Tree[Any]) -> UpdateSubType:
    """Determine the subtype of a modify operation."""
    has_delete = _has_child(modify_tree, "delete_clause")
    has_insert = _has_child(modify_tree, "insert_clause")

    if has_delete and has_insert:
        return UpdateSubType.MODIFY
    elif has_insert:
        return UpdateSubType.INSERT_WHERE
    else:
        return UpdateSubType.DELETE_WHERE


def _get_update_subtype(update1_tree: Tree[Any]) -> UpdateSubType:
    """Determine the subtype of an update1 node."""
    for child in update1_tree.children:
        if isinstance(child, Tree):
            if child.data in _UPDATE_SUBTYPE_MAP:
                return _UPDATE_SUBTYPE_MAP[child.data]
            elif child.data == "delete_where":
                return UpdateSubType.DELETE_WHERE
            elif child.data == "modify":
                return _get_modify_subtype(child)

    raise SparqlTypeError(f"Unknown update subtype in tree: {update1_tree}")


def statement_type(tree: Tree[Any]) -> SparqlStatementType:
    """Determine the type and sub-type of a SPARQL statement from its AST.

    :param tree: A lark.Tree representing a parsed SPARQL query or update.
    :return: A SparqlStatementType with the type and subtype.
    :raises SparqlTypeError: If the statement type cannot be determined.
    """
    if not isinstance(tree, Tree):
        raise SparqlTypeError(f"Expected a Tree, got {type(tree).__name__}")

    root = tree
    if root.data == "unit":
        child = _find_child(root, "query_unit", "update_unit")
        if child is None:
            raise SparqlTypeError("No query_unit or update_unit found in tree")
        root = child

    if root.data == "query_unit":
        query_tree = _find_child(root, "query")
        if query_tree is None:
            raise SparqlTypeError("No query found in query_unit")

        for name, subtype in _QUERY_SUBTYPE_MAP.items():
            if _find_child(query_tree, name) is not None:
                return SparqlStatementType(SparqlType.QUERY, subtype)

        raise SparqlTypeError("Unknown query subtype")

    elif root.data == "update_unit":
        update_tree = _find_child(root, "update")
        if update_tree is None:
            raise SparqlTypeError("No update found in update_unit")

        update1_tree = _find_child(update_tree, "update1")
        if update1_tree is None:
            raise SparqlTypeError("No update1 found in update")

        update_subtype = _get_update_subtype(update1_tree)
        return SparqlStatementType(SparqlType.UPDATE, update_subtype)

    elif root.data == "query":
        for name, query_subtype in _QUERY_SUBTYPE_MAP.items():
            if _find_child(root, name) is not None:
                return SparqlStatementType(SparqlType.QUERY, query_subtype)
        raise SparqlTypeError("Unknown query subtype")

    elif root.data == "update":
        update1_tree = _find_child(root, "update1")
        if update1_tree is None:
            raise SparqlTypeError("No update1 found in update")

        update_subtype = _get_update_subtype(update1_tree)
        return SparqlStatementType(SparqlType.UPDATE, update_subtype)

    else:
        raise SparqlTypeError(f"Unexpected root node: {root.data}")


def statement_type_from_string(
    query: str,
    parser_type: ParserType | None = None,
) -> SparqlStatementType:
    """Parse a SPARQL string and determine its statement type and sub-type.

    This is a convenience function that combines parse() and statement_type().

    :param query: Input SPARQL query or update string.
    :param parser_type: Optional parser type. If None, uses unified grammar.
    :return: A SparqlStatementType with the type and subtype.
    :raises SparqlSyntaxError: If the query has a syntax error.
    :raises SparqlTypeError: If the statement type cannot be determined.
    """
    tree = parse(query, parser_type=parser_type, preserve_comments=False)
    return statement_type(tree)
