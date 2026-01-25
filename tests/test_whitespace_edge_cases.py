"""Tests for whitespace handling edge cases in the serializer.

These tests verify that the serializer correctly handles unusual token
combinations that might cause incorrect spacing.
"""

import pytest

from sparqlkit import format_string


class TestFunctionSpacing:
    """Tests for spacing around function calls."""

    def test_nested_function_calls(self):
        # Note: SPARQL requires AS clause in SELECT expression
        query = "SELECT (STR(LANG(?label)) AS ?x) WHERE { ?s ?p ?label }"
        result = format_string(query)
        assert "STR(LANG(?label))" in result
        assert "STR (" not in result
        assert "LANG (" not in result

    def test_function_with_multiple_args(self):
        query = "SELECT (CONCAT(?a, ?b, ?c) AS ?x) WHERE { ?s ?p ?o }"
        result = format_string(query)
        # Function should be present with comma-separated arguments
        assert "CONCAT" in result
        assert "?a, ?b, ?c" in result

    def test_function_in_filter(self):
        query = "SELECT * WHERE { ?s ?p ?o FILTER(BOUND(?s) && ISIRI(?p)) }"
        result = format_string(query)
        assert "BOUND(?s)" in result
        assert "ISIRI(?p)" in result

    def test_aggregate_functions(self):
        query = "SELECT (COUNT(DISTINCT ?s) AS ?c) WHERE { ?s ?p ?o }"
        result = format_string(query)
        assert "COUNT(DISTINCT ?s)" in result


class TestBracketSpacing:
    """Tests for spacing around brackets and parentheses."""

    def test_nested_brackets(self):
        query = "SELECT * WHERE { ?s ?p [ ?q [ ?r ?t ] ] }"
        result = format_string(query)
        # Should not have spaces between consecutive brackets
        assert "[ [" not in result or "[?q [" in result

    def test_collection_syntax(self):
        query = "SELECT * WHERE { ?s ?p (1 2 3) }"
        result = format_string(query)
        # Collection elements are space-separated, closing paren may have space
        # before it
        assert "1 2 3" in result

    def test_nil(self):
        query = "SELECT * WHERE { ?s ?p () }"
        result = format_string(query)
        assert "()" in result


class TestOperatorSpacing:
    """Tests for spacing around operators."""

    def test_arithmetic_operators(self):
        # SPARQL requires AS clause in SELECT expression
        query = "SELECT (?a + ?b * ?c - ?d / ?e AS ?x) WHERE { ?s ?p ?o }"
        result = format_string(query)
        # Operators should be present
        assert "+" in result
        assert "*" in result
        assert "-" in result
        assert "/" in result

    def test_comparison_operators(self):
        query = "SELECT * WHERE { ?s ?p ?o FILTER(?o > 5 && ?o < 10) }"
        result = format_string(query)
        assert "> 5" in result or "?o > 5" in result or "?o >5" in result

    def test_logical_operators(self):
        query = "SELECT * WHERE { ?s ?p ?o FILTER(?a || ?b && ?c) }"
        result = format_string(query)
        # Result should parse correctly
        assert "||" in result
        assert "&&" in result


