import pytest
from lark import Token, Tree

from sparqlkit.serializer import SparqlSerializer


class TestRobustness:
    def setup_method(self):
        self.serializer = SparqlSerializer()

    def test_group_clause_robustness(self):
        """Test GROUP BY clause with unexpected children layout."""
        # Standard: GROUP BY var
        # Robustness: GROUP (token), BY (token), extra_token, var

        # Manually build a tree simulating a 'group_clause'
        # Current parser structure is roughly:
        # [Token(GROUP), Token(BY), group_condition...]

        group_token = Token("GROUP", "GROUP")
        by_token = Token("BY", "BY")
        garbage = Token("RAW", " /*comment*/ ")
        var_tree = Tree("var", [Token("VAR", "?x")])

        tree = Tree("group_clause", [group_token, by_token, garbage, var_tree])

        serializer = SparqlSerializer()
        # This calls _group_clause_enter
        # It should find GROUP and BY, print them, and then process children that
        # are NOT group/by. So it should process 'garbage' and 'var_tree'.
        result = serializer.visit_topdown(tree)

        # Expectation: "GROUP BY  GARBAGE  ?x " (roughly)
        # The serializer handles tokens by printing value + space.
        assert "GROUP BY" in result
        assert "/*comment*/" in result
        assert "?x" in result

    def test_dataset_clause_robustness(self):
        """Test dataset clause finding FROM/NAMED robustly."""
        # FROM <iri>
        from_token = Token("FROM", "FROM")
        iri_tree = Tree("iri", [Token("IRIREF", "<http://example.com>")])

        # Swapped order? (Grammar doesn't allow, but robust serializer might handle)
        # Tree: [iri_tree, from_token]
        tree = Tree("dataset_clause", [iri_tree, from_token])

        result = self.serializer.visit_topdown(tree)

        # Should print "FROM <http://example.com>"
        assert "FROM" in result
        assert "<http://example.com>" in result

    def test_limit_clause_robustness(self):
        """Test LIMIT clause with extra tokens."""
        limit_token = Token("LIMIT", "LIMIT")
        val_token = Token("INTEGER", "10")
        extra = Token("COMMENT", "# comment")

        tree = Tree("limit_clause", [limit_token, extra, val_token])

        result = self.serializer.visit_topdown(tree)

        assert "LIMIT" in result
        assert "10" in result
        assert "# comment" in result

    def test_quad_data_robustness(self):
        """Test QUAD DATA finding 'quads' child by type."""
        # Structure: INSERT DATA { quads }
        # Tree: quad_data -> [LCB, quads, RCB]

        lcb = Token("LEFT_CURLY_BRACE", "{")
        rcb = Token("RIGHT_CURLY_BRACE", "}")

        # quads -> triples_template
        # simple quads tree
        quads = Tree(
            "quads",
            [
                Tree(
                    "triples_template",
                    [
                        Tree(
                            "triples_same_subject",
                            [
                                Tree(
                                    "var_or_term", [Tree("var", [Token("VAR", "?s")])]
                                ),
                                Tree(
                                    "property_list_not_empty",
                                    [
                                        Tree(
                                            "verb_object_list",
                                            [
                                                Tree(
                                                    "verb",
                                                    [
                                                        Tree(
                                                            "var_or_iri",
                                                            [
                                                                Tree(
                                                                    "var",
                                                                    [
                                                                        Token(
                                                                            "VAR", "?p"
                                                                        )
                                                                    ],
                                                                )
                                                            ],
                                                        )
                                                    ],
                                                ),
                                                Tree(
                                                    "object_list",
                                                    [
                                                        Tree(
                                                            "object",
                                                            [
                                                                Tree(
                                                                    "graph_node",
                                                                    [
                                                                        Tree(
                                                                            "var_or_term",
                                                                            [
                                                                                Tree(
                                                                                    "var",
                                                                                    [
                                                                                        Token(
                                                                                            "VAR",
                                                                                            "?o",
                                                                                        )
                                                                                    ],
                                                                                )
                                                                            ],
                                                                        )
                                                                    ],
                                                                )
                                                            ],
                                                        )
                                                    ],
                                                ),
                                            ],
                                        )
                                    ],
                                ),
                            ],
                        )
                    ],
                )
            ],
        )

        # Insert a garbage token at index 1 (where quads usually is)
        garbage = Token("GARBAGE", "garbage")

        # New order: LCB, garbage, quads, RCB
        tree = Tree("quad_data", [lcb, garbage, quads, rcb])

        result = self.serializer.visit_topdown(tree)

        # It should still find 'quads' and serialize it.
        # 'garbage' might be ignored because _quad_data_enter specifically looks
        # for 'quads' child and pushes IT to the stack. It does NOT push other
        # children. This is the intended behavior of the robust change (target
        # specific child).
        assert "{" in result
        assert "?s" in result
        assert "?p" in result
        assert "?o" in result
        assert (
            "garbage" not in result
        )  # Verified behavior: explicit selection ignores others


if __name__ == "__main__":
    pytest.main([__file__])
