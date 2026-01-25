import pytest

import sparqlkit


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

        formatted = sparqlkit.format_string(query, preserve_comments=True)
        _assert_has_comment_line(formatted, "# top comment")
        _assert_has_comment_line(formatted, "# between prologue and query")

        # Round-trip: formatted output should still parse.
        sparqlkit.parse(formatted)

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

        formatted = sparqlkit.format_string(query, preserve_comments=True)
        _assert_has_comment_line(formatted, "# before optional")
        _assert_has_comment_line(formatted, "# before filter")
        sparqlkit.parse(formatted)

    def test_eof_comment_preserved(self):
        query = "SELECT * WHERE { ?s ?p ?o }\n# end"
        formatted = sparqlkit.format_string(query, preserve_comments=True)
        _assert_has_comment_line(formatted, "# end")
        sparqlkit.parse(formatted)

    def test_stability_format_twice_keeps_comments(self):
        query = (
            "SELECT * WHERE {\n"
            "  ?s ?p ?o .\n"
            "  # keep me\n"
            "  OPTIONAL { ?s ?p2 ?o2 }\n"
            "}\n"
        )
        formatted1 = sparqlkit.format_string(query, preserve_comments=True)
        formatted2 = sparqlkit.format_string(formatted1, preserve_comments=True)

        assert formatted2.count("# keep me") == 1
        sparqlkit.parse(formatted2)

    def test_ast_path_preserve_comments_toggle_in_serialize(self):
        query = "SELECT * WHERE { # c\n ?s ?p ?o }\n"

        tree = sparqlkit.parse(query, preserve_comments=True)

        with_comments = sparqlkit.serialize(tree, preserve_comments=True)
        assert "# c" in with_comments

        without_comments = sparqlkit.serialize(tree, preserve_comments=False)
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

        formatted = sparqlkit.format_string(query)
        # Inner SELECT should be indented (it appears under GRAPH -> { -> subselect).
        # With 2-space indent default, 3 levels = 6 spaces.
        assert "\n      SELECT ?x\n" in formatted

    def test_inline_comments_roundtrip_stay_inline(self):
        query = (
            "PREFIX ex: <http://www.example.org/schema#>\n"
            "PREFIX in: <http://www.example.org/instance#>\n"
            "\n"
            "SELECT ?x # test\n"
            "WHERE { # test\n"
            "  ?x ?p ?g\n"
            "  FILTER (?x != in:i1) # test\n"
            "}\n"
        )

        formatted = sparqlkit.format_string(query)
        assert formatted.strip("\n") == query.strip("\n")

    def test_prefix_spacing_and_standalone_comment_indentation(self):
        query = (
            "PREFIX ex: <http://www.example.org/schema#>\n"
            "PREFIX in: <http://www.example.org/instance#>\n"
            "# Test\n"
            "SELECT ?x # test\n"
            "WHERE { # test\n"
            "# test\n"
            "  ?x ?p ?g\n"
            "  FILTER (?x != in:i1) # test\n"
            "}\n"
        )

        expected = (
            "PREFIX ex: <http://www.example.org/schema#>\n"
            "PREFIX in: <http://www.example.org/instance#>\n"
            "\n"
            "# Test\n"
            "SELECT ?x # test\n"
            "WHERE { # test\n"
            "  # test\n"
            "  ?x ?p ?g\n"
            "  FILTER (?x != in:i1) # test\n"
            "}"
        )

        assert sparqlkit.format_string(query) == expected

    def test_inline_comments_after_semicolons_keep_semicolons_inline(self):
        query = (
            "PREFIX addr: <https://linked.data.gov.au/def/addr/>\n"
            "PREFIX la: <https://linked.data.gov.au/def/location-addressing/>\n"
            "PREFIX sdo: <https://schema.org/>\n"
            "SELECT (COUNT(DISTINCT ?iri) AS ?count)\n"
            "WHERE {\n"
            "  GRAPH ?g {\n"
            "    ?cr a la:ChangeRequest ;\n"
            "      sdo:additionalType addr:Address ; # specify the resource type\n"
            "      sdo:actionStatus "
            "<https://linked.data.gov.au/def/location-addressing/status/accepted>"
            " ; # specify the change request status\n"
            "      sdo:object ?iri .\n"
            "  }\n"
            "}\n"
        )

        expected = (
            "PREFIX addr: <https://linked.data.gov.au/def/addr/>\n"
            "PREFIX la: <https://linked.data.gov.au/def/location-addressing/>\n"
            "PREFIX sdo: <https://schema.org/>\n"
            "\n"
            "SELECT (COUNT(DISTINCT ?iri) AS ?count)\n"
            "WHERE {\n"
            "  GRAPH ?g {\n"
            "    ?cr a la:ChangeRequest ;\n"
            "      sdo:additionalType addr:Address ; # specify the resource type\n"
            "      sdo:actionStatus "
            "<https://linked.data.gov.au/def/location-addressing/status/accepted>"
            " ; # specify the change request status\n"
            "      sdo:object ?iri\n"
            "  }\n"
            "}"
        )

        formatted = sparqlkit.format_string(query, preserve_comments=True)
        assert formatted == expected
        sparqlkit.parse(formatted)


@pytest.mark.parametrize(
    "query",
    [
        "INSERT DATA { # c\n <s> <p> <o> }",
        "DELETE WHERE { # c\n ?s ?p ?o }",
    ],
)
def test_update_comments_preserved(query: str):
    formatted = sparqlkit.format_string(query, preserve_comments=True)
    assert "# c" in formatted
    sparqlkit.parse(formatted)
