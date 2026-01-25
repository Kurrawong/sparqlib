from pathlib import Path
from typing import Any

import lark
import pytest

from sparqlkit import normalize_keyword_tokens
from sparqlkit.parser import sparql_query_parser, sparql_update_parser
from sparqlkit.serializer import SparqlSerializer

TEST_DIR = Path(__file__).parent


def assert_trees_equal(
    t1: lark.Tree[Any] | lark.Token, t2: lark.Tree[Any] | lark.Token
) -> None:
    """Iteratively assert that two Lark trees/tokens are equal."""
    stack = [(t1, t2)]
    while stack:
        n1, n2 = stack.pop()

        if type(n1) is not type(n2):
            assert n1 == n2  # This will fail and show the type mismatch

        if isinstance(n1, lark.Token):
            assert n1 == n2
        elif isinstance(n1, lark.Tree):
            # n2 is guaranteed to be a Tree here because of the type check above
            assert isinstance(n2, lark.Tree)
            assert n1.data == n2.data
            assert len(n1.children) == len(n2.children)
            for c1, c2 in zip(n1.children, n2.children, strict=True):
                stack.append((c1, c2))


@pytest.fixture
def test_roundtrip():
    def _test_roundtrip(filename: str):
        with open(filename, encoding="utf-8") as file:
            query = file.read()

            parser = sparql_query_parser
            try:
                tree = parser.parse(query)
            except (
                lark.exceptions.UnexpectedCharacters,
                lark.exceptions.UnexpectedInput,
            ):
                parser = sparql_update_parser
                tree = parser.parse(query)

            sparql_serializer = SparqlSerializer()
            sparql_serializer.visit_topdown(tree)

            new_tree = parser.parse(sparql_serializer.result)
            normalized_tree = normalize_keyword_tokens(tree)
            normalized_new_tree = normalize_keyword_tokens(new_tree)
            assert_trees_equal(normalized_tree, normalized_new_tree)

    return _test_roundtrip
