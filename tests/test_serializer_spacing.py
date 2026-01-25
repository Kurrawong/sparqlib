from sparqlkit import parse_query
from sparqlkit.serializer import SparqlSerializer


def serialize(query):
    tree = parse_query(query)
    serializer = SparqlSerializer()
    return serializer.visit_topdown(tree)


def test_construct_where_spacing():
    query = "CONSTRUCT WHERE { ?s ?p ?o }"
    serialized = serialize(query)
    # Expect "WHERE {" with single space (plus indentation/newlines)
    # The serializer puts a newline before WHERE usually.
    # Output seen: "\nWHERE  {\n"
    # We want to avoid "WHERE  {"
    assert "WHERE {" in serialized
    assert "WHERE  {" not in serialized


def test_union_spacing():
    query = "SELECT * WHERE { { ?s ?p ?o } UNION { ?s ?p ?o } }"
    serialized = serialize(query)
    # The serializer handles UNION in _group_or_union_graph_pattern_enter
    # It loops over children.
    # Expect "UNION {"
    assert "UNION {" in serialized
    assert "UNION  {" not in serialized


def test_service_spacing():
    query = "SELECT * WHERE { SERVICE <http://example.org> { ?s ?p ?o } }"
    serialized = serialize(query)
    # Expect "SERVICE <...> {"
    # Note: SERVICE adds indentation too.
    assert "SERVICE <http://example.org> {" in serialized
    assert "SERVICE  <http://example.org> {" not in serialized


def test_bind_as_spacing():
    query = "SELECT * WHERE { BIND(1 AS ?x) }"
    serialized = serialize(query)
    # Expect "AS ?x"
    assert "AS ?x" in serialized
    assert "AS  ?x" not in serialized


def test_filter_not_exists_spacing():
    query = "SELECT * WHERE { ?s ?p ?o FILTER         NOT EXISTS{?s ?p ?o} }"
    serialized = serialize(query)
    assert "FILTER NOT EXISTS {" in serialized
    assert "FILTER  NOT EXISTS" not in serialized
    assert "NOT EXISTS{" not in serialized


def test_empty_where_clause_compact():
    query = "SELECT * WHERE {}"
    serialized = serialize(query)
    assert "WHERE {}" in serialized
    assert "WHERE {\n" not in serialized


def test_select_asterisk_brace_spacing():
    query = "select * { ?s ?p ?o } limit 10"
    serialized = serialize(query)
    assert "SELECT * {" in serialized
    assert "SELECT *{" not in serialized
