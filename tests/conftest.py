from pathlib import Path

import lark
import pytest

from sparql.parser import sparql_parser, sparql_update_parser
from sparql.serializer import SparqlSerializer

TEST_DIR = Path(__file__).parent


@pytest.fixture
def test_roundtrip():
    def _test_roundtrip(filename: str):
        with open(filename, "r", encoding="utf-8") as file:
            query = file.read()

            parser = sparql_parser
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
            assert tree == new_tree

    return _test_roundtrip
