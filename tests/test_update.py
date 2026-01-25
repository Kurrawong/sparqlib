import pytest

from sparqlkit.parser import sparql_update_parser
from sparqlkit.serializer import SparqlSerializer


def test_insert_data():
    query = (
        "INSERT DATA { <http://example.org/s> <http://example.org/p> "
        "<http://example.org/o> }"
    )
    tree = sparql_update_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    # The exact formatting might vary, let's see what it produces
    assert "INSERT DATA" in result
    assert "<http://example.org/s>" in result
    assert "{" in result
    assert "}" in result


def test_delete_where():
    query = "DELETE WHERE { ?s ?p ?o }"
    tree = sparql_update_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    assert "DELETE WHERE" in result
    assert "?s" in result


def test_insert_data_graph():
    query = (
        "INSERT DATA { GRAPH <http://example.org/g1> { <http://example.org/s> "
        "<http://example.org/p> <http://example.org/o> } }"
    )

    tree = sparql_update_parser.parse(query)

    serializer = SparqlSerializer()

    result = serializer.visit_topdown(tree)

    assert "GRAPH <http://example.org/g1>" in result

    assert "{\nGRAPH <http://example.org/g1> {" in result


def test_multiple_updates():
    query = "DROP ALL; CREATE GRAPH <http://example.org/g>"
    tree = sparql_update_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    assert "DROP ALL" in result
    assert "CREATE GRAPH" in result
    assert ";" in result


def test_modify_with_where_newlines_and_empty_where():
    query = 'WITH <g> INSERT { GRAPH <g> { <s> <p> "f\\"" . } } WHERE {}'
    tree = sparql_update_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    assert "WITH <g>\n" in result
    assert "\nINSERT" in result
    assert "\nWHERE {}" in result


if __name__ == "__main__":
    pytest.main([__file__])