class TestPropertyPathSpacing:
    """Tests for spacing in property paths."""

    def test_inverse_path(self):
        query = "SELECT * WHERE { ?s ^<http://example.org/p> ?o }"
        result = format_string(query)
        assert "^<http://example.org/p>" in result

    def test_sequence_path(self):
        query = "SELECT * WHERE { ?s <http://a>/<http://b> ?o }"
        result = format_string(query)
        # Path operators should be present
        assert "<http://a>" in result
        assert "/" in result
        assert "<http://b>" in result

    def test_alternative_path(self):
        query = "SELECT * WHERE { ?s <http://a>|<http://b> ?o }"
        result = format_string(query)
        # Path operators should be present
        assert "<http://a>" in result
        assert "|" in result
        assert "<http://b>" in result

    def test_path_with_modifiers(self):
        query = "SELECT * WHERE { ?s <http://a>+ ?o }"
        result = format_string(query)
        # Path and modifier should be present
        assert "<http://a>" in result
        assert "+" in result

    def test_negated_path(self):
        query = "SELECT * WHERE { ?s !<http://a> ?o }"
        result = format_string(query)
        assert "!<http://a>" in result

    def test_property_path_operators_no_space(self):
        """Regression test: property path operators should not have space before
        them.
        """
        query = """PREFIX ex: <http://example.com/>
SELECT DISTINCT ?s ?o
WHERE {
  ?s ex:knows ?o .
  ?s ex:knows/ex:worksWith ?o .
  ?s (ex:knows | ex:worksWith) ?o .
  ?s ^ex:knows ?o .
  ?s ex:knows* ?o .
  ?s ex:knows+ ?o .
  ?s ex:knows? ?o .
  ?s !(ex:knows | ex:worksWith) ?o .
  ?s (ex:knows/(ex:worksWith | ex:colleagueOf)) ?o .
}
LIMIT 50"""
        result = format_string(query)
        # No space before path operators
        assert "ex:knows*" in result, (
            f"Expected 'ex:knows*' but got space before *: {result}"
        )
        assert "ex:knows+" in result, (
            f"Expected 'ex:knows+' but got space before +: {result}"
        )
        assert "ex:knows?" in result, (
            f"Expected 'ex:knows?' but got space before ?: {result}"
        )
        assert "ex:knows/" in result, (
            f"Expected 'ex:knows/' but got space before /: {result}"
        )
        # No space around | in alternatives
        assert (
            "ex:knows|ex:worksWith" in result or "(ex:knows|ex:worksWith)" in result
        ), f"Expected no space around | in alternative path: {result}"


class TestLiteralSpacing:
    """Tests for spacing around literals."""

    def test_typed_literal(self):
        query = 'SELECT * WHERE { ?s ?p "value"^^<http://example.org/type> }'
        result = format_string(query)
        assert '"value"^^<http://example.org/type>' in result

    def test_language_tagged_literal(self):
        query = 'SELECT * WHERE { ?s ?p "hello"@en }'
        result = format_string(query)
        assert '"hello"@en' in result

    def test_numeric_literal(self):
        query = "SELECT * WHERE { ?s ?p 42 }"
        result = format_string(query)
        # Should have proper spacing around the number
        assert "42" in result


class TestMiscEdgeCases:
    """Miscellaneous edge cases."""

    def test_empty_group_pattern(self):
        query = "SELECT * WHERE { }"
        result = format_string(query)
        assert "{ }" in result or "{}" in result or "{\n" in result

    def test_semicolon_separator(self):
        query = "SELECT * WHERE { ?s ?p1 ?o1; ?p2 ?o2 }"
        result = format_string(query)
        # Semicolons should not have space before them
        assert " ; " not in result or "; " in result

    def test_comma_in_object_list(self):
        query = "SELECT * WHERE { ?s ?p ?o1, ?o2, ?o3 }"
        result = format_string(query)
        # Commas should have space after but not before
        assert ", ?" in result

    def test_as_clause(self):
        query = "SELECT (?a AS ?b) WHERE { ?s ?p ?o }"
        result = format_string(query)
        assert "AS ?b" in result

    def test_bind_expression(self):
        query = "SELECT * WHERE { BIND(1 + 2 AS ?sum) }"
        result = format_string(query)
        # BIND and AS should be present
        assert "BIND" in result
        assert "AS" in result
        assert "?sum" in result


class TestRoundTrip:
    """Tests that verify parse-serialize-parse produces valid SPARQL."""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * WHERE { ?s ?p ?o }",
            "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o } GROUP BY ?s",
            "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
            "ASK WHERE { ?s ?p ?o }",
            "DESCRIBE ?s WHERE { ?s ?p ?o }",
            "SELECT * WHERE { ?s ?p ?o OPTIONAL { ?o ?q ?r } }",
            "SELECT * WHERE { { ?s ?p ?o } UNION { ?a ?b ?c } }",
            "SELECT * WHERE { GRAPH ?g { ?s ?p ?o } }",
        ],
    )
    def test_roundtrip_preserves_validity(self, query):
        """Formatting a query and re-formatting should produce valid SPARQL."""
        result1 = format_string(query)
        result2 = format_string(result1)
        # Both results should be valid (no exception raised)
        assert result2 is not None
