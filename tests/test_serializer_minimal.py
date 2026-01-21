from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer


def test_minimal_serialization():
    # A very simple query that only needs basic structure
    # Note: Since we only have query_unit handler, it will mostly just print tokens with spaces.
    query = "SELECT * WHERE { ?s ?p ?o }"
    tree = sparql_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)

    # We expect something like "SELECT * WHERE { ?s ?p ?o } " due to _handle_token adding space
    assert "SELECT" in result
    assert "* " in result
    assert "?s " in result
    print(f"Result: '{result}'")


if __name__ == "__main__":
    test_minimal_serialization()
