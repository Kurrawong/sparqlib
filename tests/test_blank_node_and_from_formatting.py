"""Regression tests for blank node property list and FROM clause formatting."""

from sparqlkit import format_query


class TestSelectAsteriskSpacing:
    """Tests for SELECT * spacing."""

    def test_select_asterisk_has_space(self):
        query = "SELECT* WHERE { ?s ?p ?o }"
        result = format_query(query)
        assert "SELECT *" in result
        assert "SELECT*" not in result

    def test_select_distinct_asterisk_has_space(self):
        query = "SELECT DISTINCT* WHERE { ?s ?p ?o }"
        result = format_query(query)
        assert "SELECT DISTINCT *" in result


class TestFromClauseFormatting:
    """Tests for FROM clause newline formatting."""

    def test_single_from_on_own_line(self):
        query = "SELECT * FROM <urn:graph:a> WHERE { ?s ?p ?o }"
        result = format_query(query)
        lines = result.split("\n")
        assert any("FROM <urn:graph:a>" in line for line in lines)

    def test_multiple_from_clauses_on_separate_lines(self):
        query = "SELECT * FROM <urn:graph:a> FROM <urn:graph:b> WHERE { ?s ?p ?o }"
        result = format_query(query)
        lines = result.split("\n")
        from_lines = [line for line in lines if "FROM" in line]
        assert len(from_lines) == 2
        assert "FROM <urn:graph:a>" in from_lines[0]
        assert "FROM <urn:graph:b>" in from_lines[1]

    def test_from_named_on_own_line(self):
        query = (
            "SELECT * FROM <urn:graph:a> FROM NAMED <urn:graph:b> WHERE { ?s ?p ?o }"
        )
        result = format_query(query)
        lines = result.split("\n")
        from_lines = [line for line in lines if "FROM" in line]
        assert len(from_lines) == 2


class TestBlankNodePropertyListFormatting:
    """Tests for blank node [ ... ] formatting with newlines."""

    def test_simple_blank_node_multiline(self):
        query = "SELECT * WHERE { ?s <p> [ <a> <b> ] }"
        result = format_query(query)
        assert "[\n" in result
        assert "\n" in result.split("[")[1].split("]")[0]

    def test_blank_node_followed_by_dot_has_single_space(self):
        # Trailing '.' is optional for the last triple in a group pattern in SPARQL,
        # so ensure the '.' is actually required by placing another triple after it.
        query = "SELECT * WHERE { ?s <p> [ <a> <b> ] . ?s <q> <r> }"
        result = format_query(query)
        assert "] ." in result
        assert "]  ." not in result

    def test_blank_node_properties_on_separate_lines(self):
        query = "SELECT * WHERE { ?s <p> [ <a> <b> ; <c> <d> ] }"
        result = format_query(query)
        lines = result.split("\n")
        # Properties inside blank node should be on separate lines
        prop_lines = [line.strip() for line in lines if "<a>" in line or "<c>" in line]
        assert len(prop_lines) == 2

    def test_blank_node_after_semicolon_properly_indented(self):
        query = "SELECT * WHERE { ?s a <X> ; <p> [ <a> <b> ] }"
        result = format_query(query)
        lines = result.split("\n")
        # Find the line with <a> <b> inside the blank node
        for line in lines:
            if "<a> <b>" in line:
                # Should be indented more than the <p> line
                p_line = next(ln for ln in lines if "<p>" in ln)
                assert len(line) - len(line.lstrip()) > len(p_line) - len(
                    p_line.lstrip()
                )
                break


class TestFullQueryRegression:
    """Full query regression test matching the original issue."""

    EXAMPLE_INPUT = """PREFIX addr: <https://linked.data.gov.au/def/addr/>
PREFIX apt: <https://linked.data.gov.au/def/addr-part-types/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sdo: <https://schema.org/>

SELECT *
from <urn:qali:graph:addresses>
from <urn:qali:graph:geographical-names>
where {
  ?s a addr:Address ;
    sdo:hasPart [
      sdo:additionalType apt:locality ;
      sdo:value <https://linked.data.gov.au/dataset/qld-addr/gn/19896>
      ]
}
limit 1"""

    EXPECTED_OUTPUT = """PREFIX addr: <https://linked.data.gov.au/def/addr/>
PREFIX apt: <https://linked.data.gov.au/def/addr-part-types/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sdo: <https://schema.org/>

SELECT *
FROM <urn:qali:graph:addresses>
FROM <urn:qali:graph:geographical-names>
WHERE {
  ?s a addr:Address ;
    sdo:hasPart [
      sdo:additionalType apt:locality;
      sdo:value <https://linked.data.gov.au/dataset/qld-addr/gn/19896>
    ]
}
LIMIT 1"""

    def test_full_query_formatting(self):
        result = format_query(self.EXAMPLE_INPUT)
        assert result == self.EXPECTED_OUTPUT

    def test_select_asterisk_spacing(self):
        result = format_query(self.EXAMPLE_INPUT)
        assert "SELECT *" in result
        assert "SELECT*" not in result

    def test_from_clauses_on_separate_lines(self):
        result = format_query(self.EXAMPLE_INPUT)
        lines = result.split("\n")
        from_lines = [line for line in lines if line.startswith("FROM")]
        assert len(from_lines) == 2

    def test_blank_node_has_newlines(self):
        result = format_query(self.EXAMPLE_INPUT)
        # Check that blank node content is on separate lines
        assert "[\n" in result
        lines = result.split("\n")
        # sdo:additionalType and sdo:value should be on separate lines
        additional_type_lines = [ln for ln in lines if "sdo:additionalType" in ln]
        value_lines = [ln for ln in lines if "sdo:value" in ln]
        assert len(additional_type_lines) == 1
        assert len(value_lines) == 1
        assert additional_type_lines[0] != value_lines[0]
