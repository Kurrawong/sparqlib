from sparql import format_string, get_serializer_info
from sparql.parser import sparql_parser

query = r"""
prefix ex:	<http://www.example.org/schema#>
prefix in:	<http://www.example.org/instance#>

select ?x where {
graph ?g {
  {select ?x where {?x ?p ?g}}
}
}
"""

print(f"Using serializer: {get_serializer_info()}")

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
