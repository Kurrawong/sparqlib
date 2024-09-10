from lark import Token, Tree
from lark.visitors import Visitor_Recursive


def get_prefixed_name(prefixed_name: Tree) -> str:
    return prefixed_name.children[0].value


def get_iriref(iriref: Token) -> str:
    return iriref.value


def get_rdf_literal(rdf_literal: Tree) -> str:
    value = rdf_literal.children[0].children[0].value

    if len(rdf_literal.children) > 1:
        langtag_or_datatype = rdf_literal.children[1].children[0]
        if isinstance(langtag_or_datatype, Tree) and langtag_or_datatype.data == "iri":
            value += f"^^{get_iri(langtag_or_datatype)}"
        else:
            value += rdf_literal.children[1].children[0].value

    return value


def get_value(tree: Tree, memory: list[Token] = None) -> list[Token]:
    """This function walks a tree recursively and only expects a single path. Multiple paths raises a ValueError."""
    if memory is None:
        memory = []

    if isinstance(tree, Token):
        memory.append(tree)
    else:
        for child in tree.children:
            get_value(child, memory)

    return memory


def get_iri(iri: Tree) -> str:
    value = iri.children[0]
    if isinstance(value, Token):
        return get_iriref(value)
    elif isinstance(value, Tree):
        return get_prefixed_name(value)
    else:
        raise ValueError(f"Unexpected iri type: {value.data}")


def get_data_block_value(data_block_value: Tree) -> str:
    value = data_block_value.children[0]

    if value.data == "iri":
        return get_iri(value)
    elif (
        value.data == "rdf_literal"
        or value.data == "numeric_literal"
        or value.data == "boolean_literal"
    ):
        return get_rdf_literal(value)
    elif value.data == "undef":
        return "UNDEF"
    else:
        raise ValueError(f"Unexpected data_block_value type: {value.data}")


def get_var(var: Tree) -> str:
    return var.children[0].value


def get_vars(vars_: list[Tree]) -> str:
    result = ""
    for i, var in enumerate(vars_):
        result += get_var(var)
        if i + 1 != len(vars_):
            result += " "

    return result


