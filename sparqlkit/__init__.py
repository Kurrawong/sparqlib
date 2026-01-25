from __future__ import annotations

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
    "SparqlSyntaxError",
    "ParserType",
]


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
