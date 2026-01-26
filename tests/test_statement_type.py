import pytest
from lark import Tree

from sparqlkit import (
    QuerySubType,
    SparqlStatementType,
    SparqlType,
    SparqlTypeError,
    UpdateSubType,
    parse,
    statement_type,
    statement_type_from_string,
)

# Query type tests


def test_select():
    query = "SELECT * WHERE { ?s ?p ?o }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.QUERY, QuerySubType.SELECT)


def test_construct():
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.QUERY, QuerySubType.CONSTRUCT)


def test_describe():
    query = "DESCRIBE <http://example.org>"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.QUERY, QuerySubType.DESCRIBE)


def test_ask():
    query = "ASK { ?s ?p ?o }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.QUERY, QuerySubType.ASK)


# Update type tests


def test_insert_data():
    query = "INSERT DATA { <s> <p> <o> }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.INSERT_DATA)


def test_delete_data():
    query = "DELETE DATA { <s> <p> <o> }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.DELETE_DATA)


def test_delete_where():
    query = "DELETE WHERE { ?s ?p ?o }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.DELETE_WHERE)


def test_insert_where():
    query = "INSERT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.INSERT_WHERE)


def test_delete_where_modify():
    query = "DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.DELETE_WHERE)


def test_modify():
    query = "DELETE { ?s ?p ?o } INSERT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.MODIFY)


def test_drop():
    query = "DROP ALL"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.DROP)


def test_clear():
    query = "CLEAR DEFAULT"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.CLEAR)


def test_load():
    query = "LOAD <http://example.org>"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.LOAD)


def test_create():
    query = "CREATE GRAPH <http://example.org>"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.CREATE)


def test_add():
    query = "ADD DEFAULT TO <http://example.org>"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.ADD)


def test_move():
    query = "MOVE DEFAULT TO <http://example.org>"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.MOVE)


def test_copy():
    query = "COPY DEFAULT TO <http://example.org>"
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.COPY)


# Tests with pre-parsed trees


def test_statement_type_from_parsed_tree():
    query = "SELECT * WHERE { ?s ?p ?o }"
    tree = parse(query)
    result = statement_type(tree)
    assert result == SparqlStatementType(SparqlType.QUERY, QuerySubType.SELECT)


def test_statement_type_from_update_tree():
    query = "INSERT DATA { <s> <p> <o> }"
    tree = parse(query)
    result = statement_type(tree)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.INSERT_DATA)


# Error handling tests


def test_invalid_tree_type():
    with pytest.raises(SparqlTypeError, match="Expected a Tree"):
        statement_type("not a tree")


def test_unexpected_root_node():
    invalid_tree = Tree("unknown_node", [])
    with pytest.raises(SparqlTypeError, match="Unexpected root node"):
        statement_type(invalid_tree)


def test_empty_unit_tree():
    invalid_tree = Tree("unit", [])
    with pytest.raises(SparqlTypeError, match="No query_unit or update_unit"):
        statement_type(invalid_tree)


# Tests with explicit parser_type


def test_query_with_sparql_parser():
    query = "SELECT * WHERE { ?s ?p ?o }"
    result = statement_type_from_string(query, parser_type="sparql")
    assert result == SparqlStatementType(SparqlType.QUERY, QuerySubType.SELECT)


def test_update_with_update_parser():
    query = "INSERT DATA { <s> <p> <o> }"
    result = statement_type_from_string(query, parser_type="sparql_update")
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.INSERT_DATA)


# Tests with prefixes


def test_select_with_prefix():
    query = """
    PREFIX ex: <http://example.org/>
    SELECT * WHERE { ?s ex:predicate ?o }
    """
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.QUERY, QuerySubType.SELECT)


def test_insert_data_with_prefix():
    query = """
    PREFIX ex: <http://example.org/>
    INSERT DATA { ex:s ex:p ex:o }
    """
    result = statement_type_from_string(query)
    assert result == SparqlStatementType(SparqlType.UPDATE, UpdateSubType.INSERT_DATA)


if __name__ == "__main__":
    pytest.main([__file__])
