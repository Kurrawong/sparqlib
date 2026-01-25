import pytest

from sparqlkit import SparqlSyntaxError, format_string, parse, validate


def test_format_string_handles_query_and_update():
    query = "SELECT * WHERE { ?s ?p ?o }"
    update = "INSERT DATA { <s> <p> <o> }"

    assert "SELECT" in format_string(query)
    assert "INSERT DATA" in format_string(update)


def test_parse_unit_returns_unit_root():
    tree = parse("SELECT * WHERE { ?s ?p ?o }")
    assert tree.data == "unit"
    assert tree.children[0].data == "query_unit"

    update_tree = parse("INSERT DATA { <s> <p> <o> }")
    assert update_tree.data == "unit"
    assert update_tree.children[0].data == "update_unit"


def test_validate_uses_unified_parser():
    assert validate("INSERT DATA { <s> <p> <o> }") is True
    assert validate("SELECT * WHERE { ?s ?p ?o }") is True

    with pytest.raises(SparqlSyntaxError):
        validate("NOT A QUERY")
