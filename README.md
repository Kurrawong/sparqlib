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
from sparql.serializer_iterative import IterativeSparqlSerializer

tree = sparql_parser.parse(query)
serializer = IterativeSparqlSerializer()
result = serializer.visit_topdown(tree)
print(result)
```

## Features

### Iterative Serializer
As of version 0.3.0, the SPARQL serializer has been refactored to use an iterative stack-based approach. This allows serializing queries of arbitrary complexity and nesting depth (e.g., 1500+ nested OPTIONALs) that would previously trigger a `RecursionError` in Python.

#### Deep Nesting Example
The following example demonstrates a query depth that works with the new serializer but would fail with the old one:

```python
from sparql.parser import sparql_parser
from sparql.serializer_iterative import IterativeSparqlSerializer

# Create a deeply nested query string
depth = 2000
query = "SELECT * WHERE { " + ("OPTIONAL { " * depth) + "?s ?p ?o" + (" }" * depth) + " }"

# Parse and serialize (no RecursionError)
tree = sparql_parser.parse(query)
serializer = IterativeSparqlSerializer()
result = serializer.visit_topdown(tree)
print(f"Successfully serialized query with nesting depth {depth}")
```

### Performance
The iterative serializer is highly optimized for performance and maintains character-for-character parity with the original recursive version.

## Migration Guide

The original `SparqlSerializer` is now deprecated and will be removed in a future version. 

To migrate:
1. Replace `from sparql.serializer import SparqlSerializer` with `from sparql.serializer_iterative import IterativeSparqlSerializer`.
2. The API remains the same: `serializer.visit_topdown(tree)` followed by `serializer.result`.
3. If you use `sparql.format_string()`, no changes are needed as it uses the iterative version by default.

## Conformance

The parser and serializer is passing all 1,070+ tests including those from the https://github.com/w3c/rdf-tests repository.

Previously, some extremely large queries would fail due to recursion limits. These are now fully supported by the iterative serializer.
