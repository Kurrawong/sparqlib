# Iterative SPARQL Serializer Architecture

This document describes the architecture of the iterative SPARQL serializer implemented in `sparql/serializer_iterative.py`.

## Background

The original SPARQL serializer was implemented using a recursive tree-walking approach (`Visitor_Recursive`). While simple and intuitive, it was limited by Python's recursion depth (default ~1000). For extremely large or deeply nested SPARQL queries, this would result in a `RecursionError`.

The iterative serializer replaces the recursive call stack with an explicit stack managed within the serializer. This allows for queries of arbitrary depth, limited only by available memory.

## Core Design

The serializer uses a two-phase top-down traversal of the Lark AST.

### 1. Stack-Based Traversal

The traversal is managed by a `while` loop that pops frames from an explicit stack. Each frame consists of:
- `node`: The Lark `Tree` or `Token` to process.
- `phase`: Either `ENTER` or `EXIT`.
- `context`: An optional dictionary for passing state down the tree.

#### Traversal Flow Diagram

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

Instead of using method dispatch based on name (like `visit_<node_name>`), the iterative serializer uses a pre-computed `_handler_map`. This map associates each `Tree` data type with a `TreeHandler` containing:
- `enter`: A method called before processing children.
- `exit`: A method called after processing children.

```python
class TreeHandler(NamedTuple):
    enter: Optional[Callable]
    exit: Optional[Callable]
```

To optimize performance, the `_handler_map` is cached at the class level and uses unbound methods, passing `self` explicitly.

### 3. Traversal Phases

For each `Tree` node:
1. **ENTER**: The `enter` handler is called.
2. If `enter` returns `True`, children are skipped (handled by the handler itself).
3. If `enter` returns `False` or `None`, an `EXIT` frame for the current node is pushed to the stack, followed by all children in reverse order (to ensure left-to-right processing when popped).
4. **EXIT**: After all children have been processed, the `exit` frame is popped and the `exit` handler is called.

For each `Token`:
- It is processed immediately by `_handle_token`, which appends its value to the result list.

### 4. String Building

The serializer avoids repeated string concatenation (`+=`), which is O(n^2) in some Python versions. Instead, it maintains a list of string parts (`_parts`) and joins them once at the end (`".join(self._parts)`), which is O(n).

## Extending the Serializer

You can extend the `IterativeSparqlSerializer` to handle custom AST nodes or override existing behavior.

### Example: Custom Handler

```python
from sparql.serializer_iterative import IterativeSparqlSerializer
from lark import Tree

class MySerializer(IterativeSparqlSerializer):
    def _build_handler_map(self):
        # Get default map
        handlers = super()._build_handler_map()
        
        # Add custom handler
        handlers["my_custom_node"] = {
            "enter": self.__class__._my_node_enter,
            "exit": None
        }
        return handlers

    def _my_node_enter(self, tree: Tree, context: dict) -> bool:
        self._parts.append("CUSTOM_START ")
        # Return False to process children normally
        return False
```

## Performance Characteristics

- **Initialization**: Caching the `_handler_map` at the class level significantly reduces instance creation time.
- **Traversal**: The iterative approach is comparable to or faster than recursion for small queries, and significantly faster for deep/large queries.
- **Memory**: Memory usage is generally lower than recursion because we avoid the overhead of Python stack frames for every node.

## Comparison Table

| Feature | Recursive Serializer | Iterative Serializer |
|---------|----------------------|----------------------|
| Max Depth | ~1000 (Python limit) | Arbitrary (Memory limit) |
| Performance | Good (Small queries) | Excellent (All sizes) |
| Stability | Risk of RecursionError| Very High |
| Output | Identical | Identical |
| API | Deprecated | Recommended |