class SparqlSerializer(Visitor_Recursive):
    def __init__(self):
        self._result = ""
        super().__init__()
        self._indent = 0

    @property
    def result(self):
        return self._result

    def _prologue(self, prologue: Tree):
        base_decls = list(filter(lambda x: x.data == "base_decl", prologue.children))
        prefix_decls = list(
            filter(lambda x: x.data == "prefix_decl", prologue.children)
        )

        for base_decl in base_decls:
            self._result += f"{base_decl.children[0].children[0].value} {get_iriref(base_decl.children[1])}\n"

        for prefix_decl in prefix_decls:
            self._result += f"{prefix_decl.children[0].children[0].value} {prefix_decl.children[1].children[0].value} {get_iriref(prefix_decl.children[2])}\n"

        self._result += "\n"

    def query_unit(self, query_unit: Tree):
        self._query(query_unit.children[0])

    def update_unit(self, update_unit: Tree):
        self._update(update_unit.children[0])

    def _graph_ref(self, graph_ref: Tree):
        graph_str = graph_ref.children[0]
        self._result += f"{graph_str} "
        iri = graph_ref.children[1]
        self._iri(iri)

    def _load(self, load: Tree):
        for child in load.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "iri":
                    self._iri(child)
                elif child.data == "graph_ref":
                    self._graph_ref(child)
                else:
                    raise ValueError(f"Unexpected load value type: {child.data}")
            else:
                raise TypeError(f"Unexpected load value type: {type(child)}")

    def _graph_ref_all(self, graph_ref_all):
        value = graph_ref_all.children[0]
        if isinstance(value, Token):
            self._result += f"{value.value} "
        elif isinstance(value, Tree):
            if value.data == "graph_ref":
                self._graph_ref(value)
            else:
                raise ValueError(f"Unexpected graph_ref_all value type: {value.data}")
        else:
            raise TypeError(f"Unexpected graph_ref_all value type: {type(value)}")

    def _clear(self, clear: Tree):
        for child in clear.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "graph_ref_all":
                    self._graph_ref_all(child)
                else:
                    raise ValueError(f"Unexpected clear value type: {child.data}")
            else:
                raise TypeError(f"Unexpected clear value type: {type(child)}")

    def _drop(self, drop: Tree):
        for child in drop.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "graph_ref_all":
                    self._graph_ref_all(child)
                else:
                    raise ValueError(f"Unexpected drop value type: {child.data}")
            else:
                raise TypeError(f"Unexpected drop value type: {type(child)}")

    def _graph_or_default(self, graph_or_default: Tree):
        for child in graph_or_default.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "iri":
                    self._iri(child)
                else:
                    raise ValueError(
                        f"Unexpected graph_or_default value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected graph_or_default value type: {type(child)}"
                )

    def _add(self, add: Tree):
        for child in add.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "graph_or_default":
                    self._graph_or_default(child)
                else:
                    raise ValueError(f"Unexpected add value type: {child.data}")
            else:
                raise TypeError(f"Unexpected add value type: {type(child)}")

    def _move(self, move: Tree):
        for child in move.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "graph_or_default":
                    self._graph_or_default(child)
                else:
                    raise ValueError(f"Unexpected move value type: {child.data}")
            else:
                raise TypeError(f"Unexpected move value type: {type(child)}")

    def _copy(self, copy: Tree):
        for child in copy.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "graph_or_default":
                    self._graph_or_default(child)
                else:
                    raise ValueError(f"Unexpected copy value type: {child.data}")
            else:
                raise TypeError(f"Unexpected move copy type: {type(child)}")

    def _create(self, create: Tree):
        for child in create.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "graph_ref":
                    self._graph_ref(child)
                else:
                    raise ValueError(f"Unexpected create value type: {child.data}")
            else:
                raise TypeError(f"Unexpected move create type: {type(child)}")

    def _quads_not_triples(self, quads_not_triples: Tree):
        for child in quads_not_triples.children:
            if isinstance(child, Token):
                if child.value == "{":
                    self._result += "{\n"
                elif child.value == "}":
                    self._result += f"\n{'  ' * self._indent}}}"
                else:
                    self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "var_or_iri":
                    self._var_or_iri(child)
                elif child.data == "triples_template":
                    self._indent += 1
                    self._triples_template(child)
                    self._indent -= 1
                else:
                    raise ValueError(
                        f"Unexpected quads_not_triples value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected quads_not_triples value type: {type(child)}"
                )

    def _quads(self, quads: Tree):
        for child in quads.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "triples_template":
                    self._triples_template(child)
                elif child.data == "quads_not_triples":
                    self._quads_not_triples(child)
                else:
                    raise ValueError(f"Unexpected quads value type: {child.data}")
            else:
                raise TypeError(f"Unexpected quads value type: {type(child)}")

    def _quad_data(self, quad_data: Tree):
        self._result += "{\n"
        self._indent += 1
        quads = quad_data.children[1]
        self._quads(quads)
        self._indent -= 1
        self._result += f"\n{'  ' * self._indent}}}"

    def _insert_data(self, insert_data: Tree):
        insert_str = insert_data.children[0]
        data_str = insert_data.children[1]
        self._result += f"{insert_str} {data_str} "
        quad_data = insert_data.children[2]
        self._quad_data(quad_data)

    def _delete_data(self, delete_data: Tree):
        delete_str = delete_data.children[0]
        data_str = delete_data.children[1]
        self._result += f"{delete_str} {data_str} "
        quad_data = delete_data.children[2]
        self._quad_data(quad_data)

    def _quad_pattern(self, quad_pattern: Tree):
        quads = quad_pattern.children[1]
        self._result += "{\n"
        self._indent += 1
        self._quads(quads)
        self._indent -= 1
        self._result += f"\n{'  ' * self._indent}}}"

    def _delete_where(self, delete_where: Tree):
        delete_str = delete_where.children[0]
        where_str = delete_where.children[1]
        self._result += f"{delete_str} {where_str} "
        quad_pattern = delete_where.children[2]
        self._quad_pattern(quad_pattern)

    def _delete_clause(self, delete_clause: Tree):
        delete_str = delete_clause.children[0]
        self._result += f"{delete_str} "
        quad_pattern = delete_clause.children[1]
        self._quad_pattern(quad_pattern)

    def _insert_clause(self, insert_clause: Tree):
        insert_str = insert_clause.children[0]
        self._result += f"{insert_str} "
        quad_pattern = insert_clause.children[1]
        self._quad_pattern(quad_pattern)

    def _using_clause(self, using_clause: Tree):
        for child in using_clause.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "iri":
                    self._iri(child)
                else:
                    raise ValueError(
                        f"Unexpected using_clause value type: {child.data}"
                    )
            else:
                raise TypeError(f"Unexpected using_clause value type: {type(child)}")

    def _modify(self, modify: Tree):
        for child in modify.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "iri":
                    self._iri(child)
                elif child.data == "delete_clause":
                    self._delete_clause(child)
                elif child.data == "insert_clause":
                    self._insert_clause(child)
                elif child.data == "using_clause":
                    self._using_clause(child)
                elif child.data == "group_graph_pattern":
                    self._group_graph_pattern(child)
                else:
                    raise ValueError(f"Unexpected modify value type: {child.data}")
            else:
                raise TypeError(f"Unexpected modify value type: {type(child)}")

    def _update1(self, update1: Tree):
        value = update1.children[0]
        if value.data == "load":
            self._load(value)
        elif value.data == "clear":
            self._clear(value)
        elif value.data == "drop":
            self._drop(value)
        elif value.data == "add":
            self._add(value)
        elif value.data == "move":
            self._move(value)
        elif value.data == "copy":
            self._copy(value)
        elif value.data == "create":
            self._create(value)
        elif value.data == "insert_data":
            self._insert_data(value)
        elif value.data == "delete_data":
            self._delete_data(value)
        elif value.data == "delete_where":
            self._delete_where(value)
        elif value.data == "modify":
            self._modify(value)
        else:
            raise ValueError(f"Unexpected update1 value type: {value.data}")

    def _update(self, update: Tree):
        for child in update.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "prologue":
                    self._prologue(child)
                elif child.data == "update1":
                    self._update1(child)
                elif child.data == "update":
                    self._update(child)
                else:
                    raise ValueError(f"Unexpected update value type: {child.data}")
            else:
                raise TypeError(f"Unexpected update value type: {child.data}")

    def _ask_query(self, ask_query: Tree):
        for child in ask_query.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "dataset_clause":
                    self._dataset_clause(child)
                elif child.data == "where_clause":
                    self._where_clause(child)
                elif child.data == "solution_modifier":
                    self._solution_modifier(child)
                else:
                    raise ValueError(f"Unexpected ask_query value type: {child.data}")
            else:
                raise TypeError(f"Unexpected ask_query value type: {type(child)}")

    def _describe_query(self, describe_query: Tree):
        for child in describe_query.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "var_or_iri":
                    self._var_or_iri(child)
                elif child.data == "dataset_clause":
                    self._dataset_clause(child)
                elif child.data == "where_clause":
                    self._where_clause(child)
                elif child.data == "solution_modifier":
                    self._solution_modifier(child)
                else:
                    raise ValueError(
                        f"Unexpected describe_query value type: {child.data}"
                    )
            else:
                raise TypeError(f"Unexpected describe_query value type: {type(child)}")

    def _query(self, query: Tree):
        prologue = query.children[0]
        self._prologue(prologue)

        query_instance = query.children[1]
        if query_instance.data == "select_query":
            self._select_query(query_instance)
        elif query_instance.data == "construct_query":
            self._construct_query(query_instance)
        elif query_instance.data == "describe_query":
            self._describe_query(query_instance)
        elif query_instance.data == "ask_query":
            self._ask_query(query_instance)
        else:
            raise ValueError(
                f"Unexpected query_instance value type: {query_instance.data}"
            )

        values_clause = query.children[2]
        self._values_clause(values_clause)

    def _source_selector(self, source_selector: Tree):
        iri = source_selector.children[0]
        self._iri(iri)

    def _dataset_clause(self, dataset_clause: Tree):
        from_str = dataset_clause.children[0]
        self._result += f"{from_str} "
        graph_clause = dataset_clause.children[1]

        if graph_clause.data == "default_graph_clause":
            source_selector = graph_clause.children[0]
            self._source_selector(source_selector)
        elif graph_clause.data == "named_graph_clause":
            named_str = graph_clause.children[0].value
            self._result += f"{named_str} "
            source_selector = graph_clause.children[1]
            self._source_selector(source_selector)
        else:
            raise ValueError(f"Unexpected dataset_clause value: {graph_clause}")

        self._result += "\n"

    def _property_list(self, property_list: Tree):
        if property_list.children:
            property_list_not_empty = property_list.children[0]
            self._property_list_not_empty(property_list_not_empty)

    def _triples_same_subject(self, triples_same_subject: Tree):
        self._result += f"{'  ' * self._indent}"
        first_value = triples_same_subject.children[0]
        second_value = triples_same_subject.children[1]

        if first_value.data == "var_or_term":
            self._var_or_term(first_value)
            self._property_list_not_empty(second_value)
        elif first_value.data == "triples_node":
            self._triples_node(first_value)
            self._property_list(second_value)
        else:
            raise ValueError(
                f"Unexpected triples_same_subject first_value value type: {first_value.data}"
            )

    def _construct_triples(self, construct_triples: Tree):
        triples_same_subject = construct_triples.children[0]
        self._triples_same_subject(triples_same_subject)

        if len(construct_triples.children) == 2:
            self._result += " .\n"
            nested_construct_triples = construct_triples.children[1]
            self._construct_triples(nested_construct_triples)

    def _construct_template(self, construct_template: Tree):
        self._result += " {\n"
        self._indent += 1
        if len(construct_template.children) == 1:
            construct_triples = construct_template.children[0]
            self._construct_triples(construct_triples)
        self._indent -= 1
        self._result += "\n}"

    def _group_condition_expression_as_var(
        self, group_condition_expression_as_var: Tree
    ):
        for child in group_condition_expression_as_var.children:
            if isinstance(child, Token):
                self._result += f"{child.value}"
            elif isinstance(child, Tree):
                if child.data == "expression":
                    self._expression(child)
                elif child.data == "var":
                    self._var(child)
                else:
                    raise ValueError(
                        f"Unexpected group_condition_expression_as_var value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected group_condition_expression_as_var value type: {type(child)}"
                )

    def _group_condition(self, group_condition: Tree):
        value = group_condition.children[0]
        if value.data == "built_in_call":
            self._built_in_call(value)
        elif value.data == "function_call":
            self._function_call(value)
        elif value.data == "group_condition_expression_as_var":
            self._group_condition_expression_as_var(value)
        elif value.data == "var":
            self._var(value)
        else:
            raise ValueError(f"Unexpected group_condition value type: {value.data}")

    def _group_clause(self, group_clause: Tree):
        group_str = group_clause.children[0]
        by_str = group_clause.children[1]
        self._result += f"{'  ' * self._indent}{group_str} {by_str} "

        group_conditions = list(
            filter(
                lambda x: isinstance(x, Tree) and x.data == "group_condition",
                group_clause.children,
            )
        )
        for group_condition in group_conditions:
            self._group_condition(group_condition)

    def _having_condition(self, having_condition: Tree):
        constraint = having_condition.children[0]
        self._constraint(constraint)

    def _having(self, having: Tree):
        having_str = having.children[0]
        self._result += f"\n{'  ' * self._indent}{having_str}"

        having_conditions = list(
            filter(
                lambda x: isinstance(x, Tree) and x.data == "having_condition",
                having.children,
            )
        )
        for having_condition in having_conditions:
            self._having_condition(having_condition)

    def _order_condition(self, order_condition: Tree):
        for child in order_condition.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "bracketted_expression":
                    self._bracketted_expression(child)
                elif child.data == "constraint":
                    self._constraint(child)
                elif child.data == "var":
                    self._var(child)
                else:
                    raise ValueError(
                        f"Unexpected order_condition value type: {child.data}"
                    )
            else:
                raise TypeError(f"Unexpected order_condition value type: {type(child)}")

    def _order_clause(self, order_clause: Tree):
        order_str = order_clause.children[0].value
        by_str = order_clause.children[1].value
        self._result += f"\n{'  ' * self._indent}{order_str} {by_str} "

        order_conditions = list(
            filter(
                lambda x: isinstance(x, Tree) and x.data == "order_condition",
                order_clause.children,
            )
        )
        for order_condition in order_conditions:
            self._order_condition(order_condition)

    def _limit_clause(self, limit_clause: Tree):
        limit_str = limit_clause.children[0].value
        value = limit_clause.children[1].value
        self._result += f"\n{'  ' * self._indent}{limit_str} {value} "

    def _offset_clause(self, offset_clause: Tree):
        offset_str = offset_clause.children[0].value
        value = offset_clause.children[1].value
        self._result += f"\n{'  ' * self._indent}{offset_str} {value} "

    def _limit_offset_clauses(self, limit_offset_clauses: Tree):
        for child in limit_offset_clauses.children:
            if isinstance(child, Tree):
                if child.data == "limit_clause":
                    self._limit_clause(child)
                elif child.data == "offset_clause":
                    self._offset_clause(child)
                else:
                    raise ValueError(
                        f"Unexpected limit_offset_clause value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected limit_offset_clause value type: {type(child)}"
                )

    def _solution_modifier(self, solution_modifier: Tree):
        for child in solution_modifier.children:
            if child.data == "group_clause":
                self._group_clause(child)
            elif child.data == "having_clause":
                self._having(child)
            elif child.data == "order_clause":
                self._order_clause(child)
            elif child.data == "limit_offset_clauses":
                self._limit_offset_clauses(child)
            else:
                raise ValueError(
                    f"Unexpected solution_modifier value type: {child.data}"
                )

    def _construct_construct_template(self, construct_construct_template: Tree):
        construct_template = construct_construct_template.children[0]
        self._construct_template(construct_template)

        dataset_clauses = list(
            filter(
                lambda x: x.data == "dataset_clause",
                construct_construct_template.children,
            )
        )
        for dataset_clause in dataset_clauses:
            self._dataset_clause(dataset_clause)

        where_clause = list(
            filter(
                lambda x: x.data == "where_clause",
                construct_construct_template.children,
            )
        )[0]
        self._where_clause(where_clause)

        solution_modifier = list(
            filter(
                lambda x: x.data == "solution_modifier",
                construct_construct_template.children,
            )
        )[0]
        self._solution_modifier(solution_modifier)

    def _triples_template(self, triples_template):
        for child in triples_template.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "triples_same_subject":
                    self._triples_same_subject(child)
                elif child.data == "triples_template":
                    self._triples_template(child)
                else:
                    raise ValueError(
                        f"Unexpected triples_template value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected triples_template value type: {type(child)}"
                )

    def _construct_triples_template(self, construct_triples_template: Tree):
        for child in construct_triples_template.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "dataset_clause":
                    self._dataset_clause(child)
                elif child.data == "triples_template":
                    self._result += "{\n"
                    self._indent += 1
                    self._triples_template(child)
                    self._indent -= 1
                    self._result += f"{'  ' * self._indent}\n}}"
                elif child.data == "solution_modifier":
                    self._solution_modifier(child)
                else:
                    raise ValueError(
                        f"Unexpected construct_triples_template value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected construct_triples_template value type: {type(child)}"
                )

    def _construct_query(self, construct_query: Tree):
        construct_str = construct_query.children[0]
        self._result += f"{construct_str} "

        value = construct_query.children[1]
        if value.data == "construct_construct_template":
            self._construct_construct_template(value)
        elif value.data == "construct_triples_template":
            self._construct_triples_template(value)
        else:
            raise ValueError(f"Unexpected construct_query value type: {value.data}")

    def _string(self, string: Tree):
        self._result += f"{string.children[0].value} "

    def _aggregate(self, aggregate: Tree):
        for child in aggregate.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "expression":
                    self._expression(child)
                elif child.data == "string":
                    self._string(child)
                else:
                    raise ValueError(f"Unexpected aggregate value type: {child.data}")
            else:
                raise TypeError(f"Unexpected aggregate value type: {type(child)}")

    def _regex_expression(self, regex_expression: Tree):
        regex_str = regex_expression.children[0].value
        self._result += regex_str
        expressions = list(
            filter(
                lambda x: isinstance(x, Tree) and x.data == "expression",
                regex_expression.children,
            )
        )
        self._expression_list_common(expressions)

    def _expression_list_common(self, expressions: list[Tree]):
        self._result += "("
        for i, expression in enumerate(expressions):
            self._expression(expression)
            if i + 1 != len(expressions):
                self._result += ", "

        self._result += ") "

    def _expression_list(self, expression_list: Tree):
        expressions = list(
            filter(
                lambda x: isinstance(x, Tree) and x.data == "expression",
                expression_list.children,
            )
        )
        self._expression_list_common(expressions)

    def _exists_func(self, exists_func: Tree):
        exists_str = exists_func.children[0].value
        self._result += f"{'  ' * self._indent}{exists_str}"
        group_graph_pattern = exists_func.children[1]
        self._group_graph_pattern(group_graph_pattern)

    def _not_exists_func(self, not_exists_func: Tree):
        not_str = not_exists_func.children[0].value
        exists_str = not_exists_func.children[1].value
        self._result += f"{'  ' * self._indent}{not_str} {exists_str}"
        group_graph_pattern = not_exists_func.children[2]
        self._group_graph_pattern(group_graph_pattern)

    def _substring_expression(self, substring_expression: Tree):
        for child in substring_expression.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "expression":
                    self._expression(child)
                else:
                    raise ValueError(
                        f"Unexpected substring_expression value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected substring_expression value type: {type(child)}"
                )

    def _str_replace_expression(self, str_replace_expression):
        for child in str_replace_expression.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "expression":
                    self._expression(child)
                else:
                    raise ValueError(
                        f"Unexpected str_replace_expression value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected str_replace_expression value type: {type(child)}"
                )

    def _built_in_call(self, built_in_call: Tree):
        for child in built_in_call.children:
            if isinstance(child, Tree):
                if child.data == "aggregate":
                    self._aggregate(child)
                elif child.data == "expression":
                    self._expression(child)
                elif child.data == "expression_list":
                    self._expression_list(child)
                elif child.data == "substring_expression":
                    self._substring_expression(child)
                elif child.data == "str_replace_expression":
                    self._str_replace_expression(child)
                elif child.data == "regex_expression":
                    self._regex_expression(child)
                elif child.data == "exists_func":
                    self._exists_func(child)
                elif child.data == "not_exists_func":
                    self._not_exists_func(child)
                else:
                    raise ValueError(
                        f"Unexpected built_in_call tree value type: {child.data}"
                    )
            elif isinstance(child, Token):
                self._result += f"{child.value} "
            else:
                raise TypeError(f"Unexpected built_in_call value type: {type(child)}")

    def _iri_or_function(self, iri_or_function):
        for child in iri_or_function.children:
            if child.data == "iri":
                self._iri(child)
            elif child.data == "arg_list":
                self._arg_list(child)
            else:
                raise ValueError(f"Unexpected iri_or_function value type: {child.data}")

    def _primary_expression(self, primary_expression: Tree):
        value = primary_expression.children[0]

        if value.data == "bracketted_expression":
            self._bracketted_expression(value)
        elif value.data == "built_in_call":
            self._built_in_call(value)
        elif value.data == "iri_or_function":
            self._iri_or_function(value)
        elif (
            value.data == "rdf_literal"
            or value.data == "numeric_literal"
            or value.data == "boolean_literal"
        ):
            self._rdf_literal(value)
        elif value.data == "var":
            self._var(value)
        else:
            raise ValueError(f"Unexpected primary_expression value type: {value.data}")

    def _unary_expression(self, unary_expression: Tree):
        for child in unary_expression.children:
            if isinstance(child, Token):
                self._result += f"{child.value}"
            elif isinstance(child, Tree):
                if child.data == "primary_expression":
                    self._primary_expression(child)
                else:
                    raise ValueError(
                        f"Unexpected unary_expression value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected unary_expression value type: {type(child)}"
                )

    def _multiplicative_expression(self, multiplicative_expression: Tree):
        for child in multiplicative_expression.children:
            if isinstance(child, Token):
                self._result += child.value
            elif isinstance(child, Tree):
                if child.data == "unary_expression":
                    self._unary_expression(child)
                else:
                    raise ValueError(
                        f"Unexpected multiplicative_expression value type: {child.data}"
                    )
            else:
                raise ValueError(
                    f"Unexpected multiplicative_expression value type: {type(child)}"
                )

    def _additive_expression(self, additive_expression: Tree):
        for child in additive_expression.children:
            if isinstance(child, Token):
                self._result += child.value
            elif isinstance(child, Tree):
                if child.data == "multiplicative_expression":
                    self._multiplicative_expression(child)
                elif (
                    child.data == "numeric_literal_positive"
                    or child.data == "numeric_literal_negative"
                ):
                    self._numeric_literal(child)
                elif child.data == "unary_expression":
                    self._unary_expression(child)
                else:
                    raise ValueError(
                        f"Unexpected additive_expression value type: {child.data}"
                    )
            else:
                raise ValueError(
                    f"Unexpected additive_expression value type: {type(child)}"
                )

    def _numeric_expression(self, numeric_expression: Tree):
        additive_expression = numeric_expression.children[0]
        self._additive_expression(additive_expression)

    def _relational_expression(self, relational_expression: Tree):
        for child in relational_expression.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "numeric_expression":
                    self._numeric_expression(child)
                elif child.data == "expression_list":
                    self._expression_list(child)
                else:
                    raise ValueError(
                        f"Unexpected relational_expression value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected relational_expression value type: {type(child)}"
                )

    def _value_logical(self, value_logical: Tree):
        relational_expression = value_logical.children[0]
        self._relational_expression(relational_expression)

    def _conditional_and_expression(self, conditional_and_expression: Tree):
        for child in conditional_and_expression.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "value_logical":
                    self._value_logical(child)
                else:
                    raise ValueError(
                        f"Unexpected _conditional_and_expression value type: {child.data}"
                    )
            else:
                raise ValueError(
                    f"Unexpected _conditional_and_expression value type: {type(child)}"
                )

    def _conditional_or_expression(self, conditional_or_expression: Tree):
        for child in conditional_or_expression.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "conditional_and_expression":
                    self._conditional_and_expression(child)
                else:
                    raise ValueError(
                        f"Unexpected _conditional_or_expression value type: {child.data}"
                    )
            else:
                raise ValueError(
                    f"Unexpected _conditional_or_expression value type: {type(child)}"
                )

    def _expression(self, expression: Tree):
        conditional_or_expression = expression.children[0]
        self._conditional_or_expression(conditional_or_expression)

    def _select_clause_expression_as_var(self, expression_as_var: Tree):
        expression = expression_as_var.children[0]
        self._result += "("
        self._expression(expression)
        as_str = expression_as_var.children[1].value
        var = get_var(expression_as_var.children[2])
        self._result += f" {as_str} {var}) "

    def _select_clause_var_or_expression(self, select_clause_var_or_expression: Tree):
        value = select_clause_var_or_expression.children[0]
        if value.data == "var":
            self._result += f"{get_var(value)} "
        elif value.data == "select_clause_expression_as_var":
            self._select_clause_expression_as_var(value)
        else:
            raise ValueError(
                f"Unexpected select_clause_var_or_expression value: {select_clause_var_or_expression.data}"
            )

    def _select_clause(self, select_clause: Tree):
        for child in select_clause.children:
            if isinstance(child, Token):
                if child.value.lower() == "select":
                    self._result += f"{'  ' * self._indent}"
                self._result += f"{child.value} "

        select_clause_var_or_expressions = list(
            filter(
                lambda x: isinstance(x, Tree)
                and x.data == "select_clause_var_or_expression",
                select_clause.children,
            )
        )
        for i, select_clause_var_or_expression in enumerate(
            select_clause_var_or_expressions
        ):
            self._select_clause_var_or_expression(select_clause_var_or_expression)
            if i + 1 != len(select_clause_var_or_expressions):
                self._result += " "

    def _rdf_literal(self, rdf_literal: Tree):
        self._result += f"{get_rdf_literal(rdf_literal)} "

    def _numeric_literal(self, numeric_literal: Tree):
        self._result += f"{numeric_literal.children[0].children[0].value} "

    def _blank_node(self, blank_node: Tree):
        self._result += f"{blank_node.children[0].value} "

    def _boolean_literal(self, boolean_literal: Tree):
        self._result += f"{boolean_literal.children[0].children[0].value} "

    def _graph_term(self, graph_term: Tree):
        value = graph_term.children[0]
        if isinstance(value, Token):
            self._result += f"{value.value} "
        else:
            if value.data == "iri":
                self._iri(value)
            elif value.data == "rdf_literal":
                self._rdf_literal(value)
            elif value.data == "numeric_literal":
                self._numeric_literal(value)
            elif value.data == "boolean_literal":
                self._boolean_literal(value)
            elif value.data == "blank_node":
                self._blank_node(value)
            else:
                raise ValueError(f"Unexpected graph_term value type: {value.data}")

    def _var_or_term(self, var_or_term: Tree):
        value = var_or_term.children[0]
        if value.data == "var":
            self._result += f"{get_var(value)} "
        elif value.data == "graph_term":
            self._graph_term(value)
        else:
            raise ValueError(f"Unexpected var_or_term value type: {value.data}")

    def _verb_simple(self, verb_simple: Tree):
        var = verb_simple.children[0]
        self._var(var)

    def _blank_node_property_list_path(self, blank_node_property_list_path: Tree):
        property_list_not_empty = blank_node_property_list_path.children[0]
        self._result += "[\n"
        self._indent += 1
        self._result += f"{'  ' * self._indent}"
        self._property_list_path_not_empty(property_list_not_empty)
        self._indent -= 1
        self._result += f"\n{'  ' * self._indent}]\n"

    def _collection_path(self, collection_path: Tree):
        self._result += "("
        for child in collection_path.children:
            if child.data == "graph_node_path":
                self._graph_node_path(child)
            else:
                raise ValueError(f"Unexpected collection_path value type: {child.data}")
        self._result += ")"

    def _triples_node_path(self, triples_node_path: Tree):
        value = triples_node_path.children[0]
        if value.data == "collection_path":
            self._collection_path(value)
        elif value.data == "blank_node_property_list_path":
            self._blank_node_property_list_path(value)
        else:
            raise ValueError(f"Unexpected triples_node_path value type: {value.data}")

    def _graph_node_path(self, graph_node_path: Tree):
        value = graph_node_path.children[0]
        if value.data == "var_or_term":
            self._var_or_term(value)
        elif value.data == "triples_node_path":
            self._triples_node_path(value)
        else:
            raise ValueError(f"Unexpected graph_node_path value type: {value.data}")

    def _object_path(self, object_path: Tree):
        graph_node_path = object_path.children[0]
        self._graph_node_path(graph_node_path)

    def _object_list_path(self, object_list_path: Tree):
        self._result += " "
        object_path = object_list_path.children[0]
        self._object_path(object_path)

        object_list_path_others = list(
            filter(
                lambda x: x.data == "object_list_path_other", object_list_path.children
            )
        )
        for object_path_other in object_list_path_others:
            self._result += ", "
            self._object_path(object_path_other.children[0])

    def _path_mod(self, path_mod: Tree):
        symbol = path_mod.children[0].value
        self._result += symbol

    def _path_one_in_property_set(self, path_one_in_property_set: Tree):
        if len(path_one_in_property_set.children) == 2:
            self._result += "^"
            value = path_one_in_property_set.children[1]
        else:
            value = path_one_in_property_set.children[0]

        if isinstance(value, Tree):
            self._result += get_iri(value)
        else:
            self._result += "a"

    def _path_negated_property_set(self, path_negated_property_set: Tree):
        for child in path_negated_property_set.children:
            if isinstance(child, Token):
                self._result += child.value
            elif isinstance(child, Tree):
                if child.data == "path_one_in_property_set":
                    self._path_one_in_property_set(child)
                else:
                    raise ValueError(
                        f"Unexpected path_negated_property_set value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected path_negated_property_set value type: {type(child)}"
                )

    def _path_primary(self, path_primary: Tree):
        value = path_primary.children[0]
        if isinstance(value, Token):
            if value.type == "A":
                self._result += "a "
        elif isinstance(value, Tree):
            if value.data == "iri":
                self._iri(value)
            elif value.data == "path_negated_property_set":
                self._result += "!"
                self._path_negated_property_set(value)
            elif value.data == "path":
                self._result += "("
                self._path(value)
                self._result += ")"
        else:
            raise ValueError(f"Unexpected path_primary value type: {type(value)}")

    def _path_elt(self, path_elt: Tree):
        path_primary = path_elt.children[0]
        self._path_primary(path_primary)

        if len(path_elt.children) == 2:
            path_mod = path_elt.children[1]
            self._path_mod(path_mod)

        if len(path_elt.children) > 2:
            raise ValueError(
                f"Unexpected path_elt children size: {len(path_elt.children)}"
            )

    def _path_elt_or_inverse(self, path_elt_or_inverse: Tree):
        if len(path_elt_or_inverse.children) == 1:
            path_elt = path_elt_or_inverse.children[0]
            self._path_elt(path_elt)
        elif len(path_elt_or_inverse.children) == 2:
            self._result += "^"
            path_elt = path_elt_or_inverse.children[1]
            self._path_elt(path_elt)
        else:
            raise ValueError(
                f"Unexpected path_elt_or_inverse children size: {len(path_elt_or_inverse.children)}"
            )

    def _path_sequence(self, path_sequence: Tree):
        path_elt_or_inverses = list(
            filter(lambda x: x.data == "path_elt_or_inverse", path_sequence.children)
        )
        for i, path_elt_or_inverse_elt in enumerate(path_elt_or_inverses):
            self._path_elt_or_inverse(path_elt_or_inverse_elt)
            if i + 1 != len(path_elt_or_inverses):
                self._result += "/"

    def _path_alternative(self, path_alternative: Tree):
        path_sequences = list(
            filter(lambda x: x.data == "path_sequence", path_alternative.children)
        )
        for i, path_sequence in enumerate(path_sequences):
            self._path_sequence(path_sequence)
            if i + 1 != len(path_sequences):
                self._result += "|"

    def _path(self, path: Tree):
        path_alternative = path.children[0]
        self._path_alternative(path_alternative)

    def _verb_path(self, verb_path: Tree):
        path = verb_path.children[0]
        self._path(path)

    def _collection(self, collection: Tree):
        graph_nodes = list(
            filter(lambda x: x.data == "graph_node", collection.children)
        )
        self._result += "("

        for graph_node in graph_nodes:
            self._graph_node(graph_node)

        self._result += ")"

    def _verb(self, verb: Tree):
        value = verb.children[0]
        if isinstance(value, Tree):
            self._var_or_iri(value)
        elif isinstance(value, Token):
            self._result += "a "
        else:
            raise TypeError(f"Unexpected value type: {type(value)}")

    def _verb_object_list(self, verb_object_list: Tree):
        verb = verb_object_list.children[0]
        object_list = verb_object_list.children[1]
        self._verb(verb)
        self._object_list(object_list)

    def _property_list_not_empty(self, property_list_not_empty: Tree):
        verb_object_lists = list(
            filter(
                lambda x: x.data == "verb_object_list", property_list_not_empty.children
            )
        )
        for i, verb_object_list in enumerate(verb_object_lists):
            self._verb_object_list(verb_object_list)
            if i + 1 != len(verb_object_lists):
                self._result += "; "

    def _blank_node_property_list(self, blank_node_property_list: Tree):
        self._result += "["
        value = blank_node_property_list.children[0]
        self._property_list_not_empty(value)
        self._result += "]"

    def _triples_node(self, triples_node: Tree):
        value = triples_node.children[0]
        if value.data == "collection":
            self._collection(value)
        elif value.data == "blank_node_property_list":
            self._blank_node_property_list(value)
        else:
            raise ValueError(f"Unexpected triples_node value type: {value.data}")

    def _graph_node(self, graph_node: Tree):
        value = graph_node.children[0]
        if value.data == "var_or_term":
            self._var_or_term(value)
        elif value.data == "triples_node":
            self._triples_node(value)
        else:
            raise ValueError(f"Unexpected graph_node value type: {value.data}")

    def _object(self, obj: Tree):
        graph_node = obj.children[0]
        self._graph_node(graph_node)

    def _object_list(self, object_list):
        objects = list(filter(lambda x: x.data == "object", object_list.children))
        for i, obj in enumerate(objects):
            self._object(obj)
            if i + 1 != len(objects):
                self._result += ", "

    def _property_list_path_not_empty_rest(
        self, property_list_path_not_empty_rest: Tree
    ):
        first_value = property_list_path_not_empty_rest.children[0]
        if first_value.data == "verb_path":
            self._verb_path(first_value)
        elif first_value.data == "verb_simple":
            self._verb_simple(first_value)
        else:
            raise ValueError(
                f"Unexpected property_list_path_not_empty_rest value type: {first_value.data}"
            )

        object_list = property_list_path_not_empty_rest.children[1]
        self._object_list(object_list)

    def _property_list_path_not_empty_other(
        self, property_list_path_not_empty_other: Tree
    ):
        self._result += f";\n{'  ' * (self._indent + 1)}"

        if property_list_path_not_empty_other.children:
            property_list_path_not_empty_rest = (
                property_list_path_not_empty_other.children[0]
            )
            self._property_list_path_not_empty_rest(property_list_path_not_empty_rest)

    def _property_list_path_not_empty(self, property_list_path_not_empty: Tree):
        first_value = property_list_path_not_empty.children[0]
        if first_value.data == "verb_path":
            self._verb_path(first_value)
        elif first_value.data == "verb_simple":
            self._verb_simple(first_value)
        else:
            raise ValueError(f"Unexpected first_value value type: {first_value.data}")

        object_list_path = property_list_path_not_empty.children[1]
        self._object_list_path(object_list_path)

        property_list_path_not_empty_others = list(
            filter(
                lambda x: x.data == "property_list_path_not_empty_other",
                property_list_path_not_empty.children,
            )
        )
        for property_list_not_empty_other in property_list_path_not_empty_others:
            self._property_list_path_not_empty_other(property_list_not_empty_other)

    def _property_list_path(self, property_list_path: Tree):
        if len(property_list_path.children) == 1:
            self._indent += 1
            property_list_path_not_empty = property_list_path.children[0]
            self._property_list_path_not_empty(property_list_path_not_empty)
            self._indent += 1

    def _triples_same_subject_path(self, triples_same_subject_path: Tree):
        self._result += f"{'  ' * self._indent}"
        first_value = triples_same_subject_path.children[0]
        second_value = triples_same_subject_path.children[1]

        if first_value.data == "var_or_term":
            self._var_or_term(first_value)
            self._property_list_path_not_empty(second_value)
        elif first_value.data == "triples_node_path":
            self._triples_node_path(first_value)
            self._property_list_path(second_value)
        else:
            raise ValueError(f"Unexpected first value value type: {first_value.data}")

    def _triples_block(self, triples_block: Tree):
        triples_same_subject_path = triples_block.children[0]
        self._triples_same_subject_path(triples_same_subject_path)

        if len(triples_block.children) > 1:
            self._result += " .\n"
            second_triples_block = triples_block.children[1]
            self._triples_block(second_triples_block)

    def _optional_graph_pattern(self, optional_graph_pattern: Tree):
        optional_str = optional_graph_pattern.children[0].value
        self._result += f"{'  ' * self._indent}{optional_str} "

        group_graph_pattern = optional_graph_pattern.children[1]
        self._group_graph_pattern(group_graph_pattern)

    def _inline_data(self, inline_data: Tree):
        values_str = inline_data.children[0]
        self._result += f"{'  ' * self._indent}{values_str} "
        data_block = inline_data.children[1]
        self._data_block(data_block)
        self._result += "\n"

    def _var(self, var: Tree):
        self._result += f"{get_var(var)} "

    def _iri(self, iri: Tree):
        self._result += f"{get_iri(iri)} "

    def _var_or_iri(self, var_or_iri: Tree):
        value = var_or_iri.children[0]
        if value.data == "var":
            self._var(value)
        elif value.data == "iri":
            self._iri(value)
        else:
            raise ValueError(f"Unexpected var_or_iri value type: {value.data}")

    def _graph_graph_pattern(self, graph_graph_pattern: Tree):
        graph_str = graph_graph_pattern.children[0]
        self._result += f"{'  ' * self._indent}{graph_str} "

        var_or_iri = graph_graph_pattern.children[1]
        self._var_or_iri(var_or_iri)

        group_graph_pattern = graph_graph_pattern.children[2]
        self._group_graph_pattern(group_graph_pattern)

    def _group_or_union_graph_pattern(self, group_or_union_graph_pattern: Tree):
        for child in group_or_union_graph_pattern.children:
            if isinstance(child, Token):
                self._result += f"{'  ' * self._indent}{child.value} "
            elif isinstance(child, Tree):
                if child.data == "group_graph_pattern":
                    self._group_graph_pattern(child)
                else:
                    raise ValueError(
                        f"Unexpected group_graph_pattern value type: {child.data}"
                    )
            else:
                raise ValueError(
                    f"Unexpected group_graph_pattern value type: {type(child)}"
                )

    def _bracketted_expression(self, bracketted_expression: Tree):
        expression = bracketted_expression.children[0]
        self._result += "("
        self._expression(expression)
        self._result += ")"

    def _arg_list(self, arg_list: Tree):
        for i, child in enumerate(arg_list.children):
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "expression":
                    # TODO: For some reason, lark won't extract the COMMA token.
                    #   Workaround is to add our own comma for now.
                    self._expression(child)
                    next_child = arg_list.children[i + 1]
                    if isinstance(next_child, Tree) and next_child.data == "expression":
                        self._result += ", "
                else:
                    raise ValueError(f"Unexpected arg_list value type: {child.data}")
            else:
                raise TypeError(f"Unexpected arg_list value type: {type(child)}")

    def _function_call(self, function_call: Tree):
        iri = function_call.children[0]
        arg_list = function_call.children[1]
        self._iri(iri)
        self._arg_list(arg_list)

    def _constraint(self, constraint: Tree):
        value = constraint.children[0]
        if value.data == "bracketted_expression":
            self._bracketted_expression(value)
        elif value.data == "built_in_call":
            self._built_in_call(value)
        elif value.data == "function_call":
            self._function_call(value)
        else:
            raise ValueError(f"Unexpected constraint value type: {value.data}")

    def _filter(self, filter_: Tree):
        filter_str = filter_.children[0]
        self._result += f"{'  ' * self._indent}{filter_str} "

        constraint = filter_.children[1]
        self._constraint(constraint)
        self._result += "\n"

    def _bind(self, bind: Tree):
        bind_str = bind.children[0].value
        self._result += f"{'  ' * self._indent}{bind_str} "
        self._result += "("
        expression = bind.children[1]
        self._expression(expression)
        as_str = bind.children[2].value
        var = get_var(bind.children[3])
        self._result += f" {as_str} {var})\n"

    def _minus_graph_pattern(self, minus_graph_pattern: Tree):
        minus_str = minus_graph_pattern.children[0].value
        self._result += f"{'  ' * self._indent}{minus_str} "
        group_graph_pattern = minus_graph_pattern.children[1]
        self._group_graph_pattern(group_graph_pattern)

    def _service_graph_pattern(self, service_graph_pattern: Tree):
        for child in service_graph_pattern.children:
            if isinstance(child, Token):
                if child.value.lower() == "service":
                    self._result += f"{'  ' * self._indent}{child.value} "
                else:
                    self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "var_or_iri":
                    self._var_or_iri(child)
                elif child.data == "group_graph_pattern":
                    self._group_graph_pattern(child)
                else:
                    raise ValueError(
                        f"Unexpected service_graph_pattern value type: {child.data}"
                    )
            else:
                raise ValueError(
                    f"Unexpected service_graph_pattern value type: {type(child)}"
                )

    def _graph_pattern_not_triples(self, graph_pattern_not_triples: Tree):
        value = graph_pattern_not_triples.children[0]
        if value.data == "group_or_union_graph_pattern":
            self._group_or_union_graph_pattern(value)
        elif value.data == "optional_graph_pattern":
            self._optional_graph_pattern(value)
        elif value.data == "minus_graph_pattern":
            self._minus_graph_pattern(value)
        elif value.data == "graph_graph_pattern":
            self._graph_graph_pattern(value)
        elif value.data == "service_graph_pattern":
            self._service_graph_pattern(value)
        elif value.data == "filter":
            self._filter(value)
        elif value.data == "bind":
            self._bind(value)
        elif value.data == "inline_data":
            self._inline_data(value)
        else:
            raise ValueError(
                f"Unexpected graph_pattern_not_triples value type: {value.data}"
            )

    def _group_graph_pattern_sub_other(self, group_graph_pattern_sub_other: Tree):
        self._result += "\n"
        for child in group_graph_pattern_sub_other.children:
            if isinstance(child, Tree):
                if child.data == "graph_pattern_not_triples":
                    self._graph_pattern_not_triples(child)
                elif child.data == "triples_block":
                    self._triples_block(child)
            elif isinstance(child, Token):
                if child.type == "DOT":
                    self._result += f"{'  ' * self._indent}.\n"
            else:
                raise TypeError(f"Unexpected child type: {type(child)}")

    def _group_graph_pattern_sub(self, group_graph_pattern_sub: Tree):
        for child in group_graph_pattern_sub.children:
            if child.data == "triples_block":
                self._triples_block(child)
            elif child.data == "group_graph_pattern_sub_other":
                self._group_graph_pattern_sub_other(child)
            else:
                raise ValueError(
                    f"Unexpected group_graph_pattern_sub_other value type: {child.data}"
                )

    def _sub_select(self, sub_select: Tree):
        select_clause = sub_select.children[0]
        self._select_clause(select_clause)

        where_clause = sub_select.children[1]
        self._where_clause(where_clause)

        solution_modifier = sub_select.children[2]
        self._solution_modifier(solution_modifier)

        values_clause = sub_select.children[3]
        self._values_clause(values_clause)

    def _group_graph_pattern(self, group_graph_pattern: Tree):
        self._indent += 1
        self._result += f"{'  ' * (self._indent - 1)}{{\n"

        value = group_graph_pattern.children[0]
        if value.data == "sub_select":
            self._sub_select(value)
        elif value.data == "group_graph_pattern_sub":
            self._group_graph_pattern_sub(value)
        else:
            raise ValueError(f"Unexpected group_graph_pattern value type: {value.data}")

        self._result += f"\n{'  ' * (self._indent - 1)}}}\n"
        self._indent -= 1

    def _where_clause(self, where_clause: Tree):
        if len(where_clause.children) == 2:
            where_str = where_clause.children[0].value
            group_graph_pattern = where_clause.children[1]
            self._result += f"\n{'  ' * self._indent}{where_str} "
        elif len(where_clause.children) == 1:
            group_graph_pattern = where_clause.children[0]
        else:
            raise ValueError(
                f"Unexpected where_clause children count: {len(where_clause.children)}"
            )

        self._group_graph_pattern(group_graph_pattern)

    def _select_query(self, select_query: Tree):
        select_clause = select_query.children[0]
        self._select_clause(select_clause)
        dataset_clauses = list(
            filter(lambda x: x.data == "dataset_clause", select_query.children)
        )
        for dataset_clause in dataset_clauses:
            self._dataset_clause(dataset_clause)

        where_clause = list(
            filter(lambda x: x.data == "where_clause", select_query.children)
        )[0]
        self._where_clause(where_clause)

        solution_modifier = list(
            filter(lambda x: x.data == "solution_modifier", select_query.children)
        )[0]
        self._solution_modifier(solution_modifier)

    def _values_clause(self, values_clause: Tree):
        if values_clause.children:
            values_str = values_clause.children[0]
            self._result += f"{values_str} "

            data_block = values_clause.children[1]
            self._data_block(data_block)

    def _data_block(self, data_block: Tree):
        inline_data = data_block.children[0]
        if inline_data.data == "inline_data_one_var":
            self._inline_data_one_var(inline_data)
        elif inline_data.data == "inline_data_full":
            self._inline_data_full(inline_data)
        else:
            raise ValueError(f"Unexpected value for data_block: {inline_data.data}")

    def _data_block_value(self, data_block_value: Tree):
        for child in data_block_value.children:
            if isinstance(child, Token):
                self._result += f"{child.value} "
            elif isinstance(child, Tree):
                if child.data == "iri":
                    self._iri(child)
                elif (
                    child.data == "rdf_literal"
                    or child.data == "numeric_literal"
                    or child.data == "boolean_literal"
                ):
                    self._rdf_literal(child)
                else:
                    raise ValueError(
                        f"Unexpected data_block_value value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected data_block_value value type: {type(child)}"
                )

    def _inline_data_one_var(self, inline_data_one_var: Tree):
        for i, child in enumerate(inline_data_one_var.children):
            if isinstance(child, Token):
                if child.value == "{":
                    self._result += "{\n"
                elif child.value == "}":
                    self._result += f"\n{'  ' * self._indent}}}"
            elif isinstance(child, Tree):
                if child.data == "var":
                    self._var(child)
                elif child.data == "data_block_value":
                    self._indent += 1
                    next_child = inline_data_one_var.children[i + 1]
                    if (
                        isinstance(next_child, Tree)
                        and next_child.data == "data_block_value"
                    ):
                        self._result += f"{'  ' * self._indent}"

                    self._data_block_value(child)
                    self._indent -= 1

    def _data_block_value_group(self, data_block_value_group: Tree):
        for child in data_block_value_group.children:
            if isinstance(child, Token):
                if child.value == "(":
                    self._result += f"{'  ' * self._indent}("
                else:
                    self._result += f"{child.value}\n"
            elif isinstance(child, Tree):
                if child.data == "data_block_value":
                    self._data_block_value(child)
                else:
                    raise ValueError(f"Unexpected data block value: {child.data}")
            else:
                raise TypeError(f"Unexpected data block value: {type(child)}")

    def _inline_data_full(self, inline_data_full: Tree):
        for child in inline_data_full.children:
            self._indent += 1
            if isinstance(child, Token):
                if child.value == "{":
                    self._result += "{\n"
                elif child.value == "}":
                    self._result += f"{'  ' * (self._indent - 1)}}}"
                elif child.value == "(":
                    self._result += f"{child.value}"
                elif child.value == ")":
                    self._result += f"{child.value} "
                elif child.value == "()":
                    self._result += f"{child.value} "
                else:
                    raise ValueError(f"Unexpected data block value: {child.value}")
            elif isinstance(child, Tree):
                if child.data == "var":
                    self._var(child)
                elif child.data == "data_block_value_group":
                    self._data_block_value_group(child)
                else:
                    raise ValueError(
                        f"Unexpected inline_data_full value type: {child.data}"
                    )
            else:
                raise TypeError(
                    f"Unexpected inline_data_full value type: {type(child)}"
                )

            self._indent -= 1


class _SparqlSerializer(Visitor_Recursive):
    def __init__(self):
        self._result = ""
        super().__init__()
        self._indent = 0

    @property
    def result(self):
        return self._result

    def base(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def prefix(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def pname_ns(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def iriref(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def prefixed_name(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def values_clause(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def var(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def left_curly_brace(self, node: Tree):
        self._result += " {\n"
        self._indent += 1

    def right_curly_brace(self, node: Tree):
        self._result += "\n} "
        self._indent -= 1

    def left_parenthesis(self, node: Tree):
        self._result += "("

    def right_parenthesis(self, node: Tree):
        self._result += ")"

    def string(self, node: Tree):
        self._result += node.children[0].value

    def langtag(self, node: Tree):
        self._result += f"{node.children[0].value} "

    def datatype(self, node: Tree):
        self._result += "^^"

    def undef(self, node: Tree):
        self._result += "UNDEF "

    def numeric_literal(self, node: Tree):
        self._result += f"{node.children[0].children[0].value} "

    def boolean_literal(self, node: Tree):
        self._result += f"{node.children[0].children[0].value} "
