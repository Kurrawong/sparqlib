"""Regression tests for configurable indentation."""

import sparqlkit


class TestCustomIndent:
    """Tests for custom indent parameter across all formatting functions."""

    QUERY = "SELECT ?x WHERE { ?x ?p ?o }"
    UPDATE = "INSERT DATA { <s> <p> <o> }"

    def test_format_string_default_indent_is_two_spaces(self):
        formatted = sparqlkit.format_string(self.QUERY)
        assert "\n  ?x ?p ?o\n" in formatted

    def test_format_string_custom_four_space_indent(self):
        formatted = sparqlkit.format_string(self.QUERY, indent="    ")
        assert "\n    ?x ?p ?o\n" in formatted

    def test_format_string_custom_tab_indent(self):
        formatted = sparqlkit.format_string(self.QUERY, indent="\t")
        assert "\n\t?x ?p ?o\n" in formatted

    def test_format_string_explicit_default_indent(self):
        formatted = sparqlkit.format_string_explicit(self.QUERY, parser_type="sparql")
        assert "\n  ?x ?p ?o\n" in formatted

    def test_format_string_explicit_custom_indent(self):
        formatted = sparqlkit.format_string_explicit(
            self.QUERY, parser_type="sparql", indent="    "
        )
        assert "\n    ?x ?p ?o\n" in formatted

    def test_format_query_default_indent(self):
        formatted = sparqlkit.format_query(self.QUERY)
        assert "\n  ?x ?p ?o\n" in formatted

    def test_format_query_custom_indent(self):
        formatted = sparqlkit.format_query(self.QUERY, indent="    ")
        assert "\n    ?x ?p ?o\n" in formatted

    def test_format_update_default_indent(self):
        formatted = sparqlkit.format_update(self.UPDATE)
        assert "\n  <s> <p> <o>\n" in formatted

    def test_format_update_custom_indent(self):
        formatted = sparqlkit.format_update(self.UPDATE, indent="    ")
        assert "\n    <s> <p> <o>\n" in formatted

    def test_serialize_default_indent(self):
        tree = sparqlkit.parse(self.QUERY)
        serialized = sparqlkit.serialize(tree)
        assert "\n  ?x ?p ?o\n" in serialized

    def test_serialize_custom_indent(self):
        tree = sparqlkit.parse(self.QUERY)
        serialized = sparqlkit.serialize(tree, indent="    ")
        assert "\n    ?x ?p ?o\n" in serialized

    def test_nested_indent_accumulates(self):
        query = "SELECT ?x WHERE { { SELECT ?y WHERE { ?y ?p ?o } } }"
        formatted = sparqlkit.format_string(query, indent="  ")
        # Inner SELECT should be at 2 levels = 4 spaces
        assert "\n    SELECT ?y\n" in formatted

    def test_nested_indent_with_four_spaces(self):
        query = "SELECT ?x WHERE { { SELECT ?y WHERE { ?y ?p ?o } } }"
        formatted = sparqlkit.format_string(query, indent="    ")
        # Inner SELECT should be at 2 levels = 8 spaces
        assert "\n        SELECT ?y\n" in formatted
