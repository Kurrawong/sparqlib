import re

import pytest

import sparql


def _assert_has_comment_line(output: str, comment: str) -> None:
    # Ensure it's emitted as a standalone line (not inline).
    assert any(line.strip() == comment for line in output.splitlines())


class TestCommentsPreserved:
    def test_prologue_comments_preserved_and_parses(self):
        query = (
            "# top comment\n"
            "PREFIX ex: <http://example.org/>\n"
            "# between prologue and query\n"
            "SELECT * WHERE { ?s ?p ?o }\n"
        )

        formatted = sparql.format_string(query, preserve_comments=True)
        _assert_has_comment_line(formatted, "# top comment")
        _assert_has_comment_line(formatted, "# between prologue and query")

        # Round-trip: formatted output should still parse.
        sparql.parse(formatted)

    def test_where_comments_preserved_near_graph_patterns(self):
        query = (
            "SELECT * WHERE {\n"
            "  ?s ?p ?o .\n"
            "  # before optional\n"
            "  OPTIONAL { ?s ?p2 ?o2 }\n"
            "  # before filter\n"
            "  FILTER(?o = 1)\n"
            "}\n"
        )

        formatted = sparql.format_string(query, preserve_comments=True)
        _assert_has_comment_line(formatted, "# before optional")
        _assert_has_comment_line(formatted, "# before filter")
        sparql.parse(formatted)

    def test_eof_comment_preserved(self):
        query = "SELECT * WHERE { ?s ?p ?o }\n# end"
        formatted = sparql.format_string(query, preserve_comments=True)
        _assert_has_comment_line(formatted, "# end")
        sparql.parse(formatted)

    def test_stability_format_twice_keeps_comments(self):
        query = (
            "SELECT * WHERE {\n"
            "  ?s ?p ?o .\n"
            "  # keep me\n"
            "  OPTIONAL { ?s ?p2 ?o2 }\n"
            "}\n"
        )
        formatted1 = sparql.format_string(query, preserve_comments=True)
        formatted2 = sparql.format_string(formatted1, preserve_comments=True)

        assert formatted2.count("# keep me") == 1
        sparql.parse(formatted2)

    def test_ast_path_preserve_comments_toggle_in_serialize(self):
        query = "SELECT * WHERE { # c\n ?s ?p ?o }\n"

        tree = sparql.parse(query, preserve_comments=True)

        with_comments = sparql.serialize(tree, preserve_comments=True)
        assert "# c" in with_comments

        without_comments = sparql.serialize(tree, preserve_comments=False)
        assert "# c" not in without_comments

    def test_indentation_preserved_for_nested_select_with_anchored_comment(self):
        query = (
            "prefix ex:  <http://www.example.org/schema#>\n"
            "prefix in:  <http://www.example.org/instance#>\n"
            "\n"
            "select ?x where {\n"
            "graph ?g {\n"
            "# test comment\n"
            "  {select ?x where {?x ?p ?g}}\n"
            "}\n"
            "}\n"
        )

        formatted = sparql.format_string(query)
        # Inner SELECT should be indented (it appears under GRAPH -> { -> subselect).
        assert "\n            SELECT ?x\n" in formatted

    def test_inline_comments_roundtrip_stay_inline(self):
        query = (
            "PREFIX ex: <http://www.example.org/schema#>\n"
            "PREFIX in: <http://www.example.org/instance#>\n"
            "\n"
            "SELECT ?x # test\n"
            "WHERE { # test\n"
            "    ?x ?p  ?g\n"
            "    FILTER (?x != in:i1) # test\n"
            "}\n"
        )

        formatted = sparql.format_string(query)
        assert formatted.strip("\n") == query.strip("\n")

    def test_prefix_spacing_and_standalone_comment_indentation(self):
        query = (
            "PREFIX ex: <http://www.example.org/schema#>\n"
            "PREFIX in: <http://www.example.org/instance#>\n"
            "# Test\n"
            "SELECT ?x # test\n"
            "WHERE { # test\n"
            "# test\n"
            "    ?x ?p  ?g\n"
            "    FILTER (?x != in:i1) # test\n"
            "}\n"
        )

        expected = (
            "PREFIX ex: <http://www.example.org/schema#>\n"
            "PREFIX in: <http://www.example.org/instance#>\n"
            "\n"
            "# Test\n"
            "SELECT ?x # test\n"
            "WHERE { # test\n"
            "    # test\n"
            "    ?x ?p  ?g\n"
            "    FILTER (?x != in:i1) # test\n"
            "}"
        )

        assert sparql.format_string(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        "INSERT DATA { # c\n <s> <p> <o> }",
        "DELETE WHERE { # c\n ?s ?p ?o }",
    ],
)
def test_update_comments_preserved(query: str):
    formatted = sparql.format_string(query, preserve_comments=True)
    assert "# c" in formatted
    sparql.parse(formatted)
