import pytest

from sparqlkit.parser import sparql_query_parser
from sparqlkit.serializer import SparqlSerializer


def test_property_path_alternative():
    query = "SELECT * WHERE { ?s foaf:knows|foaf:friend ?o }"
    tree = sparql_query_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    assert "foaf:knows|foaf:friend" in result


def test_property_path_sequence():
    query = "SELECT * WHERE { ?s foaf:knows/foaf:name ?o }"
    tree = sparql_query_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    assert "foaf:knows/foaf:name" in result


def test_property_path_inverse():
    query = "SELECT * WHERE { ?s ^foaf:knows ?o }"
    tree = sparql_query_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    assert "^foaf:knows" in result


def test_property_path_complex():
    query = "SELECT * WHERE { ?s ^foaf:knows/(foaf:friend|foaf:colleague)* ?o }"
    tree = sparql_query_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    # The exact formatting might have some extra spaces but the logic should be there
    assert "^foaf:knows/(foaf:friend|foaf:colleague)*" in result.replace(" ", "")


def test_negated_property_set():
    query = "SELECT * WHERE { ?s !(foaf:knows|^foaf:friend) ?o }"
    tree = sparql_query_parser.parse(query)
    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    assert "!(foaf:knows|^foaf:friend)" in result.replace(" ", "")


if __name__ == "__main__":
    pytest.main([__file__])
