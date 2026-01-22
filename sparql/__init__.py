import re
from typing import Literal, Optional

from lark import Tree
from lark.exceptions import LarkError, UnexpectedInput

from sparql.parser import sparql_parser, sparql_update_parser
from sparql.serializer import SparqlSerializer

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


def _remove_noise(text: str) -> str:
    """Remove comments, strings, and IRIs from the query text."""
    # Pattern for removing comments, strings, and IRIs
    # Order matters: triple-quoted strings must be matched before single-quoted
    # 1. Comments: #.*
    # 2. Triple-quoted strings: """...""" or '''...''' (may contain unescaped quotes)
    # 3. Single-quoted strings: "..." or '...' (handling escaped quotes)
    # 4. IRIs: <...>
    pattern = r"""
        \#.*$                              |  # Comments
        \"\"\"[\s\S]*?\"\"\"               |  # Triple double-quoted strings
        '''[\s\S]*?'''                     |  # Triple single-quoted strings
        "[^"\\]*(?:\\.[^"\\]*)*"           |  # Double quoted strings
        '[^'\\]*(?:\\.[^'\\]*)*'           |  # Single quoted strings
        <[^>]*>                               # IRIs (simplified)
    """
    return re.sub(pattern, " ", text, flags=re.VERBOSE | re.MULTILINE)


def _guess_parser_type(query: str) -> ParserType:
    """Guess the parser type based on keywords in the query.

    This is a heuristic to improve performance by trying the most likely
    parser first. It is not guaranteed to be correct.
    """
    clean_query = _remove_noise(query)

    # specific keywords that strongly suggest an UPDATE query
    # Note: INSERT/DELETE can occur in CONSTRUCT/subqueries (though usually as 'INSERT DATA' etc for updates)
    # But as top-level keywords, they indicate Update.
    # We look for these keywords. If found, we guess 'sparql_update'.
    # A more robust check might skip PREFIX/BASE, but this is just a hint.
    update_keywords = (
        r"(?i)\b(INSERT|DELETE|LOAD|CLEAR|DROP|ADD|MOVE|COPY|CREATE|WITH)\b"
    )

    # Query keywords
    query_keywords = r"(?i)\b(SELECT|CONSTRUCT|ASK|DESCRIBE)\b"

    has_update = _contains(update_keywords, clean_query)
    has_query = _contains(query_keywords, clean_query)

    if has_update and not has_query:
        return "sparql_update"
    # Default to sparql (Query) as it's the most common case, or if ambiguous
    return "sparql"


def validate(query: str, parser_type: Optional[ParserType] = None) -> bool:
    """Validate a SPARQL query without serializing it.

    This is faster than format_string when you only need to check validity.

    When parser_type is None, a heuristic is used to guess the most likely
    parser type. If parsing fails, the other parser is tried as a fallback.
    If both parsers fail, the error from the initially guessed parser is raised.

    :param query: Input query string.
    :param parser_type: Optional parser type. If None, tries both parsers.
    :return: True if the query is valid.
    :raises SparqlSyntaxError: If the query has a syntax error.
    :raises ValueError: If parser_type is not None, "sparql", or "sparql_update".
    """
    if parser_type is None:
        guessed_type = _guess_parser_type(query)
        try:
            return validate(query, guessed_type)
        except SparqlSyntaxError as e:
            other_type: ParserType = (
                "sparql_update" if guessed_type == "sparql" else "sparql"
            )
            try:
                return validate(query, other_type)
            except SparqlSyntaxError:
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
    else:
        raise ValueError(
            f"Unexpected parser type: {parser_type}. Must be one of {ParserType}"
        )


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
    secondary_parser = (
        sparql_update_parser if guessed_type == "sparql" else sparql_parser
    )

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
    :raises ValueError: If parser_type is not "sparql" or "sparql_update".
    """
    if parser_type == "sparql":
        _parser = sparql_parser
        context = "SPARQL query"
    elif parser_type == "sparql_update":
        _parser = sparql_update_parser
        context = "SPARQL update"
    else:
        raise ValueError(
            f"Unexpected parser type: {parser_type}. Must be one of {ParserType}"
        )

    try:
        tree = _parser.parse(query)
    except (LarkError, UnexpectedInput) as e:
        raise _wrap_lark_error(e, context) from e

    serializer = SparqlSerializer()
    serializer.visit_topdown(tree)

    return serializer.result


def format_query(query: str) -> str:
    """Parse and format a SPARQL query.

    This is a convenience function equivalent to format_string_explicit(query, "sparql").

    :param query: Input SPARQL query string.
    :return: Formatted query.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    return format_string_explicit(query, parser_type="sparql")


def format_update(query: str) -> str:
    """Parse and format a SPARQL update.

    This is a convenience function equivalent to format_string_explicit(query, "sparql_update").

    :param query: Input SPARQL update string.
    :return: Formatted update.
    :raises SparqlSyntaxError: If the update has a syntax error.
    """
    return format_string_explicit(query, parser_type="sparql_update")


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


def parse(query: str, parser_type: Optional[ParserType] = None) -> Tree:
    """Parse a SPARQL query or update and return the AST.

    This function provides direct access to the parsed abstract syntax tree,
    enabling advanced use cases like query analysis and modification.

    When parser_type is None, a heuristic is used to guess the most likely
    parser type. If parsing fails, the other parser is tried as a fallback.

    :param query: Input SPARQL query or update string.
    :param parser_type: Optional parser type. If None, tries both parsers.
    :return: The parsed AST as a lark.Tree.
    :raises SparqlSyntaxError: If the query has a syntax error.
    :raises ValueError: If parser_type is not None, "sparql", or "sparql_update".
    """
    if parser_type is None:
        guessed_type = _guess_parser_type(query)
        try:
            return parse(query, guessed_type)
        except SparqlSyntaxError as e:
            other_type: ParserType = (
                "sparql_update" if guessed_type == "sparql" else "sparql"
            )
            try:
                return parse(query, other_type)
            except SparqlSyntaxError:
                raise e

    if parser_type == "sparql":
        try:
            return sparql_parser.parse(query)
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL query") from e
    elif parser_type == "sparql_update":
        try:
            return sparql_update_parser.parse(query)
        except (LarkError, UnexpectedInput) as e:
            raise _wrap_lark_error(e, "SPARQL update") from e
    else:
        raise ValueError(
            f"Unexpected parser type: {parser_type}. Must be one of {ParserType}"
        )


def parse_query(query: str) -> Tree:
    """Parse a SPARQL query and return the AST.

    This is a convenience function equivalent to parse(query, "sparql").

    :param query: Input SPARQL query string.
    :return: The parsed AST as a lark.Tree.
    :raises SparqlSyntaxError: If the query has a syntax error.
    """
    return parse(query, parser_type="sparql")


def parse_update(query: str) -> Tree:
    """Parse a SPARQL update and return the AST.

    This is a convenience function equivalent to parse(query, "sparql_update").

    :param query: Input SPARQL update string.
    :return: The parsed AST as a lark.Tree.
    :raises SparqlSyntaxError: If the update has a syntax error.
    """
    return parse(query, parser_type="sparql_update")


def serialize(tree: Tree) -> str:
    """Serialize a SPARQL AST back to a string.

    This function enables round-tripping: parse a query, modify the AST,
    then serialize it back to a string.

    :param tree: A lark.Tree representing a parsed SPARQL query or update.
    :return: The serialized SPARQL string.
    """
    serializer = SparqlSerializer()
    serializer.visit_topdown(tree)
    return serializer.result
