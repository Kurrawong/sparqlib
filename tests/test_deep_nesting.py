import sys

import pytest
from lark import Token, Tree

from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer
from sparql.serializer_iterative import IterativeSparqlSerializer


def iterative_tree_eq(t1, t2):
    stack = [(t1, t2)]
    while stack:
        n1, n2 = stack.pop()
        if type(n1) != type(n2):
            return False
        if isinstance(n1, Tree):
            if n1.data != n2.data or len(n1.children) != len(n2.children):
                return False
            for c1, c2 in zip(reversed(n1.children), reversed(n2.children)):
                stack.append((c1, c2))
        elif isinstance(n1, Token):
            if n1.type != n2.type or n1.value != n2.value:
                return False
        else:
            if n1 != n2:
                return False
    return True


def test_deeply_nested_optionals():
    depth = 1500  # Total depth will be around 3000-4500 frames
    query = (
        "SELECT * WHERE { " + "OPTIONAL { " * depth + "?s ?p ?o" + " } " * depth + "}"
    )

    # This should fail with recursive serializer if depth is large enough
    ser_rec = SparqlSerializer()
    tree = sparql_parser.parse(query)

    try:
        ser_rec.visit_topdown(tree)
        recursive_failed = False
    except RecursionError:
        recursive_failed = True
        print("\nRecursive serializer failed as expected with RecursionError")
    except Exception as e:
        # Some systems might have very large stack or fail differently
        recursive_failed = True
        print(f"\nRecursive serializer failed with {type(e).__name__}")

    # This should succeed with iterative serializer
    ser_iter = IterativeSparqlSerializer()
    result = ser_iter.visit_topdown(tree)
    # Remove all whitespace for comparison
    flat_result = "".join(result.split())
    assert "?s?p?o" in flat_result
    assert "OPTIONAL" in flat_result

    # Roundtrip check
    tree2 = sparql_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)
    print(f"Iterative serializer succeeded for depth {depth}")


def test_deeply_nested_expressions():
    depth = 2000
    query = "SELECT * WHERE { BIND(" + "(" * depth + "1 + 1" + ")" * depth + " AS ?x) }"
    tree = sparql_parser.parse(query)

    # Verify recursive fails
    ser_rec = SparqlSerializer()
    try:
        ser_rec.visit_topdown(tree)
    except RecursionError:
        print(
            "\nRecursive serializer failed as expected with RecursionError for expressions"
        )

    ser_iter = IterativeSparqlSerializer()
    result = ser_iter.visit_topdown(tree)
    flat_result = "".join(result.split())
    assert "1+1" in flat_result

    # Roundtrip
    tree2 = sparql_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)
    print(f"Iterative serializer succeeded for nested expressions depth {depth}")


def test_deeply_nested_unions():
    depth = 1000
    query = "SELECT * WHERE { " + "{ " * depth + "?s ?p ?o" + " } " * depth + "}"
    tree = sparql_parser.parse(query)

    # Verify recursive fails
    ser_rec = SparqlSerializer()
    try:
        ser_rec.visit_topdown(tree)
    except RecursionError:
        print(
            "\nRecursive serializer failed as expected with RecursionError for unions"
        )

    ser_iter = IterativeSparqlSerializer()
    result = ser_iter.visit_topdown(tree)
    flat_result = "".join(result.split())
    assert "?s?p?o" in flat_result

    # Roundtrip
    tree2 = sparql_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)
    print(f"Iterative serializer succeeded for nested unions depth {depth}")


def test_deeply_nested_subselects():
    depth = 500
    query = (
        "SELECT * WHERE { "
        + "{ SELECT * WHERE { " * depth
        + "?s ?p ?o"
        + " } } " * depth
        + "}"
    )
    tree = sparql_parser.parse(query)

    # Verify recursive fails
    ser_rec = SparqlSerializer()
    try:
        ser_rec.visit_topdown(tree)
    except RecursionError:
        print(
            "\nRecursive serializer failed as expected with RecursionError for subselects"
        )

    ser_iter = IterativeSparqlSerializer()
    result = ser_iter.visit_topdown(tree)
    flat_result = "".join(result.split())
    assert "?s?p?o" in flat_result

    # Roundtrip
    tree2 = sparql_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)
    print(f"Iterative serializer succeeded for nested subselects depth {depth}")


def test_complex_combined_nesting():
    # Combination of different types of nesting
    depth = 300
    # Nested graphs containing nested optionals containing nested expressions
    inner = "BIND( (1+1) AS ?x )"
    for _ in range(depth):
        inner = f"OPTIONAL {{ GRAPH ?g {{ {inner} }} }}"

    query = f"SELECT * WHERE {{ {inner} }}"
    tree = sparql_parser.parse(query)

    ser_iter = IterativeSparqlSerializer()
    result = ser_iter.visit_topdown(tree)

    # Roundtrip
    tree2 = sparql_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)
    print(f"Iterative serializer succeeded for complex combined nesting depth {depth}")


def test_get_value_deep_nesting():
    """Verify get_value handles deeply nested trees without RecursionError."""
    from lark import Token, Tree

    from sparql.serializer_base import get_value

    # Build a deeply nested tree structure (depth > Python recursion limit)
    depth = 2000  # Well beyond typical recursion limit of ~1000
    node = Token("VAR", "?x")
    for i in range(depth):
        node = Tree(f"level_{i}", [node])

    # This should NOT raise RecursionError
    tokens = get_value(node)

    # Verify we collected the token
    assert len(tokens) == 1
    assert tokens[0].value == "?x"
    print(f"get_value successfully handled depth {depth}")


if __name__ == "__main__":
    pytest.main([__file__])
