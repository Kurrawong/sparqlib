# Python SPARQL

This package provides parsers and serializers for the [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/).

Note: This is not a SPARQL processing engine.

## Install

Replace `<version>` with the latest GitHub release.

```shell
pip install https://github.com/Kurrawong/sparql/archive/refs/tags/<version>.zip
```

## Usage

```python
import sparql

query = r'''
PREFIX : <http://www.example.org/>
SELECT * WHERE { ?s ?p ?o }
'''

# Use the convenience function
formatted = sparql.format_string(query)
print(formatted)
```

For advanced usage with the AST:

```python
from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer

tree = sparql_parser.parse(query)
serializer = SparqlSerializer()
result = serializer.visit_topdown(tree)
print(result)
```

## Features

### Iterative Stack-Based Serializer

The SPARQL serializer uses an iterative stack-based approach, allowing serialization of queries with arbitrary complexity and nesting depth (e.g., 1500+ nested OPTIONALs) without triggering Python's `RecursionError`.

#### Deep Nesting Example

```python
from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer

# Create a deeply nested query string
depth = 2000
query = "SELECT * WHERE { " + ("OPTIONAL { " * depth) + "?s ?p ?o" + (" }" * depth) + " }"

# Parse and serialize (no RecursionError)
tree = sparql_parser.parse(query)
serializer = SparqlSerializer()
result = serializer.visit_topdown(tree)
print(f"Successfully serialized query with nesting depth {depth}")
```

### Extensibility

The serializer can be extended through subclassing to customize output:

```python
from sparql.serializer import SparqlSerializer
from lark import Tree

class CustomSerializer(SparqlSerializer):
    def _build_handler_map(self):
        handlers = super()._build_handler_map()
        handlers["var"] = {"enter": CustomSerializer._custom_var_enter, "exit": None}
        return handlers

    def _custom_var_enter(self, tree: Tree, context: dict) -> bool:
        self._parts.append(tree.children[0].value.upper())
        self._parts.append(" ")
        return True
```

## Conformance

The parser and serializer passes all 1,070+ tests including those from the https://github.com/w3c/rdf-tests repository.
