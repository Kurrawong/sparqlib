import pytest
from lark.exceptions import LarkError

import sparql


def test_guess_sparql_update():
    result = sparql.format_string_guess(
        """
        LOAD <http://example.org/faraway> INTO GRAPH <localCopy>
    """
    )

    assert result


def test_guess_sparql():
    result = sparql.format_string_guess(
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
    with pytest.raises(LarkError):
        sparql.format_string(
            """
            LOAD <http://example.org/faraway> INTO GRAPH <localCopy>
        """,
            parser_type="sparql",
        )


def test_specify_sparql_update_parser():
    with pytest.raises(LarkError):
        sparql.format_string(
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
