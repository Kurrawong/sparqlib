from sparqlkit import format_string, normalize_keyword_tokens
from sparqlkit.parser import sparql_parser
from sparqlkit.serializer import SparqlSerializer

query = r"""
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

print(f"Using serializer: {SparqlSerializer.__name__}")

# Original tree
tree = sparql_parser.parse(query)
print(f"Tree: {tree}")

# Format
formatted = format_string(query)
print(f"\nNew query:\n{formatted}")

# Parse back to verify
new_tree = sparql_parser.parse(formatted)
normalized_tree = normalize_keyword_tokens(tree)
normalized_new_tree = normalize_keyword_tokens(new_tree)
print(f"\nQuery is the same: {normalized_tree == normalized_new_tree}")
assert normalized_tree == normalized_new_tree

expected = """\
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
ORDER BY DESC (?weight)""".strip()

assert formatted == expected
