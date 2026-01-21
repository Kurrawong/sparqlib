from sparql.parser import sparql_parser
from sparql.serializer import SparqlSerializer
from sparql.serializer_iterative import IterativeSparqlSerializer

query = "SELECT * WHERE { ?s foaf:knows|foaf:friend ?o }"
tree = sparql_parser.parse(query)

print("Recursive:")
ser_rec = SparqlSerializer()
ser_rec.visit_topdown(tree)
print(f"'{ser_rec.result}'")

print("\nIterative:")
ser_iter = IterativeSparqlSerializer()
ser_iter.visit_topdown(tree)
print(f"'{ser_iter.result}'")
