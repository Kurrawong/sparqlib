"""Tests for serializer extensibility through subclassing."""

from __future__ import annotations

from typing import Any

import pytest
from lark import Token, Tree

from sparqlkit.parser import sparql_query_parser
from sparqlkit.serializer import SparqlSerializer


class CustomSerializer(SparqlSerializer):
    """A custom serializer that uppercases all variables."""

    def _build_handler_map(self):
        # Get the base handler map
        handler_map = super()._build_handler_map()
        # Override the var handler
        handler_map["var"] = {"enter": CustomSerializer._custom_var_enter, "exit": None}
        return handler_map

    def _custom_var_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        """Custom handler that uppercases variables."""
        var_token = tree.children[0]
        assert isinstance(var_token, Token)
        self._parts.append(var_token.value.upper())
        self._parts.append(" ")
        return True


class ExtendedSerializer(SparqlSerializer):
    """A serializer that adds a custom prefix to NIL tokens."""

    def _build_handler_map(self):
        handler_map = super()._build_handler_map()
        handler_map["nil"] = {
            "enter": ExtendedSerializer._custom_nil_enter,
            "exit": None,
        }
        return handler_map

    def _custom_nil_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        """Custom handler that adds a comment before NIL."""
        self._parts.append("() ")  # Standard NIL output
        return True


def test_subclass_can_override_handler():
    """Verify a subclass can override existing handlers."""
    query = "SELECT ?x WHERE { ?x ?p ?o }"
    tree = sparql_query_parser.parse(query)

    # Base serializer should produce lowercase variables
    base_ser = SparqlSerializer()
    base_result = base_ser.visit_topdown(tree)
    assert "?x" in base_result
    assert "?X" not in base_result

    # Custom serializer should produce uppercase variables
    custom_ser = CustomSerializer()
    custom_result = custom_ser.visit_topdown(tree)
    assert "?X" in custom_result
    assert "?P" in custom_result
    assert "?O" in custom_result


def test_base_class_unaffected_by_subclass():
    """Verify base class maintains its handlers independently after subclass
    instantiation.
    """
    query = "SELECT ?x WHERE { ?s ?p ?o }"
    tree = sparql_query_parser.parse(query)

    # First create a custom serializer (this will populate _handler_cache for
    # CustomSerializer)
    custom_ser = CustomSerializer()
    custom_result = custom_ser.visit_topdown(tree)

    # Now create a base serializer - it should NOT use the custom handler
    base_ser = SparqlSerializer()
    base_result = base_ser.visit_topdown(tree)

    # Base result should have lowercase variables
    assert "?x" in base_result or "?s" in base_result
    # Custom result should have uppercase
    assert "?X" in custom_result or "?S" in custom_result


def test_multiple_subclasses_independent():
    """Verify multiple subclasses have independent handler maps."""
    query = "SELECT * WHERE { ?s ?p () }"  # Query with NIL
    tree = sparql_query_parser.parse(query)

    custom_ser = CustomSerializer()
    extended_ser = ExtendedSerializer()

    custom_result = custom_ser.visit_topdown(tree)
    extended_result = extended_ser.visit_topdown(tree)

    # Both should produce valid output
    assert "()" in custom_result
    assert "()" in extended_result

    # Extended serializer uses custom NIL handler
    # Custom serializer uses custom var handler
    assert "?S" in custom_result  # uppercase from CustomSerializer
    assert (
        "?s" in extended_result
    )  # lowercase from ExtendedSerializer (uses base var handler)


def test_handler_cache_efficiency():
    """Verify handler map is cached and not rebuilt for each instance."""
    # Clear the cache first
    SparqlSerializer._handler_cache.clear()

    # Create multiple instances
    ser1 = SparqlSerializer()
    ser2 = SparqlSerializer()
    ser3 = SparqlSerializer()

    # All should share the same handler map instance
    assert ser1._handler_map is ser2._handler_map
    assert ser2._handler_map is ser3._handler_map

    # Cache should only have one entry for the base class
    assert len(SparqlSerializer._handler_cache) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
