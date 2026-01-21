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


def _guess_parser_type(query: str) -> ParserType:
    """Guess the parser type based on keywords in the query.

    This is a heuristic to improve performance by trying the most likely
    parser first. It is not guaranteed to be correct.
    """
    # specific keywords that strongly suggest an UPDATE query
    # Note: INSERT/DELETE can occur in CONSTRUCT/subqueries (though usually as 'INSERT DATA' etc for updates)
    # But as top-level keywords, they indicate Update.
    # We look for these keywords. If found, we guess 'sparql_update'.
    # A more robust check might skip PREFIX/BASE, but this is just a hint.
    update_keywords = r"(?i)\b(INSERT|DELETE|LOAD|CLEAR|DROP|ADD|MOVE|COPY|CREATE|WITH)\b"
    
    # Query keywords
    query_keywords = r"(?i)\b(SELECT|CONSTRUCT|ASK|DESCRIBE)\b"

    has_update = _contains(update_keywords, query)
    has_query = _contains(query_keywords, query)

    if has_update and not has_query:
        return "sparql_update"
    # Default to sparql (Query) as it's the most common case, or if ambiguous
    return "sparql"


def validate(query: str, parser_type: Optional[ParserType] = None) -> bool:
    """Validate a SPARQL query without serializing it.

    This is faster than format_string when you only need to check validity.

    :param query: Input query string.
    :param parser_type: Optional parser type. If None, tries both parsers.
    :return: True if the query is valid.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    if parser_type is None:
        # specific optimization: guess type to avoid double parsing penalty
        parser_type = _guess_parser_type(query)
        # We will try the guessed one first, then fallback
        try:
            return validate(query, parser_type)
        except SparqlSyntaxError as e:
            # If the guess failed, try the other one
            other_type: ParserType = "sparql_update" if parser_type == "sparql" else "sparql"
            try:
                return validate(query, other_type)
            except SparqlSyntaxError:
                # If both fail, raise the error from the guessed type (original attempt)
                # or maybe the first one makes more sense? 
                # Actually, if the user didn't specify, we usually assume Query implies Query syntax error.
                # But if it was an Update, we want that error.
                # Let's raise the error corresponding to the one that matched the structure closest?
                # For now, let's just re-raise the first one as it was the "best guess".
                raise e

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
    
    return False


def format_string(query: str) -> str:
    """Parse the input string and return a formatted version of it.

    It first attempts to parse the query based on a heuristic guess,
    falling back to the other parser if the first fails.

    :param query: Input query string.
    :return: Formatted query.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    guessed_type = _guess_parser_type(query)
    primary_parser = sparql_parser if guessed_type == "sparql" else sparql_update_parser
    secondary_parser = sparql_update_parser if guessed_type == "sparql" else sparql_parser
    
    first_error: Optional[Exception] = None

    try:
        tree = primary_parser.parse(query)
        serializer = SparqlSerializer()
        serializer.visit_topdown(tree)
        return serializer.result
    except (LarkError, UnexpectedInput) as e:
        first_error = e

    try:
        tree = secondary_parser.parse(query)
        serializer = SparqlSerializer()
        serializer.visit_topdown(tree)
        return serializer.result
    except (LarkError, UnexpectedInput):
        # Raise error for the primary guess type, as it was the most likely intent
        context = "query" if guessed_type == "sparql" else "update"
        raise _wrap_lark_error(first_error, f"SPARQL {context}") from first_error


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
