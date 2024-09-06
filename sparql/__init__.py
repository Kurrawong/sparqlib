import re
from typing import Literal

from sparql.parser import sparql_parser, sparql_update_parser
from sparql.serializer import SparqlSerializer

ParserType = Literal["sparql", "sparql_update"]


def _contains(pattern: str, text: str) -> bool:
    return True if re.search(pattern, text, re.IGNORECASE) is not None else False


def format_string(query: str) -> str:
    """Parse the input string and return a formatted version of it.

    It first attempts to parse the query as a SPARQL 1.1 query before
    trying to parse it as a SPARQL 1.1 Update query.

    :param query: Input query string.
    :return: Formatted query.
    """
    try:
        _parser = sparql_parser
        tree = _parser.parse(query)

        sparql_serializer = SparqlSerializer()
        sparql_serializer.visit_topdown(tree)

        return sparql_serializer.result
    except:
        _parser = sparql_update_parser
        tree = _parser.parse(query)

        sparql_serializer = SparqlSerializer()
        sparql_serializer.visit_topdown(tree)

        return sparql_serializer.result



def format_string_explicit(query: str, parser_type: ParserType = "sparql") -> str:
    """Parse the input string and return a formatted version of it.

    This is faster than the format_string function if you know the query type ahead of time.

    :param query: Input query string.
    :param parser_type: The parser type, either "sparql" or "sparql_update".
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

    sparql_serializer = SparqlSerializer()
    sparql_serializer.visit_topdown(tree)

    return sparql_serializer.result
