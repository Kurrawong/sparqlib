from sparqlkit import format_string

EXAMPLE_QUERY = (
    'SELECT ?search_result_uri ?predicate ?match ?weight (URI(CONCAT("urn:hash:", '
    "SHA256(CONCAT(STR(?search_result_uri), STR(?predicate), STR(?match), "
    "STR(?weight))))) AS ?hashID)\n"
    "    WHERE {\n"
    "        SELECT ?search_result_uri ?predicate ?match (SUM(?w) AS ?weight)\n"
    "        WHERE\n"
    "        {\n"
    "          ?search_result_uri ?predicate ?match .\n"
    "            VALUES ?predicate { <bar> }\n"
    "            {\n"
    "                ?search_result_uri ?predicate ?match .\n"
    "                BIND (100 AS ?w)\n"
    '                FILTER (LCASE(?match) = "$term")\n'
    "            }\n"
    "          UNION\n"
    "            {\n"
    "                ?search_result_uri ?predicate ?match .\n"
    "                BIND (20 AS ?w)\n"
    '                FILTER (REGEX(?match, "^$term", "i"))\n'
    "            }\n"
    "          UNION\n"
    "            {\n"
    "                ?search_result_uri ?predicate ?match .\n"
    "                BIND (10 AS ?w)\n"
    '                FILTER (REGEX(?match, "$term", "i"))\n'
    "            }\n"
    "        }\n"
    "        GROUP BY ?search_result_uri ?predicate ?match\n"
    "    }\n"
    "        ORDER BY DESC(?weight)\n"
)


EXPECTED_FORMATTED = (
    'SELECT ?search_result_uri ?predicate ?match ?weight (URI(CONCAT ("urn:hash:", '
    "SHA256(CONCAT (STR(?search_result_uri), STR(?predicate), STR(?match), "
    "STR(?weight))))) AS ?hashID)\n"
    "WHERE {\n"
    "  SELECT ?search_result_uri ?predicate ?match (SUM(?w) AS ?weight)\n"
    "  WHERE {\n"
    "    ?search_result_uri ?predicate ?match\n"
    "    VALUES ?predicate {\n"
    "      <bar>\n"
    "    }\n"
    "    {\n"
    "      ?search_result_uri ?predicate ?match\n"
    "      BIND (100  AS ?w) \n"
    '      FILTER (LCASE(?match)= "$term")\n'
    "    }\n"
    "    UNION {\n"
    "      ?search_result_uri ?predicate ?match\n"
    "      BIND (20  AS ?w) \n"
    '      FILTER (REGEX(?match, "^$term", "i"))\n'
    "    }\n"
    "    UNION {\n"
    "      ?search_result_uri ?predicate ?match\n"
    "      BIND (10  AS ?w) \n"
    '      FILTER (REGEX(?match, "$term", "i"))\n'
    "    }\n"
    "  }\n"
    "  GROUP BY ?search_result_uri ?predicate ?match\n"
    "}\n"
    "ORDER BY DESC (?weight)"
)


def test_example_query_formatting_regression():
    assert format_string(EXAMPLE_QUERY) == EXPECTED_FORMATTED
