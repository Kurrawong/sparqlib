from sparqlkit.parser import sparql_query_parser
from sparqlkit.serializer import SparqlSerializer


def test_minimal_serialization():
    # A very simple query that only needs basic structure
    # Note: Since we only have query_unit handler, it will mostly just print tokens.
    query = "SELECT * WHERE { ?s ?p ?o }"
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)

    # We expect tokens to be separated without trailing spaces
    assert "SELECT" in result
    assert "*" in result
    assert "?s" in result
    print(f"Result: '{result}'")


def test_serializer_spacing_punctuation():
    query = (
        "SELECT (STR(?s) AS ?x) WHERE { GRAPH <http://example.org/g1> { ?s ?p ?o } }"
    )
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)

    assert "GRAPH <http://example.org/g1>" in result
    assert "STR(?s)" in result
    assert "( STR" not in result


def test_serializer_spacing_functions():
    query = """
        SELECT *
        WHERE {
            BIND(SUBSTR(?s, 1, 2) AS ?x)
            FILTER(REPLACE(?s, "a", "b") = ?t)
            FILTER(REGEX(?s, "a"))
        }
    """
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)

    assert "SUBSTR(?s, 1, 2)" in result
    assert 'REPLACE(?s, "a", "b")' in result
    assert 'REGEX(?s, "a")' in result


if __name__ == "__main__":
    test_minimal_serialization()
