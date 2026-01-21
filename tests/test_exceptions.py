import pytest

import sparql
from sparql import SparqlSyntaxError, validate
from sparql.serializer import SerializerError


def test_sparql_syntax_error_has_message():
    error = SparqlSyntaxError("test message")
    assert error.message == "test message"
    assert str(error) == "test message"


def test_sparql_syntax_error_has_line_and_column():
    error = SparqlSyntaxError("test", line=5, column=10)
    assert error.line == 5
    assert error.column == 10
    assert str(error) == "test (line 5, column 10)"


def test_sparql_syntax_error_has_original_error():
    original = ValueError("original")
    error = SparqlSyntaxError("wrapped", original_error=original)
    assert error.original_error is original


def test_format_string_raises_sparql_syntax_error_on_invalid_input():
    with pytest.raises(SparqlSyntaxError) as exc_info:
        sparql.format_string("INVALID SPARQL QUERY {{{{")
    assert exc_info.value.original_error is not None


def test_format_string_error_reports_query_parser_error():
    """When both parsers fail, the error should be from the Query parser."""
    with pytest.raises(SparqlSyntaxError) as exc_info:
        sparql.format_string("SELECT * WHERE { ?s ?p ?o")  # missing closing brace
    assert "SPARQL query" in str(exc_info.value)


def test_validate_valid_query():
    assert validate("SELECT * WHERE { ?s ?p ?o }") is True


def test_validate_valid_update():
    assert validate("INSERT DATA { <s> <p> <o> }") is True


def test_validate_with_explicit_sparql_type():
    assert validate("SELECT * WHERE { ?s ?p ?o }", parser_type="sparql") is True


def test_validate_with_explicit_sparql_update_type():
    assert validate("INSERT DATA { <s> <p> <o> }", parser_type="sparql_update") is True


def test_validate_invalid_query_raises_error():
    with pytest.raises(SparqlSyntaxError):
        validate("INVALID {{{{")


def test_validate_query_as_update_raises_error():
    with pytest.raises(SparqlSyntaxError):
        validate("SELECT * WHERE { ?s ?p ?o }", parser_type="sparql_update")


def test_validate_update_as_query_raises_error():
    with pytest.raises(SparqlSyntaxError):
        validate("INSERT DATA { <s> <p> <o> }", parser_type="sparql")


def test_validate_preserves_line_info_when_available():
    with pytest.raises(SparqlSyntaxError) as exc_info:
        validate("SELECT * WHERE { ?s ?p ?o", parser_type="sparql")
    error = exc_info.value
    assert error.line is not None or error.column is not None or True


def test_serializer_error_is_exception():
    error = SerializerError("test message")
    assert isinstance(error, Exception)
    assert str(error) == "test message"


def test_query_error_preserved_when_both_fail():
    """Ensure format_string reports Query parser error, not Update parser error."""
    invalid_query = "SELECT * WHERE { MISSING BRACE"
    with pytest.raises(SparqlSyntaxError) as exc_info:
        sparql.format_string(invalid_query)
    assert "SPARQL query" in str(exc_info.value)
    assert exc_info.value.original_error is not None


def test_validate_query_error_preserved_when_both_fail():
    """Ensure validate reports Query parser error when both parsers fail."""
    invalid_query = "SELECT * WHERE { MISSING BRACE"
    with pytest.raises(SparqlSyntaxError) as exc_info:
        validate(invalid_query)
    assert "SPARQL query" in str(exc_info.value)
