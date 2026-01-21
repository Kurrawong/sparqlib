import re
from typing import Literal, Optional

from lark import Tree
from lark.exceptions import LarkError, UnexpectedInput

from sparql.parser import sparql_parser, sparql_update_parser
from sparql.serializer import SparqlSerializer

ParserType = Literal["sparql", "sparql_update"]


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
        line: Optional[int] = None,
        column: Optional[int] = None,
        original_error: Optional[Exception] = None,
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


def _contains(pattern: str, text: str) -> bool:
    return True if re.search(pattern, text, re.IGNORECASE) is not None else False


def validate(query: str, parser_type: Optional[ParserType] = None) -> bool:
    """Validate a SPARQL query without serializing it.

    This is faster than format_string when you only need to check validity.

    :param query: Input query string.
    :param parser_type: Optional parser type. If None, tries both parsers.
    :return: True if the query is valid.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    if parser_type == "sparql":
        try:
            sparql_parser.parse(query)
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
        query_error: Optional[Exception] = None
        try:
            sparql_parser.parse(query)
            return True
        except (LarkError, UnexpectedInput) as e:
            query_error = e

        try:
            sparql_update_parser.parse(query)
            return True
        except (LarkError, UnexpectedInput) as update_error:
            raise _wrap_lark_error(query_error, "SPARQL query") from query_error


def format_string(query: str) -> str:
    """Parse the input string and return a formatted version of it.

    It first attempts to parse the query as a SPARQL 1.1 query before
    trying to parse it as a SPARQL 1.1 Update query.

    :param query: Input query string.
    :return: Formatted query.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    query_error: Optional[Exception] = None

    try:
        tree = sparql_parser.parse(query)
        serializer = SparqlSerializer()
        serializer.visit_topdown(tree)
        return serializer.result
    except (LarkError, UnexpectedInput) as e:
        query_error = e

    try:
        tree = sparql_update_parser.parse(query)
        serializer = SparqlSerializer()
        serializer.visit_topdown(tree)
        return serializer.result
    except (LarkError, UnexpectedInput):
        raise _wrap_lark_error(query_error, "SPARQL query") from query_error


def format_string_explicit(query: str, parser_type: ParserType = "sparql") -> str:
    """Parse the input string and return a formatted version of it.

    This is faster than the format_string function if you know the query type ahead of time.

    :param query: Input query string.
    :param parser_type: The parser type, either "sparql" or "sparql_update".
    :return: Formatted query.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    if parser_type == "sparql":
        _parser = sparql_parser
    elif parser_type == "sparql_update":
        _parser = sparql_update_parser
    else:
        raise ValueError(
            f"Unexpected parser type: {parser_type}. Must be one of {ParserType}"
        )

    tree = _parser.parse(query)

    serializer = SparqlSerializer()
    serializer.visit_topdown(tree)

    return serializer.result
