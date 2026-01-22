from sparql import format_string, normalize_keyword_tokens
from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer

query = r"""
prefix ex:	<http://www.example.org/schema#>
prefix in:	<http://www.example.org/instance#>

select ?x where {
VALUES ?g { <urn:g1> <urn:g2> }
graph ?g {
  {select ?x where {?x ?p ?g filter(?x != in:i1)}}
}
}
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
