from sparqlkit import format_query, format_update


def test_update_with_insert_and_empty_where():
    query = 'WITH <g> INSERT { GRAPH <g> { <s> <p> "f\\"" . } } WHERE {}'
    result = format_update(query)
    assert result.startswith("WITH <g>\nINSERT {")
    assert "\nWHERE {}" in result
    assert "WHERE {\n" not in result


def test_select_empty_where_compact():
    result = format_query("select * where {}")
    assert "WHERE {}" in result
    assert "WHERE {\n" not in result


def test_select_asterisk_has_space_before_brace():
    result = format_query("select * { ?s ?p ?o } limit 10")
    assert "SELECT * {" in result
    assert "SELECT *{" not in result
