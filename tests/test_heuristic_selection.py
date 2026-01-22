from unittest.mock import MagicMock, patch

import pytest

from sparql import (
    _guess_parser_type,
    format_string,
    sparql_parser,
    sparql_update_parser,
    validate,
)


def test_guess_parser_type_update():
    """Test that Update queries are correctly identified."""
    assert _guess_parser_type("INSERT DATA { <s> <p> <o> }") == "sparql_update"
    assert _guess_parser_type("DELETE WHERE { ?s ?p ?o }") == "sparql_update"
    assert _guess_parser_type("LOAD <http://example.com>") == "sparql_update"
    assert _guess_parser_type("CLEAR DEFAULT") == "sparql_update"
    assert _guess_parser_type("DROP ALL") == "sparql_update"
    assert _guess_parser_type("CREATE GRAPH <g>") == "sparql_update"
    # Case insensitive
    assert _guess_parser_type("insert data { }") == "sparql_update"


def test_guess_parser_type_query():
    """Test that Select/Construct queries are correctly identified."""
    assert _guess_parser_type("SELECT * WHERE { ?s ?p ?o }") == "sparql"
    assert _guess_parser_type("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }") == "sparql"
    assert _guess_parser_type("ASK { ?s ?p ?o }") == "sparql"
    assert _guess_parser_type("DESCRIBE ?s") == "sparql"
    # Default fallback
    assert _guess_parser_type("PREFIX : <http://example.org/>") == "sparql"
    # Variable names and prefixed names should not trigger update detection
    assert _guess_parser_type("SELECT ?INSERT WHERE { ?s ?p ?o }") == "sparql"
    assert _guess_parser_type("SELECT ?s WHERE { ?s :DELETE ?o }") == "sparql"
    # Prefix labels that match keywords should be ignored
    assert (
        _guess_parser_type("PREFIX select: <http://ex/> INSERT DATA { <s> <p> <o> }")
        == "sparql_update"
    )
    assert (
        _guess_parser_type("PREFIX delete: <http://ex/> SELECT * WHERE { ?s ?p ?o }")
        == "sparql"
    )


def test_guess_parser_type_ambiguous():
    """Test mixed keywords favor Query if ambiguous or standard."""
    # SELECT with INSERT inside a string or comment?
    # The heuristic checks for presence. If both present, it returns 'sparql'.
    query = "SELECT * WHERE { ?s ?p 'INSERT' }"
    assert _guess_parser_type(query) == "sparql"

    # Update query with SELECT in a string (should be identified as update)
    query_update = "INSERT DATA { <s> <p> 'SELECT' }"
    assert _guess_parser_type(query_update) == "sparql_update"


def test_guess_parser_type_triple_quoted_strings():
    """Test that keywords inside triple-quoted strings are ignored."""
    # Triple single-quoted string with INSERT keyword
    query = "SELECT * WHERE { ?s ?p '''INSERT DELETE''' }"
    assert _guess_parser_type(query) == "sparql"

    # Triple double-quoted string with INSERT keyword
    query2 = 'SELECT * WHERE { ?s ?p """INSERT DELETE""" }'
    assert _guess_parser_type(query2) == "sparql"

    # Triple-quoted string with internal unescaped quotes
    query3 = "SELECT * WHERE { ?s ?p '''It's INSERT time''' }"
    assert _guess_parser_type(query3) == "sparql"

    # Update with SELECT in triple-quoted string
    query4 = "INSERT DATA { <s> <p> '''SELECT CONSTRUCT''' }"
    assert _guess_parser_type(query4) == "sparql_update"

    # Multi-line triple-quoted string with keywords
    query5 = '''SELECT * WHERE { ?s ?p """
        INSERT
        DELETE
        DROP
    """ }'''
    assert _guess_parser_type(query5) == "sparql"


def test_format_string_uses_heuristic_success():
    """Test that format_string uses the heuristic and succeeds."""
    query = "INSERT DATA { <s> <p> <o> }"

    # We can patch the parsers to see which one is called first.
    # But since we want to test the *real* logic, we can verify it works.
    result = format_string(query)
    assert "INSERT DATA" in result


def test_format_string_fallback():
    """Test that if heuristic guesses wrong, it falls back to the other parser."""
    query = "INSERT { ?s ?p ?o } WHERE { SELECT ?s WHERE { ?s ?p ?o } }"

    with patch("sparql._guess_parser_type", return_value="sparql"):
        result = format_string(query)

    assert "INSERT" in result
    assert "SELECT" in result


def test_format_string_strict_rejects_fallback():
    """Test that strict mode does not try the secondary parser."""
    from sparql import SparqlSyntaxError

    query = "INSERT { ?s ?p ?o } WHERE { SELECT ?s WHERE { ?s ?p ?o } }"

    with patch("sparql._guess_parser_type", return_value="sparql"):
        with pytest.raises(SparqlSyntaxError):
            format_string(query, strict=True)


def test_strict_success_cases():
    """Test strict mode succeeds when heuristic is correct."""
    assert (
        format_string(
            "PREFIX select: <http://ex/> INSERT DATA { <s> <p> <o> }", strict=True
        )
        is not None
    )
    assert (
        format_string(
            "PREFIX delete: <http://ex/> SELECT * WHERE { ?s ?p ?o }",
            strict=True,
        )
        is not None
    )


def test_validate_heuristic():
    """Test validate uses the heuristic."""
    from sparql import SparqlSyntaxError

    # Update query
    assert validate("INSERT DATA { <s> <p> <o> }") is True
    # Query query
    assert validate("SELECT * WHERE { ?s ?p ?o }") is True

    # Invalid query
    with pytest.raises(SparqlSyntaxError):
        validate("NOT A QUERY")


def test_validate_strict_rejects_fallback():
    """Test validate strict mode does not try the secondary parser."""
    from sparql import SparqlSyntaxError

    query = "INSERT { ?s ?p ?o } WHERE { SELECT ?s WHERE { ?s ?p ?o } }"
    with patch("sparql._guess_parser_type", return_value="sparql"):
        with pytest.raises(SparqlSyntaxError):
            validate(query, strict=True)
