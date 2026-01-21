from enum import Enum, auto
from typing import Any, Callable, NamedTuple, NotRequired, Optional, TypedDict, Union

from lark import Token, Tree


class SerializerError(Exception):
    """Raised when the serializer encounters an unexpected tree structure."""

    pass


class TraversalPhase(Enum):
    """Phases of tree traversal."""

    ENTER = auto()
    EXIT = auto()
    LEAF = auto()


class TreeHandler(NamedTuple):
    """Handlers for entering and exiting a tree node."""

    enter: Optional[Callable[[Tree, dict[str, Any]], Optional[bool]]] = None
    exit: Optional[Callable[[Tree, dict[str, Any]], None]] = None


class TraversalContext(TypedDict, total=False):
    """Context passed to tree handlers during traversal."""

    indent_inc: bool


def _safe_get_child(
    node: Tree, index: int, expected_type: Optional[type] = None, context: str = ""
) -> Any:
    """Safely get a child node at the given index.

    :param node: The parent tree node.
    :param index: The index of the child to retrieve.
    :param expected_type: Optional type to validate the child against.
    :param context: Context string for error messages.
    :return: The child node.
    :raises SerializerError: If the child doesn't exist or has wrong type.
    """
    if not hasattr(node, "children") or node.children is None:
        raise SerializerError(
            f"Node has no children{f' in {context}' if context else ''}: {node}"
        )
    if index >= len(node.children) or index < -len(node.children):
        raise SerializerError(
            f"Child index {index} out of range for node with {len(node.children)} children"
            f"{f' in {context}' if context else ''}: {node.data if hasattr(node, 'data') else node}"
        )
    child = node.children[index]
    if expected_type is not None and not isinstance(child, expected_type):
        raise SerializerError(
            f"Expected child of type {expected_type.__name__}, got {type(child).__name__}"
            f"{f' in {context}' if context else ''}"
        )
    return child


def get_prefixed_name(prefixed_name: Tree) -> str:
    """Extracts the value from a prefixed_name node."""
    child = _safe_get_child(prefixed_name, 0, Token, "prefixed_name")
    return child.value


def get_iriref(iriref: Token) -> str:
    """Extracts the value from an iriref token."""
    return iriref.value


def get_rdf_literal(rdf_literal: Tree) -> str:
    """Extracts the string representation of an rdf_literal node."""
    string_node = _safe_get_child(rdf_literal, 0, Tree, "rdf_literal.string")
    value_token = _safe_get_child(string_node, 0, Token, "rdf_literal.string.value")
    value = value_token.value

    if len(rdf_literal.children) > 1:
        suffix_node = _safe_get_child(rdf_literal, 1, Tree, "rdf_literal.suffix")
        langtag_or_datatype = _safe_get_child(
            suffix_node, 0, context="rdf_literal.langtag_or_datatype"
        )
        if isinstance(langtag_or_datatype, Tree) and langtag_or_datatype.data == "iri":
            value += f"^^{get_iri(langtag_or_datatype)}"
        elif isinstance(langtag_or_datatype, Token):
            value += langtag_or_datatype.value
        else:
            raise SerializerError(
                f"Unexpected langtag_or_datatype type in rdf_literal: {type(langtag_or_datatype)}"
            )

    return value


def get_value(
    tree: Union[Tree, Token], memory: Optional[list[Token]] = None
) -> list[Token]:
    """Iteratively walks a tree and collects all tokens.

    Uses a stack-based approach to avoid RecursionError on deeply nested trees.
    """
    if memory is None:
        memory = []

    stack: list[Union[Tree, Token]] = [tree]

    while stack:
        node = stack.pop()
        if isinstance(node, Token):
            memory.append(node)
        elif isinstance(node, Tree) and node.children:
            for child in reversed(node.children):
                if child is not None:
                    stack.append(child)

    return memory


def get_iri(iri: Tree) -> str:
    """Extracts the string representation of an iri node."""
    if not iri.children:
        raise SerializerError(f"iri node has no children: {iri}")

    value = iri.children[0]
    if isinstance(value, Token):
        return get_iriref(value)
    elif isinstance(value, Tree):
        return get_prefixed_name(value)
    else:
        raise SerializerError(
            f"Unexpected iri child type: {type(value).__name__}, expected Token or Tree"
        )


def get_data_block_value(data_block_value: Tree) -> str:
    """Extracts the string representation of a data_block_value node."""
    value = _safe_get_child(data_block_value, 0, Tree, "data_block_value")

    if not hasattr(value, "data"):
        raise SerializerError(
            f"data_block_value child has no 'data' attribute: {type(value)}"
        )

    if value.data == "iri":
        return get_iri(value)
    elif value.data in ("rdf_literal", "numeric_literal", "boolean_literal"):
        return get_rdf_literal(value)
    elif value.data == "undef":
        return "UNDEF"
    else:
        raise SerializerError(f"Unexpected data_block_value type: {value.data}")


def get_var(var: Tree) -> str:
    """Extracts the variable name from a var node."""
    child = _safe_get_child(var, 0, Token, "var")
    return child.value


def get_vars(vars_: list[Tree]) -> str:
    """Joins variable names with spaces."""
    return " ".join(get_var(var) for var in vars_)


