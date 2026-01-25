"""Tests for the parse() and serialize() public API functions."""

import pytest
from lark import Tree

from sparqlkit import (
    SparqlSyntaxError,
    parse,
    parse_query,
    parse_update,
    serialize,
)


class TestParse:
    """Tests for the parse() function."""

    def test_parse_select_query(self):
        """Test parsing a SELECT query returns a Tree."""
        query = "SELECT * WHERE { ?s ?p ?o }"
        tree = parse(query)
        assert isinstance(tree, Tree)
        assert tree.data == "unit"
        assert tree.children[0].data == "query_unit"

    def test_parse_update(self):
        """Test parsing an UPDATE returns a Tree."""
        query = "INSERT DATA { <s> <p> <o> }"
        tree = parse(query)
        assert isinstance(tree, Tree)
        assert tree.data == "unit"
        assert tree.children[0].data == "update_unit"

    def test_parse_with_explicit_type(self):
        """Test parsing with explicit parser type."""
        query = "SELECT * WHERE { ?s ?p ?o }"
        tree = parse(query, parser_type="sparql")
        assert isinstance(tree, Tree)

    def test_parse_invalid_query_raises_error(self):
        """Test that invalid queries raise SparqlSyntaxError."""
        with pytest.raises(SparqlSyntaxError):
            parse("NOT A VALID QUERY")

    def test_parse_unified_unit_root(self):
        """Test unified parser returns a unit root."""
        update = "INSERT DATA { <s> <p> <o> }"
        tree = parse(update)
        assert tree.data == "unit"

    def test_parse_query_convenience(self):
        """Test parse_query convenience function."""
        query = "SELECT * WHERE { ?s ?p ?o }"
        tree = parse_query(query)
        assert isinstance(tree, Tree)
        assert tree.data == "query_unit"

    def test_parse_query_rejects_update(self):
        """Test parse_query rejects UPDATE statements."""
        with pytest.raises(SparqlSyntaxError):
            parse_query("INSERT DATA { <s> <p> <o> }")

    def test_parse_update_convenience(self):
        """Test parse_update convenience function."""
        update = "INSERT DATA { <s> <p> <o> }"
        tree = parse_update(update)
        assert isinstance(tree, Tree)
        assert tree.data == "update_unit"

    def test_parse_update_rejects_query(self):
        """Test parse_update rejects SELECT statements."""
        with pytest.raises(SparqlSyntaxError):
            parse_update("SELECT * WHERE { ?s ?p ?o }")


class TestSerialize:
    """Tests for the serialize() function."""

    def test_serialize_produces_string(self):
        """Test serializing a tree produces a string."""
        query = "SELECT * WHERE { ?s ?p ?o }"
        tree = parse(query)
        result = serialize(tree)
        assert isinstance(result, str)
        assert "SELECT" in result

    def test_round_trip_preserves_semantics(self):
        """Test that parse -> serialize -> parse produces equivalent AST."""
        query = "SELECT ?x ?y WHERE { ?x <http://example.org/p> ?y }"
        tree1 = parse(query)
        serialized = serialize(tree1)
        tree2 = parse(serialized)
        assert tree1.data == tree2.data

    def test_serialize_update(self):
        """Test serializing an UPDATE tree."""
        update = "INSERT DATA { <http://s> <http://p> <http://o> }"
        tree = parse(update)
        result = serialize(tree)
        assert "INSERT DATA" in result


class TestRoundTrip:
    """Integration tests for parse + serialize round-tripping."""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * WHERE { ?s ?p ?o }",
            "SELECT DISTINCT ?x WHERE { ?x a <http://example.org/Type> }",
            "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
            "ASK { ?s ?p ?o }",
            "DESCRIBE ?x WHERE { ?x a <http://example.org/Type> }",
            "PREFIX ex: <http://example.org/> SELECT * WHERE { ?s ex:p ?o }",
        ],
    )
    def test_query_round_trip(self, query):
        """Test various queries can be parsed and re-serialized."""
        tree = parse(query)
        result = serialize(tree)
        tree2 = parse(result)
        assert tree.data == tree2.data

    @pytest.mark.parametrize(
        "update",
        [
            "INSERT DATA { <s> <p> <o> }",
            "DELETE WHERE { ?s ?p ?o }",
            "DELETE { ?s ?p ?o } INSERT { ?s ?p2 ?o } WHERE { ?s ?p ?o }",
        ],
    )
    def test_update_round_trip(self, update):
        """Test various updates can be parsed and re-serialized."""
        tree = parse(update)
        result = serialize(tree)
        tree2 = parse(result)
        assert tree.data == tree2.data
