from sparql import format_string


EXAMPLE_QUERY = """\
SELECT ?search_result_uri ?predicate ?match ?weight (URI(CONCAT("urn:hash:", SHA256(CONCAT(STR(?search_result_uri), STR(?predicate), STR(?match), STR(?weight))))) AS ?hashID)
    WHERE {
        SELECT ?search_result_uri ?predicate ?match (SUM(?w) AS ?weight)
        WHERE
        {
          ?search_result_uri ?predicate ?match .
            VALUES ?predicate { <bar> }
            {
                ?search_result_uri ?predicate ?match .
                BIND (100 AS ?w)
                FILTER (LCASE(?match) = "$term")
            }
          UNION
            {
                ?search_result_uri ?predicate ?match .
                BIND (20 AS ?w)
                FILTER (REGEX(?match, "^$term", "i"))
            }
          UNION
            {
                ?search_result_uri ?predicate ?match .
                BIND (10 AS ?w)
                FILTER (REGEX(?match, "$term", "i"))
            }
        }
        GROUP BY ?search_result_uri ?predicate ?match
    }
        ORDER BY DESC(?weight)
"""


EXPECTED_FORMATTED = """\

SELECT ?search_result_uri ?predicate ?match ?weight (URI(CONCAT ("urn:hash:", SHA256(CONCAT (STR(?search_result_uri), STR(?predicate), STR(?match), STR(?weight))))) AS ?hashID)
WHERE {
    SELECT ?search_result_uri ?predicate ?match (SUM(?w) AS ?weight)
    WHERE {
        ?search_result_uri ?predicate ?match
        VALUES ?predicate {
            <bar>
        }
        {
            ?search_result_uri ?predicate ?match
            BIND (100  AS ?w) 
            FILTER (LCASE(?match)= "$term")
        }
        UNION {
            ?search_result_uri ?predicate ?match
            BIND (20  AS ?w) 
            FILTER (REGEX(?match, "^$term", "i"))
        }
        UNION {
            ?search_result_uri ?predicate ?match
            BIND (10  AS ?w) 
            FILTER (REGEX(?match, "$term", "i"))
        }
    }
    GROUP BY ?search_result_uri ?predicate ?match
}
ORDER BY DESC (?weight)"""


def test_example_query_formatting_regression():
    assert format_string(EXAMPLE_QUERY) == EXPECTED_FORMATTED

