# SPARQL Serializer Architecture

This document describes the architecture of the SPARQL serializer implemented in `sparql/serializer.py`.

## Overview

The serializer uses an iterative stack-based approach to traverse and serialize Lark AST trees. This design avoids Python's recursion limit, allowing serialization of queries with arbitrary nesting depth.

## Core Design

### 1. Stack-Based Traversal

The traversal is managed by a `while` loop that pops frames from an explicit stack. Each frame consists of:
- `node`: The Lark `Tree` or `Token` to process.
- `phase`: Either `ENTER` or `EXIT`.
- `context`: An optional dictionary for passing state down the tree.

```
       +-------------------+
       |    Stack          |
       |                   |
       |  [Node A, ENTER]  | <--- Initial State
       +---------+---------+
                 |
                 v
       +-------------------+
       |   Pop Frame       |
       +---------+---------+
                 |
      Is Node a Tree or Token?
      /                    \
  Token                    Tree
    |                        |
Append value            Lookup Handler
to Output                    |
                    +--------v---------+
                    |   ENTER Handler  |
                    +--------+---------+
                             |
                   +---------v---------+
                   | Returns True?     |
                   | (Skip Children)   |
                   +----+---------+----+
                        |         |
                      Yes         No
                       |          |
                   Continue       v
                               +-----------------------+
                               | Push [Node A, EXIT]   |
                               | Push Children (Rev)   |
                               +-----------------------+
                                          |
                                          v
                                   (Loop continues)
                                          |
                                          v
                               +-----------------------+
                               |   EXIT Handler        |
                               | (After children proc) |
                               +-----------------------+
```

### 2. Handler Pattern

The serializer uses a pre-computed `_handler_map` that associates each `Tree` data type with handlers:
- `enter`: Called before processing children.
- `exit`: Called after processing children.

To optimize performance, the `_handler_map` is cached at the class level and uses unbound methods.

### 3. Traversal Phases

For each `Tree` node:
1. **ENTER**: The `enter` handler is called.
2. If `enter` returns `True`, children are skipped (handled by the handler itself).
3. If `enter` returns `False` or `None`, an `EXIT` frame is pushed, followed by all children in reverse order.
4. **EXIT**: After all children are processed, the `exit` handler is called.

For each `Token`:
- It is processed immediately by `_handle_token`, which appends its value to the result list.

### 4. String Building

The serializer avoids repeated string concatenation. It maintains a list of string parts (`_parts`) and joins them once at the end, which is O(n) instead of O(n²).

## Extending the Serializer

You can extend `SparqlSerializer` to handle custom AST nodes or override existing behavior:

```python
from sparql.serializer import SparqlSerializer
from lark import Tree

class MySerializer(SparqlSerializer):
    def _build_handler_map(self):
        handlers = super()._build_handler_map()
        handlers["my_custom_node"] = {
            "enter": self.__class__._my_node_enter,
            "exit": None
        }
        return handlers

    def _my_node_enter(self, tree: Tree, context: dict) -> bool:
        self._parts.append("CUSTOM_START ")
        return False  # Process children normally
```

## Performance Characteristics

- **Initialization**: The `_handler_map` is cached at the class level for fast instance creation.
- **Traversal**: The iterative approach handles queries of any depth without stack overflow.
- **Memory**: Memory usage is generally lower than recursion due to avoiding Python stack frame overhead.
