from sparql import format_string


def test_serializer_opinionated_formatting():
    query = (
        "prefix ex: <http://www.example.org/schema#> "
        "prefix in: <http://www.example.org/instance#> "
        "select ?x where { graph ?g { { select ?x where { ?x ?p ?g } } } }"
    )

    expected = (
        "prefix ex: <http://www.example.org/schema#>\n"
        "prefix in: <http://www.example.org/instance#>\n"
        "\n"
        "select ?x\n"
        "where {\n"
        "    graph ?g {\n"
        "        {\n"
        "            select ?x\n"
        "            where {\n"
        "                ?x ?p  ?g\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}"
    )

    assert format_string(query) == expected
