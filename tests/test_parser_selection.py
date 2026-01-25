import pytest

import sparqlkit
from sparqlkit import SparqlSyntaxError


def test_guess_sparql_update():
    result = sparqlkit.format_string(
        """
        LOAD <http://example.org/faraway> INTO GRAPH <localCopy>
    """
    )

    assert result


def test_guess_sparql():
    result = sparqlkit.format_string(
        """
        select distinct ?s (count(?s) as ?count)
        FROM <http://dbpedia.org>
        FROM NAMED <http://dbpedia.org>
        where {
            ?s ?p ?o .
            ?o ?pp ?oo ;
                ?ppp ?ooo .
            OPTIONAL {
                ?s a ?o .
            } .
            ?o2 ?p2 ?o3 .
        }
    """
    )

    assert result


def test_specify_sparql_parser():
    with pytest.raises(SparqlSyntaxError):
        sparqlkit.format_string_explicit(
            """
            LOAD <http://example.org/faraway> INTO GRAPH <localCopy>
        """,
            parser_type="sparql",
        )


def test_specify_sparql_update_parser():
    with pytest.raises(SparqlSyntaxError):
        sparqlkit.format_string_explicit(
            """
            select distinct ?s (count(?s) as ?count)
        FROM <http://dbpedia.org>
        FROM NAMED <http://dbpedia.org>
        where {
            ?s ?p ?o .
            ?o ?pp ?oo ;
                ?ppp ?ooo .
            OPTIONAL {
                ?s a ?o .
            } .
            ?o2 ?p2 ?o3 .
        }
        """,
            parser_type="sparql_update",
        )


def test_format_string_parser_type_hint():
    result = sparqlkit.format_string(
        """
        select distinct ?s (count(?s) as ?count)
        WHERE { ?s ?p ?o }
    """,
        parser_type="sparql",
    )
    assert result
