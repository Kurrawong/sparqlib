from importlib.resources import files

from lark import Lark

grammar = files(__package__).joinpath("grammar.lark").read_text(encoding="utf-8")

# Keep Earley + dynamic lexer (Lark defaults) for correct tokenization of
# ambiguous operators (e.g. property path modifiers vs arithmetic operators).
sparql_parser = Lark(grammar, start="unit", propagate_positions=True)
sparql_query_parser = Lark(grammar, start="query_unit", propagate_positions=True)
sparql_update_parser = Lark(grammar, start="update_unit", propagate_positions=True)
