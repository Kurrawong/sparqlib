import sparql


def test_values_one_var_each_value_on_own_line():
    query = """
prefix ex:  <http://www.example.org/schema#>
prefix in:  <http://www.example.org/instance#>

select ?x where {
VALUES ?g { <urn:g1> <urn:g2> }
graph ?g {
  {select ?x where {?x ?p ?g filter(?x != in:i1)}}
}
}
""".lstrip()

    formatted = sparql.format_string(query)

    assert ("  VALUES ?g {\n    <urn:g1>\n    <urn:g2>\n  }\n") in formatted


def test_values_two_vars_each_row_on_own_line():
    query = (
        "SELECT * WHERE { VALUES (?g ?g2) { (<urn:g1> <urn:g2>) (<urn:g3> <urn:g4>) } }"
    )
    formatted = sparql.format_string(query)

    assert (
        "  VALUES (?g ?g2) {\n    (<urn:g1> <urn:g2>)\n    (<urn:g3> <urn:g4>)\n  }\n"
    ) in formatted
