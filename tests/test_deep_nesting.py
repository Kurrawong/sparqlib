"""Tests for serializer handling of deeply nested SPARQL structures.

These tests verify that the iterative serializer can handle nesting depths
well beyond Python's default recursion limit.
"""

import pytest
from lark import Token, Tree

from sparqlkit import normalize_keyword_tokens
from sparqlkit.parser import sparql_query_parser
from sparqlkit.serializer import SparqlSerializer, get_value


def iterative_tree_eq(t1, t2):
    """Iteratively compare two trees for equality."""
    stack = [(t1, t2)]
    while stack:
        n1, n2 = stack.pop()
        if type(n1) is not type(n2):
            return False
        if isinstance(n1, Tree):
            if n1.data != n2.data or len(n1.children) != len(n2.children):
                return False
            for c1, c2 in zip(
                reversed(n1.children), reversed(n2.children), strict=True
            ):
                stack.append((c1, c2))
        elif isinstance(n1, Token):
            if n1.type != n2.type or n1.value != n2.value:
                return False
        else:
            if n1 != n2:
                return False
    return True


def test_deeply_nested_optionals():
    """Test serializer handles deeply nested OPTIONAL clauses."""
    depth = 1500
    query = (
        "SELECT * WHERE { " + "OPTIONAL { " * depth + "?s ?p ?o" + " } " * depth + "}"
    )
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)

    # Remove all whitespace for comparison
    flat_result = "".join(result.split())
    assert "?s?p?o" in flat_result
    assert "OPTIONAL" in flat_result

    # Roundtrip check
    tree2 = sparql_query_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)


def test_deeply_nested_expressions():
    """Test serializer handles deeply nested bracket expressions."""
    depth = 2000
    query = "SELECT * WHERE { BIND(" + "(" * depth + "1 + 1" + ")" * depth + " AS ?x) }"
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    flat_result = "".join(result.split())
    assert "1+1" in flat_result

    # Roundtrip
    tree2 = sparql_query_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)


def test_deeply_nested_unions():
    """Test serializer handles deeply nested group graph patterns."""
    depth = 1000
    query = "SELECT * WHERE { " + "{ " * depth + "?s ?p ?o" + " } " * depth + "}"
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    flat_result = "".join(result.split())
    assert "?s?p?o" in flat_result

    # Roundtrip
    tree2 = sparql_query_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)


def test_deeply_nested_subselects():
    """Test serializer handles deeply nested subselects."""
    depth = 500
    query = (
        "SELECT * WHERE { "
        + "{ SELECT * WHERE { " * depth
        + "?s ?p ?o"
        + " } } " * depth
        + "}"
    )
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)
    flat_result = "".join(result.split())
    assert "?s?p?o" in flat_result

    # Roundtrip
    tree2 = sparql_query_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)


def test_complex_combined_nesting():
    """Test serializer handles complex combined nesting patterns."""
    depth = 300
    inner = "BIND( (1+1) AS ?x )"
    for _ in range(depth):
        inner = f"OPTIONAL {{ GRAPH ?g {{ {inner} }} }}"

    query = f"SELECT * WHERE {{ {inner} }}"
    tree = sparql_query_parser.parse(query)

    serializer = SparqlSerializer()
    result = serializer.visit_topdown(tree)

    # Roundtrip
    tree2 = sparql_query_parser.parse(result)
    assert iterative_tree_eq(tree, tree2)


def test_get_value_deep_nesting():
    """Verify get_value handles deeply nested trees without RecursionError."""
    # Build a deeply nested tree structure (depth > Python recursion limit)
    depth = 2000
    node = Token("VAR", "?x")
    for i in range(depth):
        node = Tree(f"level_{i}", [node])

    # This should NOT raise RecursionError
    tokens = get_value(node)

    # Verify we collected the token
    assert len(tokens) == 1
    assert tokens[0].value == "?x"


def test_normalize_keyword_tokens_deep_tree():
    depth = 2000
    node = Token("KEYWORD", " select ")
    for i in range(depth):
        node = Tree(f"level_{i}", [node])

    normalized = normalize_keyword_tokens(node)
    current = normalized
    while isinstance(current, Tree):
        current = current.children[0]

    assert isinstance(current, Token)
    assert current.value == " SELECT "


if __name__ == "__main__":
    pytest.main([__file__])
