from sparqlkit import parse_query, serialize


def test_inline_eof_comment_preserved_after_closing_brace():
    query = "SELECT * WHERE { FILTER (?x < 10) } # comment"
    tree = parse_query(query)
    serialized = serialize(tree)
    assert "# comment" in serialized