class SparqlSerializer:
    """An iterative SPARQL serializer that avoids recursion depth issues.

    This serializer uses an explicit stack to traverse the SPARQL AST top-down,
    eliminating the risk of RecursionError for deeply nested queries. It maintains
    exact output parity with the original recursive serializer while supporting
    arbitrarily complex structures.

    Example:
        >>> from sparql.parser import sparql_parser
        >>> from sparql.serializer import SparqlSerializer
        >>> tree = sparql_parser.parse("SELECT * WHERE { ?s ?p ?o }")
        >>> serializer = SparqlSerializer()
        >>> print(serializer.visit_topdown(tree))
    """

    _handler_cache: dict[type, dict[str, TreeHandler]] = {}

    def __init__(self):
        self._parts: list[str] = []
        self._indent: int = 0
        self._stack: list[
            tuple[Union[Tree, Token], TraversalPhase, Optional[TraversalContext]]
        ] = []
        cls = self.__class__
        if cls not in SparqlSerializer._handler_cache:
            SparqlSerializer._handler_cache[cls] = self._build_handler_map()
        self._handler_map = SparqlSerializer._handler_cache[cls]

    @property
    def result(self) -> str:
        """Returns the serialized SPARQL query as a string."""
        return "".join(self._parts)

    def visit_topdown(self, tree: Tree) -> str:
        """Traverses the tree top-down iteratively and returns the serialized result.

        Args:
            tree: The Lark Tree to serialize.

        Returns:
            The serialized SPARQL query string.
        """
        self._parts = []
        self._indent = 0
        self._stack = [(tree, TraversalPhase.ENTER, None)]

        while self._stack:
            node, phase, context = self._stack.pop()
            if isinstance(node, Tree):
                self._handle_tree(node, phase, context)
            else:
                self._handle_token(node)

        return self.result

    def _handle_tree(
        self, node: Tree, phase: TraversalPhase, context: Optional[TraversalContext]
    ) -> None:
        """Handles a Tree node based on the current phase."""
        handler = self._handler_map.get(node.data)

        if phase == TraversalPhase.ENTER:
            # Push EXIT frame first so it is popped last
            self._stack.append((node, TraversalPhase.EXIT, context))

            skip_children = False
            if handler and handler["enter"]:
                # Pass self explicitly to the unbound method
                skip_children = handler["enter"](self, node, context or {}) is True

            if not skip_children:
                for child in reversed(node.children):
                    if isinstance(child, (Tree, Token)):
                        self._stack.append((child, TraversalPhase.ENTER, context))
        else:  # TraversalPhase.EXIT
            if handler and handler["exit"]:
                handler["exit"](self, node, context or {})

    def _handle_token(self, token: Token) -> None:
        """Handles a Token by appending its value to the result parts."""
        if token.type == "DOT_NEWLINE":
            self._parts.append(token.value)
        elif token.type == "SPACE":
            self._parts.append(" ")
        elif token.type == "RAW":
            self._parts.append(token.value)
        else:
            self._parts.append(token.value)
            self._parts.append(" ")

    def _build_handler_map(self) -> dict[str, dict[str, Any]]:
        """Builds a map of tree node types to their respective handlers (unbound methods).

        Subclasses can override this method to add or modify handlers.
        """
        cls = self.__class__
        return {
            "query_unit": {"enter": None, "exit": None},
            "update_unit": {"enter": None, "exit": None},
            "update": {"enter": cls._update_enter, "exit": None},
            "update1": {"enter": None, "exit": None},
            "load": {"enter": cls._load_enter, "exit": None},
            "clear": {"enter": cls._clear_enter, "exit": None},
            "drop": {"enter": cls._drop_enter, "exit": None},
            "add": {"enter": cls._add_enter, "exit": None},
            "move": {"enter": cls._move_enter, "exit": None},
            "copy": {"enter": cls._copy_enter, "exit": None},
            "create": {"enter": cls._create_enter, "exit": None},
            "insert_data": {"enter": cls._insert_data_enter, "exit": None},
            "delete_data": {"enter": cls._delete_data_enter, "exit": None},
            "delete_where": {"enter": cls._delete_where_enter, "exit": None},
            "modify": {"enter": cls._modify_enter, "exit": None},
            "delete_clause": {"enter": cls._delete_clause_enter, "exit": None},
            "insert_clause": {"enter": cls._insert_clause_enter, "exit": None},
            "using_clause": {"enter": cls._using_clause_enter, "exit": None},
            "quad_data": {"enter": cls._quad_data_enter, "exit": cls._quad_data_exit},
            "quad_pattern": {
                "enter": cls._quad_pattern_enter,
                "exit": cls._quad_pattern_exit,
            },
            "quads": {"enter": None, "exit": None},
            "quads_not_triples": {"enter": cls._quads_not_triples_enter, "exit": None},
            "graph_ref": {"enter": cls._graph_ref_enter, "exit": None},
            "graph_ref_all": {"enter": cls._graph_ref_all_enter, "exit": None},
            "graph_or_default": {"enter": cls._graph_or_default_enter, "exit": None},
            "query": {"enter": None, "exit": None},
            "prologue": {"enter": cls._prologue_enter, "exit": None},
            "select_query": {"enter": None, "exit": None},
            "construct_query": {"enter": None, "exit": None},
            "describe_query": {"enter": None, "exit": None},
            "ask_query": {"enter": None, "exit": None},
            "construct_construct_template": {
                "enter": cls._construct_construct_template_enter,
                "exit": None,
            },
            "construct_triples_template": {
                "enter": cls._construct_triples_template_enter,
                "exit": None,
            },
            "select_clause": {"enter": cls._select_clause_enter, "exit": None},
            "where_clause": {"enter": cls._where_clause_enter, "exit": None},
            "dataset_clause": {
                "enter": cls._dataset_clause_enter,
                "exit": cls._dataset_clause_exit,
            },
            "solution_modifier": {"enter": None, "exit": None},
            "group_clause": {"enter": cls._group_clause_enter, "exit": None},
            "having_clause": {"enter": cls._having_clause_enter, "exit": None},
            "order_clause": {"enter": cls._order_clause_enter, "exit": None},
            "limit_clause": {"enter": cls._limit_clause_enter, "exit": None},
            "offset_clause": {"enter": cls._offset_clause_enter, "exit": None},
            "limit_offset_clauses": {"enter": None, "exit": None},
            "construct_template": {
                "enter": cls._construct_template_enter,
                "exit": cls._construct_template_exit,
            },
            "construct_triples": {"enter": cls._construct_triples_enter, "exit": None},
            "group_graph_pattern": {
                "enter": cls._group_graph_pattern_enter,
                "exit": cls._group_graph_pattern_exit,
            },
            "group_graph_pattern_sub": {"enter": None, "exit": None},
            "group_graph_pattern_sub_other": {
                "enter": cls._group_graph_pattern_sub_other_enter,
                "exit": None,
            },
            "triples_block": {"enter": cls._triples_block_enter, "exit": None},
            "graph_pattern_not_triples": {"enter": None, "exit": None},
            "optional_graph_pattern": {
                "enter": cls._optional_graph_pattern_enter,
                "exit": None,
            },
            "minus_graph_pattern": {
                "enter": cls._minus_graph_pattern_enter,
                "exit": None,
            },
            "graph_graph_pattern": {
                "enter": cls._graph_graph_pattern_enter,
                "exit": None,
            },
            "group_or_union_graph_pattern": {
                "enter": cls._group_or_union_graph_pattern_enter,
                "exit": None,
            },
            "service_graph_pattern": {
                "enter": cls._service_graph_pattern_enter,
                "exit": None,
            },
            "filter": {"enter": cls._filter_enter, "exit": None},
            "bind": {"enter": cls._bind_enter, "exit": None},
            "inline_data": {"enter": cls._inline_data_enter, "exit": None},
            "values_clause": {"enter": cls._values_clause_enter, "exit": None},
            "triples_same_subject": {
                "enter": cls._triples_same_subject_enter,
                "exit": None,
            },
            "triples_same_subject_path": {
                "enter": cls._triples_same_subject_path_enter,
                "exit": None,
            },
            "triples_template": {
                "enter": cls._triples_template_enter,
                "exit": cls._triples_template_exit,
            },
            "property_list_not_empty": {
                "enter": cls._property_list_not_empty_enter,
                "exit": None,
            },
            "property_list_path_not_empty": {
                "enter": cls._property_list_path_not_empty_enter,
                "exit": None,
            },
            "property_list_path_not_empty_other": {
                "enter": cls._property_list_path_not_empty_other_enter,
                "exit": None,
            },
            "property_list_path_not_empty_rest": {"enter": None, "exit": None},
            "verb_object_list": {"enter": None, "exit": None},
            "verb": {"enter": cls._verb_enter, "exit": None},
            "object_list": {"enter": cls._object_list_enter, "exit": None},
            "object": {"enter": None, "exit": None},
            "object_list_path": {"enter": cls._object_list_path_enter, "exit": None},
            "object_list_path_other": {
                "enter": cls._object_list_path_other_enter,
                "exit": None,
            },
            "object_path": {"enter": None, "exit": None},
            "verb_path": {"enter": None, "exit": None},
            "verb_simple": {"enter": None, "exit": None},
            "path": {"enter": None, "exit": None},
            "path_alternative": {"enter": cls._path_alternative_enter, "exit": None},
            "path_sequence": {"enter": cls._path_sequence_enter, "exit": None},
            "path_elt_or_inverse": {
                "enter": cls._path_elt_or_inverse_enter,
                "exit": None,
            },
            "path_elt": {"enter": None, "exit": None},
            "path_mod": {"enter": cls._path_mod_enter, "exit": None},
            "path_primary": {"enter": cls._path_primary_enter, "exit": None},
            "path_negated_property_set": {
                "enter": cls._path_negated_property_set_enter,
                "exit": None,
            },
            "path_one_in_property_set": {
                "enter": cls._path_one_in_property_set_enter,
                "exit": None,
            },
            "triples_node_path": {"enter": None, "exit": None},
            "graph_node_path": {"enter": None, "exit": None},
            "collection_path": {
                "enter": cls._collection_path_enter,
                "exit": cls._collection_path_exit,
            },
            "blank_node_property_list_path": {
                "enter": cls._blank_node_property_list_path_enter,
                "exit": cls._blank_node_property_list_path_exit,
            },
            "graph_node": {"enter": None, "exit": None},
            "var_or_term": {"enter": None, "exit": None},
            "var_or_iri": {"enter": None, "exit": None},
            "triples_node": {"enter": None, "exit": None},
            "collection": {
                "enter": cls._collection_enter,
                "exit": cls._collection_exit,
            },
            "blank_node_property_list": {
                "enter": cls._blank_node_property_list_enter,
                "exit": cls._blank_node_property_list_exit,
            },
            "iri": {"enter": cls._iri_enter, "exit": None},
            "select_clause_var_or_expression": {"enter": None, "exit": None},
            "select_clause_expression_as_var": {
                "enter": cls._select_clause_expression_as_var_enter,
                "exit": None,
            },
            "var": {"enter": cls._var_enter, "exit": None},
            # Expressions
            "expression": {"enter": None, "exit": None},
            "conditional_or_expression": {
                "enter": cls._conditional_or_expression_enter,
                "exit": None,
            },
            "conditional_and_expression": {
                "enter": cls._conditional_and_expression_enter,
                "exit": None,
            },
            "value_logical": {"enter": None, "exit": None},
            "relational_expression": {
                "enter": cls._relational_expression_enter,
                "exit": None,
            },
            "numeric_expression": {"enter": None, "exit": None},
            "additive_expression": {
                "enter": cls._additive_expression_enter,
                "exit": None,
            },
            "multiplicative_expression": {
                "enter": cls._multiplicative_expression_enter,
                "exit": None,
            },
            "unary_expression": {"enter": cls._unary_expression_enter, "exit": None},
            "primary_expression": {
                "enter": cls._primary_expression_enter,
                "exit": None,
            },
            "bracketted_expression": {
                "enter": cls._bracketted_expression_enter,
                "exit": None,
            },
            "built_in_call": {"enter": cls._built_in_call_enter, "exit": None},
            "aggregate": {"enter": cls._aggregate_enter, "exit": None},
            "function_call": {"enter": cls._function_call_enter, "exit": None},
            "iri_or_function": {"enter": None, "exit": None},
            "arg_list": {"enter": cls._arg_list_enter, "exit": None},
            "substring_expression": {
                "enter": cls._substring_expression_enter,
                "exit": None,
            },
            "str_replace_expression": {
                "enter": cls._str_replace_expression_enter,
                "exit": None,
            },
            "regex_expression": {"enter": cls._regex_expression_enter, "exit": None},
            "exists_func": {"enter": cls._exists_func_enter, "exit": None},
            "not_exists_func": {"enter": cls._not_exists_func_enter, "exit": None},
            "expression_list": {"enter": cls._expression_list_enter, "exit": None},
            "group_condition_expression_as_var": {
                "enter": cls._group_condition_expression_as_var_enter,
                "exit": None,
            },
            "group_condition": {"enter": cls._group_condition_enter, "exit": None},
            "having_condition": {"enter": cls._having_condition_enter, "exit": None},
            "order_condition": {"enter": cls._order_condition_enter, "exit": None},
            "constraint": {"enter": cls._constraint_enter, "exit": None},
            "string": {"enter": cls._string_enter, "exit": None},
            # Literals
            "rdf_literal": {"enter": cls._rdf_literal_enter, "exit": None},
            "numeric_literal": {"enter": cls._numeric_literal_enter, "exit": None},
            "boolean_literal": {"enter": cls._boolean_literal_enter, "exit": None},
            "blank_node": {"enter": cls._blank_node_enter, "exit": None},
            "anon": {"enter": cls._anon_enter, "exit": None},
            "nil": {"enter": cls._nil_enter, "exit": None},
            "undef": {"enter": cls._undef_enter, "exit": None},
            "iriref": {"enter": cls._iriref_enter, "exit": None},
            "prefixed_name": {"enter": cls._prefixed_name_enter, "exit": None},
            # Inline data
            "inline_data_one_var": {
                "enter": cls._inline_data_one_var_enter,
                "exit": None,
            },
            "inline_data_full": {"enter": cls._inline_data_full_enter, "exit": None},
            "data_block_value_group": {
                "enter": cls._data_block_value_group_enter,
                "exit": None,
            },
            "data_block_value": {"enter": cls._data_block_value_enter, "exit": None},
        }

    def _safe_get_child_by_type(
        self, node: Tree, child_type: Union[str, type], index: int = 0
    ) -> Optional[Union[Tree, Token]]:
        """Safely find a child of a specific type (Tree data or Token type)."""
        count = 0
        for child in node.children:
            match = False
            if isinstance(child_type, str):
                if isinstance(child, Tree) and child.data == child_type:
                    match = True
                elif isinstance(child, Token) and child.type == child_type:
                    match = True
            elif isinstance(child, child_type):
                match = True

            if match:
                if count == index:
                    return child
                count += 1
        return None

    def _find_token(self, node: Tree, value: str) -> Optional[Token]:
        """Find a token child with a specific value (case-insensitive)."""
        for child in node.children:
            if isinstance(child, Token) and child.value.lower() == value.lower():
                return child
        return None

    def _insert_data_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _delete_data_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _delete_where_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _modify_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _delete_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _insert_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _using_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _quad_data_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append("{\n")
        self._indent += 1
        # Robustly find the child to traverse (the ones inside braces)
        # Assuming structure: LEFT_CURLY_BRACE quads RIGHT_CURLY_BRACE
        # We want to traverse 'quads'
        quads = self._safe_get_child_by_type(tree, "quads")
        if quads:
            self._stack.append((quads, TraversalPhase.ENTER, context))
        return True

    def _quad_data_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        self._indent -= 1
        self._parts.append(f"\n{'\t' * self._indent}}}")

    def _quad_pattern_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append("{\n")
        self._indent += 1
        # Robustly find 'quads'
        quads = self._safe_get_child_by_type(tree, "quads")
        if quads:
            self._stack.append((quads, TraversalPhase.ENTER, context))
        return True

    def _quad_pattern_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        self._indent -= 1
        self._parts.append(f"\n{'\t' * self._indent}}}")

    def _quads_not_triples_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        """Handles quads that are not triples, manually injecting braces and indentation.

        This handler manually traverses the children to inject RAW tokens for braces
        and indentation, ensuring proper formatting without relying on recursion.
        """
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                if child.value == "{":
                    self._stack.append(
                        (Token("RAW", "{\n"), TraversalPhase.ENTER, context)
                    )
                elif child.value == "}":
                    self._stack.append(
                        (
                            Token("RAW", f"\n{'\t' * self._indent}}}"),
                            TraversalPhase.ENTER,
                            context,
                        )
                    )
                else:
                    self._stack.append((child, TraversalPhase.ENTER, context))
            elif isinstance(child, Tree):
                if child.data == "triples_template":
                    self._stack.append(
                        (child, TraversalPhase.ENTER, {"indent_inc": True})
                    )
                else:
                    self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _update_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        """Handles the top-level update node, injecting semicolons between operations."""
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token) and child.value == ";":
                self._stack.append((Token("RAW", ";\n"), TraversalPhase.ENTER, context))
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _load_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _clear_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _drop_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _add_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _move_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _copy_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _create_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _graph_ref_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _graph_ref_all_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _graph_or_default_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _prologue_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        """Handles the prologue (BASE and PREFIX declarations).

        This is a special case where we process the entire subtree in the ENTER phase
        and return True to skip standard child traversal. This simplifies the logic
        as the prologue structure is flat and rigid.
        """
        base_decls = [
            c for c in tree.children if isinstance(c, Tree) and c.data == "base_decl"
        ]
        prefix_decls = [
            c for c in tree.children if isinstance(c, Tree) and c.data == "prefix_decl"
        ]

        for base_decl in base_decls:
            base_token = base_decl.children[0].children[0]
            iriref_token = base_decl.children[1]
            self._parts.append(f"{base_token.value} {iriref_token.value}\n")

        for prefix_decl in prefix_decls:
            prefix_token = prefix_decl.children[0].children[0]
            pname_ns_token = prefix_decl.children[1].children[0]
            iriref_token = prefix_decl.children[2]
            self._parts.append(
                f"{prefix_token.value} {pname_ns_token.value} {iriref_token.value}\n"
            )

        self._parts.append("\n")
        return True

    def _select_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        """Handles the SELECT clause, managing tokens and expressions manually.

        We manually push children to the stack to ensure correct spacing and
        indentation for the 'SELECT' keyword and the variables/expressions that follow.
        """
        tokens = [c for c in tree.children if isinstance(c, Token)]
        exprs = [
            c
            for c in tree.children
            if isinstance(c, Tree) and c.data == "select_clause_var_or_expression"
        ]

        self._stack.append((tree, TraversalPhase.EXIT, context))

        for i in range(len(exprs) - 1, -1, -1):
            self._stack.append((exprs[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("SPACE", ""), TraversalPhase.ENTER, context))

        for i in range(len(tokens) - 1, -1, -1):
            token = tokens[i]
            if token.value.lower() == "select":
                self._stack.append(
                    (
                        Token("SELECT", ("\t" * self._indent) + token.value),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((token, TraversalPhase.ENTER, context))

        return True

    def _where_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        where_token = self._find_token(tree, "WHERE")
        if where_token:
            self._parts.append(f"\n" + ("\t" * self._indent) + f"{where_token.value} ")

        # Traverse any children that are Trees (graph pattern)
        # Note: if there is a where token, the pattern is usually next, but we just traverse all children
        # except the where token? Actually existing logic pushed child[1].
        # Let's iterate and push non-WHERE children.
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not where_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _dataset_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        # Robustly find FROM or NAMED
        from_token = self._find_token(tree, "FROM")
        named_token = self._find_token(tree, "NAMED")

        if from_token:
            self._parts.append(f"{from_token.value} ")
        if named_token:
            self._parts.append(f"{named_token.value} ")

        # Traverse source selector (usually second child)
        # We can just push all children that are not the FROM/NAMED tokens
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not from_token and child is not named_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _dataset_clause_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        self._parts.append("\n")

    def _group_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        group_token = self._find_token(tree, "GROUP")
        by_token = self._find_token(tree, "BY")

        prefix = ""
        if group_token:
            prefix += f"{group_token.value} "
        if by_token:
            prefix += f"{by_token.value} "

        self._parts.append(("\t" * self._indent) + prefix)

        # Traverse children in reverse order, excluding keywords
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not group_token and child is not by_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _having_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        having_token = self._find_token(tree, "HAVING")
        if having_token:
            self._parts.append(f"\n" + ("\t" * self._indent) + f"{having_token.value} ")

        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not having_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _order_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        order_token = self._find_token(tree, "ORDER")
        by_token = self._find_token(tree, "BY")

        prefix = ""
        if order_token:
            prefix += f"{order_token.value} "
        if by_token:
            prefix += f"{by_token.value} "

        self._parts.append(f"\n" + ("\t" * self._indent) + prefix)

        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not order_token and child is not by_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _limit_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        limit_token = self._find_token(tree, "LIMIT")
        # INTEGER is a token type, not value. The value is variable.
        # But wait, limit_clause grammar is: /LIMIT/i INTEGER
        # So we have 2 children: Token(LIMIT), Token(INTEGER)

        # We can just append all children values since they are tokens
        self._parts.append(f"\n" + ("\t" * self._indent))
        for child in tree.children:
            if isinstance(child, Token):
                self._parts.append(f"{child.value} ")
        return True

    def _offset_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        # Same as limit: /OFFSET/i INTEGER
        self._parts.append(f"\n" + ("\t" * self._indent))
        for child in tree.children:
            if isinstance(child, Token):
                self._parts.append(f"{child.value} ")
        return True

    def _construct_construct_template_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            self._stack.append((tree.children[i], TraversalPhase.ENTER, context))
        return True

    def _construct_triples_template_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        """Handles the CONSTRUCT triples template.

        This complex handler manages the optional 'WHERE' keyword and the braces
        around the triples template. It explicitly pushes tokens and the triples_template
        node to the stack with proper indentation context.
        """
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                if child.value.lower() == "where":
                    self._stack.append(
                        (
                            Token(
                                "WHERE",
                                f"\n" + ("\t" * self._indent) + child.value + " ",
                            ),
                            TraversalPhase.ENTER,
                            context,
                        )
                    )
                else:
                    self._stack.append((child, TraversalPhase.ENTER, context))
            elif isinstance(child, Tree):
                if child.data == "triples_template":
                    # Manually add braces and indentation around triples_template
                    self._stack.append(
                        (
                            Token("RAW", f"\n{'\t' * self._indent}}}"),
                            TraversalPhase.ENTER,
                            context,
                        )
                    )
                    self._stack.append(
                        (child, TraversalPhase.ENTER, {"indent_inc": True})
                    )
                    self._stack.append(
                        (Token("RAW", "{\n"), TraversalPhase.ENTER, context)
                    )
                else:
                    self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _property_list_not_empty_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        verb_object_lists = [
            c
            for c in tree.children
            if isinstance(c, Tree) and c.data == "verb_object_list"
        ]
        for i in range(len(verb_object_lists) - 1, -1, -1):
            self._stack.append((verb_object_lists[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", "; "), TraversalPhase.ENTER, context))
        return True

    def _construct_triples_template_exit(
        self, tree: Tree, context: dict[str, Any]
    ) -> None:
        pass

    def _construct_template_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(" {\n")
        self._indent += 1
        for child in reversed(tree.children):
            if isinstance(child, Tree) and child.data == "construct_triples":
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _construct_template_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        self._indent -= 1
        self._parts.append(f"\n" + ("\t" * self._indent) + "}")

    def _construct_triples_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._stack.append((tree, TraversalPhase.EXIT, context))
        if len(tree.children) == 2:
            self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
            self._stack.append(
                (Token("DOT_NEWLINE", " .\n"), TraversalPhase.ENTER, context)
            )
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _group_graph_pattern_enter(self, tree: Tree, context: dict[str, Any]) -> None:
        self._parts.append(f"{'	' * self._indent}{{\n")
        self._indent += 1

    def _group_graph_pattern_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        self._indent -= 1
        self._parts.append(f"\n{'	' * self._indent}}}")

    def _group_graph_pattern_sub_other_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        self._parts.append("\n")
        for child in reversed(tree.children):
            if isinstance(child, Token) and child.type == "DOT":
                self._stack.append(
                    (
                        Token("DOT_NEWLINE", f"{'	' * self._indent}.\n"),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _triples_block_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._stack.append((tree, TraversalPhase.EXIT, context))
        if len(tree.children) == 2:
            self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
            self._stack.append(
                (Token("DOT_NEWLINE", " .\n"), TraversalPhase.ENTER, context)
            )
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _optional_graph_pattern_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        optional_token = tree.children[0]
        self._parts.append(f"{'	' * self._indent}{optional_token.value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _minus_graph_pattern_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        minus_token = tree.children[0]
        self._parts.append(f"{'	' * self._indent}{minus_token.value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _graph_graph_pattern_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        graph_token = tree.children[0]
        self._parts.append(f"{'	' * self._indent}{graph_token.value} ")
        self._stack.append((tree.children[2], TraversalPhase.ENTER, context))
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _group_or_union_graph_pattern_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token) and child.value.lower() == "union":
                self._stack.append(
                    (
                        Token("UNION", f"{'	' * self._indent}{child.value} "),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _service_graph_pattern_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token) and child.value.lower() == "service":
                self._stack.append(
                    (
                        Token("SERVICE", f"{'	' * self._indent}{child.value} "),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _filter_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        filter_token = tree.children[0]
        self._parts.append(f"{'	' * self._indent}{filter_token.value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _bind_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        bind_token = tree.children[0]
        as_token = tree.children[2]
        self._parts.append(f"{'	' * self._indent}{bind_token.value} (")
        self._stack.append((Token("RPAR", ") "), TraversalPhase.ENTER, context))
        self._stack.append((tree.children[3], TraversalPhase.ENTER, context))
        self._stack.append(
            (Token("AS", f" {as_token.value} "), TraversalPhase.ENTER, context)
        )
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _inline_data_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        values_token = tree.children[0]
        self._parts.append(f"{'	' * self._indent}{values_token.value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _values_clause_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        if not tree.children:
            return True
        values_token = tree.children[0]
        self._parts.append(f"{values_token.value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _triples_same_subject_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append("\t" * self._indent)
        return False

    def _triples_same_subject_path_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        self._parts.append("\t" * self._indent)
        return False

    def _triples_template_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        if context.get("indent_inc"):
            self._indent += 1
        self._stack.append((tree, TraversalPhase.EXIT, context))

        for child in reversed(tree.children):
            if isinstance(child, Token) and child.type == "DOT":
                self._stack.append(
                    (Token("DOT_NEWLINE", " .\n"), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _triples_template_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        if context.get("indent_inc"):
            self._indent -= 1

    def _property_list_path_not_empty_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            self._stack.append((tree.children[i], TraversalPhase.ENTER, context))
        return True

    def _property_list_path_not_empty_other_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        self._parts.append(f";\n{'	' * (self._indent + 1)}")
        return False

    def _verb_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        val = tree.children[0]
        if isinstance(val, Token) and val.type == "A":
            self._parts.append("a ")
            return True
        return False

    def _object_list_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            self._stack.append((child, TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", ", "), TraversalPhase.ENTER, context))
        return True

    def _object_list_path_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(" ")
        return False

    def _object_list_path_other_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        self._parts.append(", ")
        return False

    def _path_alternative_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        path_sequences = [
            c
            for c in tree.children
            if isinstance(c, Tree) and c.data == "path_sequence"
        ]
        for i in range(len(path_sequences) - 1, -1, -1):
            self._stack.append((path_sequences[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", "|"), TraversalPhase.ENTER, context))
        return True

    def _path_sequence_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        elts = [
            c
            for c in tree.children
            if isinstance(c, Tree) and c.data == "path_elt_or_inverse"
        ]
        for i in range(len(elts) - 1, -1, -1):
            self._stack.append((elts[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", "/"), TraversalPhase.ENTER, context))
        return True

    def _path_elt_or_inverse_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        if len(tree.children) == 2:  # CARET path_elt
            self._parts.append("^")
            self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
            return True
        return False  # path_elt

    def _path_mod_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(tree.children[0].value)
        return True

    def _path_primary_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        value = tree.children[0]
        if isinstance(value, Token) and value.type == "A":
            self._parts.append("a ")
            return True
        elif isinstance(value, Tree):
            if value.data == "iri":
                return False
            elif value.data == "path_negated_property_set":
                self._parts.append("!")
                return False
            elif value.data == "path":
                self._parts.append("(")
                self._stack.append((Token("RAW", ")"), TraversalPhase.ENTER, context))
                self._stack.append((value, TraversalPhase.ENTER, context))
                return True
        return False

    def _path_negated_property_set_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", child.value), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _path_one_in_property_set_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        if len(tree.children) == 2:  # CARET (iri | A)
            self._parts.append("^")
            value = tree.children[1]
        else:
            value = tree.children[0]

        if isinstance(value, Tree):
            self._parts.append(get_iri(value))
        else:
            self._parts.append("a")
        return True

    def _collection_path_enter(self, tree: Tree, context: dict[str, Any]) -> None:
        self._parts.append("(")

    def _collection_path_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        self._parts.append(") ")

    def _blank_node_property_list_path_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> None:
        self._parts.append("[")

    def _blank_node_property_list_path_exit(
        self, tree: Tree, context: dict[str, Any]
    ) -> None:
        self._parts.append("] ")

    def _collection_enter(self, tree: Tree, context: dict[str, Any]) -> None:
        self._parts.append("(")

    def _collection_exit(self, tree: Tree, context: dict[str, Any]) -> None:
        self._parts.append(") ")

    def _blank_node_property_list_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> None:
        self._parts.append("[")

    def _blank_node_property_list_exit(
        self, tree: Tree, context: dict[str, Any]
    ) -> None:
        self._parts.append("] ")

    def _conditional_or_expression_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _conditional_and_expression_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _relational_expression_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _additive_expression_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", child.value), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _multiplicative_expression_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", child.value), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _unary_expression_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", child.value), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _primary_expression_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _bracketted_expression_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append("(")
        self._stack.append((Token("RAW", ")"), TraversalPhase.ENTER, context))
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _built_in_call_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _aggregate_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _function_call_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        # function_call: iri arg_list
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _arg_list_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        # arg_list: "(" ( /DISTINCT/i? expression ( "," expression )* )? ")"
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            elif isinstance(child, Tree) and child.data == "expression":
                self._stack.append((child, TraversalPhase.ENTER, context))
                # Look ahead (actually look behind in the original list)
                if i > 0:
                    prev_child = tree.children[i - 1]
                    if isinstance(prev_child, Tree) and prev_child.data == "expression":
                        self._stack.append(
                            (Token("RAW", ", "), TraversalPhase.ENTER, context)
                        )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _substring_expression_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _str_replace_expression_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _regex_expression_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        exprs = [
            c for c in tree.children if isinstance(c, Tree) and c.data == "expression"
        ]
        regex_token = tree.children[0]
        self._parts.append(regex_token.value)

        self._stack.append((Token("RAW", ") "), TraversalPhase.ENTER, context))
        for i in range(len(exprs) - 1, -1, -1):
            self._stack.append((exprs[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", ", "), TraversalPhase.ENTER, context))
        self._parts.append("(")
        return True

    def _exists_func_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        exists_token = tree.children[0]
        self._parts.append(f"{'	' * self._indent}{exists_token.value}")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _not_exists_func_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        not_token = tree.children[0]
        exists_token = tree.children[1]
        self._parts.append(
            f"{'	' * self._indent}{not_token.value} {exists_token.value}"
        )
        self._stack.append((tree.children[2], TraversalPhase.ENTER, context))
        return True

    def _expression_list_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        exprs = [
            c for c in tree.children if isinstance(c, Tree) and c.data == "expression"
        ]

        self._stack.append((Token("RAW", ") "), TraversalPhase.ENTER, context))
        for i in range(len(exprs) - 1, -1, -1):
            self._stack.append((exprs[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", ", "), TraversalPhase.ENTER, context))
        self._parts.append("(")
        return True

    def _group_condition_expression_as_var_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", child.value), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _group_condition_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _having_condition_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _order_condition_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", f"{child.value} "), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _constraint_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False

    def _string_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(f"{tree.children[0].value} ")
        return True

    def _iri_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(f"{get_iri(tree)} ")
        return True

    def _select_clause_expression_as_var_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        # select_clause_expression_as_var: "(" expression /AS/i var ")"

        self._parts.append("(")
        self._stack.append((Token("RAW", ") "), TraversalPhase.ENTER, context))
        self._stack.append((tree.children[2], TraversalPhase.ENTER, context))
        self._stack.append(
            (
                Token("RAW", f" {tree.children[1].value} "),
                TraversalPhase.ENTER,
                context,
            )
        )
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _var_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(f"{get_var(tree)} ")
        return True

    def _rdf_literal_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(f"{get_rdf_literal(tree)} ")
        return True

    def _numeric_literal_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        val = tree.children[0].children[0]
        self._parts.append(f"{val.value} ")
        return True

    def _boolean_literal_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        val = tree.children[0].children[0]
        self._parts.append(f"{val.value} ")
        return True

    def _blank_node_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(f"{tree.children[0].value} ")
        return True

    def _anon_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append("[] ")
        return True

    def _nil_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append("() ")
        return True

    def _undef_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append("UNDEF ")
        return True

    def _iriref_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(f"{tree.children[0].value} ")
        return True

    def _prefixed_name_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._parts.append(f"{tree.children[0].value} ")
        return True

    def _inline_data_one_var_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        self._stack.append((tree, TraversalPhase.EXIT, context))
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                if child.value == "{":
                    self._stack.append(
                        (Token("RAW", "{\n"), TraversalPhase.ENTER, context)
                    )
                elif child.value == "}":
                    self._stack.append(
                        (
                            Token("RAW", f"\n{'	' * self._indent}}}"),
                            TraversalPhase.ENTER,
                            context,
                        )
                    )
            elif isinstance(child, Tree) and child.data == "data_block_value":
                self._stack.append((child, TraversalPhase.ENTER, context))
                self._stack.append(
                    (
                        Token("RAW", f"{'	' * (self._indent + 1)}"),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _inline_data_full_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        """Handles the full form of inline data (VALUES clause).

        This handler manually traverses children to correctly handle the structure:
        VALUES data_block_value_group { ( ... ) }
        It manages the braces and parentheses explicitly via RAW tokens.
        """
        self._stack.append((tree, TraversalPhase.EXIT, context))
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                if child.value == "{":
                    self._stack.append(
                        (Token("RAW", "{\n"), TraversalPhase.ENTER, context)
                    )
                elif child.value == "}":
                    self._stack.append(
                        (
                            Token("RAW", f"{'	' * self._indent}}}"),
                            TraversalPhase.ENTER,
                            context,
                        )
                    )
                elif child.value == "(":
                    self._stack.append(
                        (Token("RAW", "("), TraversalPhase.ENTER, context)
                    )
                elif child.value == ")":
                    self._stack.append(
                        (Token("RAW", ") "), TraversalPhase.ENTER, context)
                    )
                elif child.value == "()":
                    self._stack.append(
                        (Token("RAW", "() "), TraversalPhase.ENTER, context)
                    )
                else:
                    self._stack.append((child, TraversalPhase.ENTER, context))
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _data_block_value_group_enter(
        self, tree: Tree, context: dict[str, Any]
    ) -> bool:
        self._parts.append(f"{'	' * (self._indent + 1)}")
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                if child.value == "(":
                    self._stack.append(
                        (Token("RAW", "("), TraversalPhase.ENTER, context)
                    )
                elif child.value == ")":
                    self._stack.append(
                        (Token("RAW", ")\n"), TraversalPhase.ENTER, context)
                    )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _data_block_value_enter(self, tree: Tree, context: dict[str, Any]) -> bool:
        return False
