import pytest
from lark import Token, Tree

from sparqlkit.serializer import (
    SerializerError,
    _safe_get_child,
    get_iri,
    get_prefixed_name,
    get_rdf_literal,
    get_var,
)


def test_safe_get_child_raises_on_missing_children():
    node = Tree("test", [])
    with pytest.raises(SerializerError) as exc_info:
        _safe_get_child(node, 0)
    assert "out of range" in str(exc_info.value)


def test_safe_get_child_raises_on_wrong_type():
    node = Tree("test", [Token("VAR", "?x")])
    with pytest.raises(SerializerError) as exc_info:
        _safe_get_child(node, 0, expected_type=Tree, context="test_context")
    assert "Expected child of type Tree" in str(exc_info.value)
    assert "test_context" in str(exc_info.value)


def test_safe_get_child_includes_context_in_error():
    node = Tree("test", [])
    with pytest.raises(SerializerError) as exc_info:
        _safe_get_child(node, 0, context="my_context")
    assert "my_context" in str(exc_info.value)


def test_get_prefixed_name_raises_on_wrong_child_type():
    node = Tree("prefixed_name", [Tree("unexpected", [])])
    with pytest.raises(SerializerError) as exc_info:
        get_prefixed_name(node)
    assert "Expected child of type Token" in str(exc_info.value)


def test_get_var_raises_on_wrong_child_type():
    node = Tree("var", [Tree("unexpected", [])])
    with pytest.raises(SerializerError) as exc_info:
        get_var(node)
    assert "Expected child of type Token" in str(exc_info.value)


def test_get_iri_raises_on_empty_children():
    node = Tree("iri", [])
    with pytest.raises(SerializerError) as exc_info:
        get_iri(node)
    assert "no children" in str(exc_info.value)


def test_get_iri_raises_on_unexpected_child_type():
    node = Tree("iri", ["string_not_token_or_tree"])
    with pytest.raises(SerializerError) as exc_info:
        get_iri(node)
    assert "Unexpected iri child type" in str(exc_info.value)


def test_get_rdf_literal_raises_on_missing_string_node():
    node = Tree("rdf_literal", [])
    with pytest.raises(SerializerError) as exc_info:
        get_rdf_literal(node)
    assert "out of range" in str(exc_info.value)
