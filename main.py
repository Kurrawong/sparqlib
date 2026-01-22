from sparql import format_string
from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer

query = r"""
prefix ex:	<http://www.example.org/schema#>
prefix in:	<http://www.example.org/instance#>

select ?x where {
graph ?g {
  {select ?x where {?x ?p ?g}}
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
print(f"\nQuery is the same: {tree == new_tree}")
assert tree == new_tree
