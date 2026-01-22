from importlib.resources import files

from lark import Lark

grammar = files(__package__).joinpath("grammar.lark").read_text(encoding="utf-8")
sparql_parser = Lark(grammar, start="query_unit")
sparql_update_parser = Lark(grammar, start="update_unit")
