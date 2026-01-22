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
    # A query that looks like Update but is actually a Select?
    # Or vice versa.
    # Let's craft a SELECT query that has UPDATE keywords in comments or strings,
    # but we want to force a WRONG guess.
    # Current logic: if has_update and not has_query -> update.
    # If has_query -> sparql.

    # So to fool it to think it's UPDATE, we need UPDATE keywords but NO query keywords.
    # But a valid query must have SELECT/CONSTRUCT/ASK/DESCRIBE.
    # So it's hard to make a valid Query that guesses Update.

    # Let's try to fool it to think it's QUERY but it's actually UPDATE.
    # Update with SELECT?
    # "INSERT { ?s ?p ?o } WHERE { SELECT ... }" is valid Update.
    # If it has SELECT, heuristic says "sparql".

    query = "INSERT { ?s ?p ?o } WHERE { SELECT ?s WHERE { ?s ?p ?o } }"
    # Heuristic sees INSERT and SELECT.
    # _guess_parser_type logic: if has_update and not has_query -> update. Else sparql.
    # So it returns 'sparql'.
    assert _guess_parser_type(query) == "sparql"

    # But this is an UPDATE query!
    # So 'sparql_parser.parse(query)' will FAIL.
    # Then it should fallback to 'sparql_update_parser.parse(query)', which should SUCCEED.

    result = format_string(query)
    assert "INSERT" in result
    assert "SELECT" in result


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
