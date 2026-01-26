# SPARQLKit

This package provides parsers and serializers for the [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/).

Note: This is not a SPARQL processing engine.

## Install

```shell
pip install sparqlkit
```

For CLI support:

```shell
pip install sparqlkit[cli]
```

## CLI

SPARQLKit provides a command-line interface for formatting SPARQL files.

```shell
sparql --help
sparql -h
```

### Commands

#### format

Format SPARQL files in-place:

```shell
sparql format path/to/query.rq
sparql format path/to/directory/
```

Check if files are formatted without making changes:

```shell
sparql format --check path/to/query.rq
```

## Usage

```python
import sparqlkit

query = r'''
PREFIX : <http://www.example.org/>
SELECT * WHERE { ?s ?p ?o }
'''

# Use the convenience function
formatted = sparqlkit.format_string(query)
print(formatted)
```

### Statement type detection

Determine the type and sub-type of a SPARQL statement:

```python
import sparqlkit

# From a statement string
result = sparqlkit.statement_type_from_string("SELECT * WHERE { ?s ?p ?o }")
print(result.type)     # SparqlType.QUERY
print(result.subtype)  # QuerySubType.SELECT

# From a parsed tree
tree = sparqlkit.parse("INSERT DATA { <s> <p> <o> }")
result = sparqlkit.statement_type(tree)
print(result.type)     # SparqlType.UPDATE
print(result.subtype)  # UpdateSubType.INSERT_DATA
```

Supported query sub-types: `SELECT`, `CONSTRUCT`, `DESCRIBE`, `ASK`

Supported update sub-types: `INSERT_WHERE`, `INSERT_DATA`, `DELETE_WHERE`, `DELETE_DATA`, `MODIFY`, `DROP`, `CLEAR`, `LOAD`, `CREATE`, `ADD`, `MOVE`, `COPY`

Note: `MODIFY` includes both `INSERT` and `DELETE` operations. E.g., `DELETE {…} INSERT {…} WHERE {…}`

### Preserving comments

Comments are preserved end-to-end through `format_string` and `parse`/`serialize` by default.
To disable comment preservation, use `preserve_comments=False`:

```python
import sparqlkit

query = "SELECT * WHERE { # comment\n  ?s ?p ?o }\n"
formatted = sparqlkit.format_string(query)
print(formatted)

tree = sparqlkit.parse(query)
print(sparqlkit.serialize(tree))

no_comments = sparqlkit.format_string(query, preserve_comments=False)
print(no_comments)
```

Notes:

- Comments are preserved using **stable anchoring** (nearby-token association), not exact original spacing.
- Comments are emitted as **standalone lines** by default for safety, but common inline forms are preserved:
  - `SELECT ?x # comment` (inline after a token)
  - `WHERE { # comment` (inline after `{`)
  - `FILTER(... ) # comment` (inline after `)`)

For advanced usage with the AST:

```python
from sparqlkit.parser import sparql_query_parser
from sparqlkit.serializer import SparqlSerializer

tree = sparql_query_parser.parse(query)
serializer = SparqlSerializer()
result = serializer.visit_topdown(tree)
print(result)
```

## Features

### Iterative Stack-Based Serializer

The SPARQL serializer uses an iterative stack-based approach, allowing serialization of queries with arbitrary complexity and nesting depth (e.g., 1500+ nested OPTIONALs) without triggering Python's `RecursionError`.

#### Deep Nesting Example

```python
from sparqlkit.parser import sparql_query_parser
from sparqlkit.serializer import SparqlSerializer

# Create a deeply nested query string
depth = 2000
query = "SELECT * WHERE { " + ("OPTIONAL { " * depth) + "?s ?p ?o" + (" }" * depth) + " }"

# Parse and serialize (no RecursionError)
tree = sparql_query_parser.parse(query)
serializer = SparqlSerializer()
result = serializer.visit_topdown(tree)
print(f"Successfully serialized query with nesting depth {depth}")
```

### Extensibility

The serializer can be extended through subclassing to customize output:

```python
from sparqlkit.serializer import SparqlSerializer
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
