from sparql.parser import sparql_update_parser
from sparql.serializer import SparqlSerializer
from sparql.serializer_iterative import IterativeSparqlSerializer

query = "INSERT DATA { GRAPH <http://example.org/g1> { <http://example.org/s> <http://example.org/p> <http://example.org/o> } }"
tree = sparql_update_parser.parse(query)

print("Recursive:")
ser_rec = SparqlSerializer()
ser_rec.visit_topdown(tree)
print(f"'{ser_rec.result}'")

print("\nIterative:")
ser_iter = IterativeSparqlSerializer()
ser_iter.visit_topdown(tree)
print(f"'{ser_iter.result}'")
