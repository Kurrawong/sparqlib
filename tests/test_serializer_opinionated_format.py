from sparqlkit import format_string


def test_serializer_opinionated_formatting():
    query = (
        "prefix ex: <http://www.example.org/schema#> "
        "prefix in: <http://www.example.org/instance#> "
        "select ?x where { graph ?g { { select ?x where { ?x ?p ?g } } } }"
    )

    expected = (
        "PREFIX ex: <http://www.example.org/schema#>\n"
        "PREFIX in: <http://www.example.org/instance#>\n"
        "\n"
        "SELECT ?x\n"
        "WHERE {\n"
        "  GRAPH ?g {\n"
        "    {\n"
        "      SELECT ?x\n"
        "      WHERE {\n"
        "        ?x ?p ?g\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}"
    )

    assert format_string(query) == expected
