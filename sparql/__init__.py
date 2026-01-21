import os
import re
from typing import Literal

from sparql.parser import sparql_parser, sparql_update_parser
from sparql.serializer import SparqlSerializer
from sparql.serializer_iterative import IterativeSparqlSerializer

ParserType = Literal["sparql", "sparql_update"]

USE_ITERATIVE_SERIALIZER = (
    os.environ.get("SPARQL_USE_ITERATIVE_SERIALIZER", "true").lower() == "true"
)


def get_serializer(use_iterative: bool = None):
    """Returns the selected serializer implementation."""
    if use_iterative is None:
        use_iterative = USE_ITERATIVE_SERIALIZER

    if use_iterative:
        return IterativeSparqlSerializer()
    else:
        return SparqlSerializer()


def get_serializer_info() -> str:
    """Returns information about the active serializer implementation."""
    return "iterative" if USE_ITERATIVE_SERIALIZER else "recursive"


def _contains(pattern: str, text: str) -> bool:
    return True if re.search(pattern, text, re.IGNORECASE) is not None else False


def format_string(query: str, use_iterative: bool = None) -> str:
    """Parse the input string and return a formatted version of it.

    It first attempts to parse the query as a SPARQL 1.1 query before
    trying to parse it as a SPARQL 1.1 Update query.

    :param query: Input query string.
    :param use_iterative: Whether to use the iterative serializer.
    :return: Formatted query.
    """
    try:
        _parser = sparql_parser
        tree = _parser.parse(query)

        serializer = get_serializer(use_iterative)
        serializer.visit_topdown(tree)

        return serializer.result
    except:
        _parser = sparql_update_parser
        tree = _parser.parse(query)

        serializer = get_serializer(use_iterative)
        serializer.visit_topdown(tree)

        return serializer.result


def format_string_explicit(
    query: str, parser_type: ParserType = "sparql", use_iterative: bool = None
) -> str:
    """Parse the input string and return a formatted version of it.

    This is faster than the format_string function if you know the query type ahead of time.

    :param query: Input query string.
    :param parser_type: The parser type, either "sparql" or "sparql_update".
    :param use_iterative: Whether to use the iterative serializer.
    :return: Formatted query.
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

    serializer = get_serializer(use_iterative)
    serializer.visit_topdown(tree)

    return serializer.result
