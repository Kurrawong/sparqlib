from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from typing import Any, TypedDict

from lark import Token, Tree


class SerializerError(Exception):
    """Raised when the serializer encounters an unexpected tree structure."""


class TraversalPhase(Enum):
    """Phases of tree traversal."""

    ENTER = auto()
    EXIT = auto()


class TreeHandler(TypedDict, total=False):
    """Handlers for entering and exiting a tree node."""

    enter: Callable[[Any, Tree[Any], dict[str, Any]], bool | None] | None
    exit: Callable[[Any, Tree[Any], dict[str, Any]], None] | None


class TraversalContext(TypedDict, total=False):
    """Context passed to tree handlers during traversal."""

    indent_inc: bool
    no_space_after: bool


def _safe_get_child(
    node: Tree[Any], index: int, expected_type: type | None = None, context: str = ""
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
        node_repr = node.data if hasattr(node, "data") else node
        raise SerializerError(
            f"Child index {index} out of range for node with "
            f"{len(node.children)} children"
            f"{f' in {context}' if context else ''}: {node_repr}"
        )
    child = node.children[index]
    if expected_type is not None and not isinstance(child, expected_type):
        raise SerializerError(
            f"Expected child of type {expected_type.__name__}, "
            f"got {type(child).__name__}{f' in {context}' if context else ''}"
        )
    return child


def get_prefixed_name(prefixed_name: Tree[Any]) -> str:
    """Extracts the value from a prefixed_name node."""

    child = _safe_get_child(prefixed_name, 0, Token, "prefixed_name")

    return str(child.value)


def get_iriref(iriref: Token) -> str:
    """Extracts the value from an iriref token."""

    return str(iriref.value)


def get_rdf_literal(rdf_literal: Tree[Any]) -> str:
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
                f"Unexpected langtag_or_datatype type in rdf_literal: "
                f"{type(langtag_or_datatype)}"
            )

    return str(value)


def get_value(
    tree: Tree[Any] | Token, memory: list[Token] | None = None
) -> list[Token]:
    """Iteratively walks a tree and collects all tokens.





    Uses a stack-based approach to avoid RecursionError on deeply nested trees.


    """

    if memory is None:
        memory = []

    stack: list[Tree[Any] | Token] = [tree]

    while stack:
        node = stack.pop()

        if isinstance(node, Token):
            memory.append(node)

        elif isinstance(node, Tree) and node.children:
            for child in reversed(node.children):
                if child is not None:
                    stack.append(child)

    return memory


def get_iri(iri: Tree[Any]) -> str:
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


def get_data_block_value(data_block_value: Tree[Any]) -> str:
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


def get_var(var: Tree[Any]) -> str:
    """Extracts the variable name from a var node."""

    child = _safe_get_child(var, 0, Token, "var")

    return str(child.value)


def get_vars(vars_: list[Tree[Any]]) -> str:
    """Joins variable names with spaces."""

    return " ".join(get_var(var) for var in vars_)


class IterativeTreeVisitor:
    """A generic iterative tree visitor that avoids recursion depth issues.

    This base class provides an explicit stack-based traversal engine for Lark
    parse trees, eliminating the risk of RecursionError for deeply nested structures.

    Subclasses should:
    1. Override `_build_handler_map()` to define handlers for specific node types
    2. Optionally override `_handle_token()` to customize token processing

    The visitor supports both ENTER and EXIT phases for each node, allowing
    pre-order and post-order processing logic.
    """

    _handler_cache: dict[type, dict[str, TreeHandler]] = {}

    # Tokens that should not have a space before them
    _NO_SPACE_BEFORE: frozenset[str] = frozenset(
        (")", "]", "}", ",", ";", "(", "[", "*", "+", "?", "/", "|")
    )
    # Tokens that should not have a space after them
    _NO_SPACE_AFTER: frozenset[str] = frozenset(("(", "["))

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._indent: int = 0
        self._no_space_after: bool = False  # State flag for space suppression
        self._stack: list[
            tuple[Tree[Any] | Token, TraversalPhase, dict[str, Any] | None]
        ] = []
        cls = self.__class__
        if cls not in IterativeTreeVisitor._handler_cache:
            IterativeTreeVisitor._handler_cache[cls] = self._build_handler_map()
        self._handler_map = IterativeTreeVisitor._handler_cache[cls]

    @property
    def result(self) -> str:
        """Returns the serialized result as a string."""
        return "".join(self._parts)

    def visit_topdown(self, tree: Tree[Any]) -> str:
        """Traverses the tree top-down iteratively and returns the serialized result.

        Args:
            tree: The Lark Tree to serialize.

        Returns:
            The serialized string.
        """
        self._parts = []
        self._indent = 0
        self._no_space_after = False
        self._stack = [(tree, TraversalPhase.ENTER, None)]

        while self._stack:
            node, phase, context = self._stack.pop()
            if isinstance(node, Tree):
                self._handle_tree(node, phase, context)
            else:
                self._handle_token(node)

        return self.result

    def _last_char(self) -> str | None:
        """Returns the last non-empty character in the output buffer."""
        for part in reversed(self._parts):
            if part:
                return part[-1]
        return None

    def _trim_trailing_space(self) -> None:
        """Removes trailing spaces from the last non-empty part."""
        for i in range(len(self._parts) - 1, -1, -1):
            part = self._parts[i]
            if part:
                if part.endswith(" "):
                    self._parts[i] = part.rstrip(" ")
                break

    def _handle_tree(
        self,
        node: Tree[Any],
        phase: TraversalPhase,
        context: dict[str, Any] | None,
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
        """Handles a Token by appending its value to the result parts.

        Uses state-aware spacing logic:
        - `_no_space_after` flag prevents trailing space when set by previous token
        - Tokens in `_NO_SPACE_BEFORE` never have a space before them
        - Tokens in `_NO_SPACE_AFTER` set the flag for the next token

        Subclasses may override this method to customize token handling.
        """
        if token.type == "DOT_NEWLINE":
            self._no_space_after = False
            self._parts.append(token.value)
        elif token.type == "SPACE":
            if self._no_space_after:
                return
            last_char = self._last_char()
            if (
                last_char is None
                or last_char.isspace()
                or last_char in self._NO_SPACE_AFTER
            ):
                return
            self._parts.append(" ")
        elif token.type == "RAW":
            first_char = token.value[0] if token.value else ""
            if first_char in self._NO_SPACE_BEFORE:
                self._trim_trailing_space()
            if token.value.startswith("\n"):
                self._trim_trailing_space()
            self._no_space_after = False
            self._parts.append(token.value)
        else:
            first_char = token.value[0] if token.value else ""
            should_suppress_leading_space = first_char in self._NO_SPACE_BEFORE

            if should_suppress_leading_space:
                self._trim_trailing_space()

            self._parts.append(token.value)

            if token.value in self._NO_SPACE_AFTER:
                self._no_space_after = True
            else:
                self._no_space_after = False
                self._parts.append(" ")

    def _build_handler_map(self) -> dict[str, TreeHandler]:
        """Builds a map of tree node types to their respective handlers.

        Subclasses should override this method to define handlers for their
        specific grammar rules.

        Returns:
            A dictionary mapping node type names to handler dictionaries with
            'enter' and 'exit' keys.
        """
        return {}


class SparqlSerializer(IterativeTreeVisitor):
    """An iterative SPARQL serializer that avoids recursion depth issues.

    This serializer extends IterativeTreeVisitor with SPARQL-specific formatting
    rules. It maintains exact output parity with the original recursive serializer
    while supporting arbitrarily complex structures.

    Example:
        >>> from sparqlkit.parser import sparql_query_parser
        >>> from sparqlkit.serializer import SparqlSerializer
        >>> tree = sparql_query_parser.parse("SELECT * WHERE { ?s ?p ?o }")
        >>> serializer = SparqlSerializer()
        >>> print(serializer.visit_topdown(tree))
    """

    # Prevent pathological output growth for extremely deep nesting (e.g. tests
    # that intentionally exceed recursion limits). Without a cap, indentation
    # grows with nesting depth, which can make the serialized string enormous
    # and dominate runtime when re-parsing.
    MAX_INDENT_LEVEL = 40
    KEYWORDS = frozenset(
        {
            "ADD",
            "ALL",
            "AS",
            "ASC",
            "ASK",
            "AVG",
            "BASE",
            "BIND",
            "BNODE",
            "BOUND",
            "BY",
            "CEIL",
            "CLEAR",
            "COALESCE",
            "CONCAT",
            "CONSTRUCT",
            "CONTAINS",
            "COPY",
            "COUNT",
            "CREATE",
            "DATA",
            "DATATYPE",
            "DAY",
            "DEFAULT",
            "DELETE",
            "DESC",
            "DESCRIBE",
            "DISTINCT",
            "DROP",
            "ENCODE_FOR_URI",
            "EXISTS",
            "FILTER",
            "FLOOR",
            "FROM",
            "GRAPH",
            "GROUP",
            "GROUP_CONCAT",
            "HAVING",
            "HOURS",
            "IF",
            "IN",
            "INSERT",
            "INTO",
            "IRI",
            "ISBLANK",
            "ISIRI",
            "ISLITERAL",
            "ISNUMERIC",
            "ISURI",
            "LANG",
            "LANGMATCHES",
            "LCASE",
            "LIMIT",
            "LOAD",
            "MAX",
            "MD5",
            "MIN",
            "MINUS",
            "MINUTES",
            "MONTH",
            "MOVE",
            "NAMED",
            "NOT",
            "NOW",
            "OFFSET",
            "OPTIONAL",
            "ORDER",
            "PREFIX",
            "RAND",
            "REDUCED",
            "REGEX",
            "REPLACE",
            "ROUND",
            "SAMPLE",
            "SAMETERM",
            "SECONDS",
            "SELECT",
            "SEPARATOR",
            "SERVICE",
            "SHA1",
            "SHA256",
            "SHA384",
            "SHA512",
            "SILENT",
            "STR",
            "STRAFTER",
            "STRBEFORE",
            "STRDT",
            "STRENDS",
            "STRLANG",
            "STRLEN",
            "STRSTARTS",
            "STRUUID",
            "SUBSTR",
            "SUM",
            "TIMEZONE",
            "TO",
            "TZ",
            "UCASE",
            "UNION",
            "URI",
            "USING",
            "UUID",
            "VALUES",
            "WHERE",
            "WITH",
            "YEAR",
        }
    )

    def __init__(self, preserve_comments: bool = True, indent: str = "  "):
        super().__init__()
        self._preserve_comments: bool = preserve_comments
        self._indent_str: str = indent
        self._comment_map: dict[Any, Any] | None = None
        self._comment_token_id_to_index: dict[int, int] = {}
        self._emitted_comment_indices: set[int] = set()
        self._inline_after_token: dict[int, list[str]] = {}
        self._inline_after_open_brace: dict[int, list[str]] = {}
        self._inline_after_close_paren: dict[int, list[str]] = {}
        self._open_brace_index: int = 0
        self._close_paren_index: int = 0
        self._pending_inline_comments_before_semicolon: list[str] | None = None

    def visit_topdown(self, tree: Tree[Any]) -> str:
        # Reset comment state per-visit.
        self._comment_map = None
        self._comment_token_id_to_index = {}
        self._emitted_comment_indices = set()
        self._inline_after_token = {}
        self._inline_after_open_brace = {}
        self._inline_after_close_paren = {}
        self._open_brace_index = 0
        self._close_paren_index = 0
        self._pending_inline_comments_before_semicolon = None

        if self._preserve_comments and hasattr(tree, "meta"):
            comment_map = getattr(tree.meta, "sparql_comments", None)
            token_ids = getattr(tree.meta, "sparql_comment_token_ids", None)
            if isinstance(comment_map, dict) and isinstance(token_ids, list):
                self._comment_map = comment_map
                self._comment_token_id_to_index = {
                    int(token_id): i for i, token_id in enumerate(token_ids)
                }
            inline_after_token = getattr(
                tree.meta, "sparql_inline_comments_after_token", None
            )
            if isinstance(inline_after_token, dict):
                self._inline_after_token = inline_after_token
            inline_after_open_brace = getattr(
                tree.meta, "sparql_inline_comments_after_open_brace", None
            )
            if isinstance(inline_after_open_brace, dict):
                self._inline_after_open_brace = inline_after_open_brace
            inline_after_close_paren = getattr(
                tree.meta, "sparql_inline_comments_after_close_paren", None
            )
            if isinstance(inline_after_close_paren, dict):
                self._inline_after_close_paren = inline_after_close_paren

        super().visit_topdown(tree)

        # Emit any EOF-anchored comments at the end (safe boundary).
        if self._preserve_comments and isinstance(self._comment_map, dict):
            eof_comments = self._comment_map.get("eof", [])
            if eof_comments:
                self._emit_comment_lines(eof_comments)

        return self.result

    def _peek_next_enter_node(self) -> Tree[Any] | Token | None:
        for node, phase, _context in reversed(self._stack):
            if phase == TraversalPhase.ENTER:
                return node
        return None

    def _emit_inline_comments_after_token(self, token: Token) -> None:
        if not self._preserve_comments:
            return
        idx = self._comment_token_id_to_index.get(id(token))
        if idx is None:
            return
        comments = self._inline_after_token.get(idx)
        if not comments:
            return

        # If the next emitted node is a serializer-injected semicolon delimiter,
        # delay emitting the inline comment so it can appear after the semicolon:
        #   ... obj ; # comment
        # rather than:
        #   ... obj # comment
        #   ;
        next_node = self._peek_next_enter_node()
        if self._pending_inline_comments_before_semicolon is None and (
            (
                isinstance(next_node, Token)
                and next_node.type == "RAW"
                and isinstance(next_node.value, str)
                and next_node.value.startswith(";")
                and "\n" in next_node.value
            )
            or (
                isinstance(next_node, Tree)
                and next_node.data == "property_list_path_not_empty_other"
            )
        ):
            self._pending_inline_comments_before_semicolon = list(comments)
            return

        # Inline comments must end the line.
        self._trim_trailing_space()
        for c in comments:
            self._parts.append(f" {c}")
        self._parts.append("\n")
        self._no_space_after = False

    def _emit_inline_comments_after_close_paren(self) -> bool:
        """Emit inline comments that were originally after ')'.

        Returns True if it emitted (and thus already handled line termination).
        """
        if not self._preserve_comments:
            return False
        self._close_paren_index += 1
        comments = self._inline_after_close_paren.get(self._close_paren_index)
        if not comments:
            return False
        self._trim_trailing_space()
        for c in comments:
            self._parts.append(f" {c}")
        self._parts.append("\n")
        self._no_space_after = False
        return True

    def _emit_comment_lines(self, comments: list[str]) -> None:
        """Emit comment lines at a safe boundary (start-of-line)."""
        if not comments:
            return

        carry_prefix: str | None = None
        have_prefix_on_current_line = False

        if not self._at_line_start():
            # If we're currently only in indentation whitespace (i.e., since the last
            # newline, only spaces/tabs were emitted), preserve that indentation for
            # the comment line and also carry it forward for the next token. This
            # prevents anchored comments from "eating" indentation that was emitted
            # in advance for the upcoming token.
            line_suffix_parts: list[str] = []
            for part in reversed(self._parts):
                if "\n" in part:
                    idx = part.rfind("\n")
                    line_suffix_parts.append(part[idx + 1 :])
                    break
                line_suffix_parts.append(part)
            line_suffix = "".join(reversed(line_suffix_parts))

            if line_suffix and line_suffix.strip() == "":
                carry_prefix = line_suffix
                have_prefix_on_current_line = True
            else:
                self._trim_trailing_space()
                self._parts.append("\n")

        for c in comments:
            # Comments are emitted as standalone lines. If we detected an existing
            # indentation-only prefix, reuse it; otherwise use current indent.
            if carry_prefix is not None and have_prefix_on_current_line:
                # Indentation whitespace is already present on the current line, so
                # don't duplicate it.
                self._parts.append(f"{c}\n")
            else:
                prefix = (
                    carry_prefix if carry_prefix is not None else self._indent_prefix()
                )
                self._parts.append(f"{prefix}{c}\n")
            if carry_prefix is not None:
                # Re-apply indentation for the next token on the following line.
                self._parts.append(carry_prefix)
                have_prefix_on_current_line = True

        # After emitting full lines, suppress any pending space.
        self._no_space_after = False

    def _emit_anchored_comments_for_token(self, token: Token) -> None:
        if not self._preserve_comments or not isinstance(self._comment_map, dict):
            return

        idx = self._comment_token_id_to_index.get(id(token))
        if idx is None or idx in self._emitted_comment_indices:
            return

        comments = self._comment_map.get(idx)
        if isinstance(comments, list) and comments:
            self._emit_comment_lines(comments)
        self._emitted_comment_indices.add(idx)

    def _format_keyword_value(self, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            return value
        upper = stripped.upper()
        if upper not in self.KEYWORDS:
            return value
        leading = value[: len(value) - len(value.lstrip())]
        trailing = value[len(value.rstrip()) :]
        return f"{leading}{upper}{trailing}"

    def _indent_prefix(self, extra: int = 0) -> str:
        level = self._indent + extra
        if level > self.MAX_INDENT_LEVEL:
            level = self.MAX_INDENT_LEVEL
        return self._indent_str * level

    def _at_line_start(self) -> bool:
        last_char = self._last_char()
        return last_char is None or last_char == "\n"

    def _open_brace(self) -> None:
        self._open_brace_index += 1
        inline = self._inline_after_open_brace.get(self._open_brace_index, [])

        if self._at_line_start():
            self._parts.append(f"{self._indent_prefix()}{{")
        else:
            self._parts.append("{")

        if inline:
            for c in inline:
                self._parts.append(f" {c}")
        self._parts.append("\n")

    def _raw_token_value(self, value: str) -> str:
        """Converts a token value to a string with appropriate spacing."""
        if value in ("(", ")"):
            return value
        if value == ",":
            return ", "
        return f"{self._format_keyword_value(value)} "

    def _handle_token(self, token: Token) -> None:
        """Handles a Token by appending its value to the result parts."""
        if self._preserve_comments:
            if token.type == "COMMENT":
                self._emit_comment_lines([token.value])
                return
            self._emit_anchored_comments_for_token(token)

        token_value = self._format_keyword_value(token.value)
        if token.type == "DOT_NEWLINE":
            self._no_space_after = False
            # Some serializer-injected DOT_NEWLINE tokens include a leading space
            # (e.g. " .\n"). If the previous emitter already ended with whitespace
            # (like a blank-node close handler appending "] "), drop that leading
            # space to avoid double spaces ("]  .").
            if token_value.startswith(" "):
                last_char = self._last_char()
                if last_char is not None and last_char.isspace():
                    token_value = token_value[1:]
            self._parts.append(token_value)
        elif token.type == "SPACE":
            if self._no_space_after:
                return
            last_char = self._last_char()
            if (
                last_char is None
                or last_char.isspace()
                or last_char in self._NO_SPACE_AFTER
            ):
                return
            self._parts.append(" ")
        elif token.type == "SELECT_ASTERIX":
            # Special case for SELECT * - don't strip the leading space
            self._parts.append(token_value)
            self._no_space_after = False
            self._parts.append(" ")
        elif token.type == "RAW":
            if (
                self._pending_inline_comments_before_semicolon
                and isinstance(token_value, str)
                and token_value.startswith(";")
                and "\n" in token_value
            ):
                head, tail = token_value.split("\n", 1)
                self._parts.append(head)
                for c in self._pending_inline_comments_before_semicolon:
                    self._parts.append(f" {c}")
                self._parts.append("\n")
                if tail:
                    self._parts.append(tail)
                self._pending_inline_comments_before_semicolon = None
                self._no_space_after = False
                return

            # Special case: RAW ')' is commonly used by handlers instead of the
            # original token. If there's an inline comment that was after ')',
            # emit it here.
            if token_value in (")", ") ", ")\n"):
                # Emit the ')' itself.
                self._trim_trailing_space()
                self._parts.append(")")
                emitted = self._emit_inline_comments_after_close_paren()
                if emitted:
                    # Swallow any trailing space/newline that would have come from RAW.
                    return
                # If original RAW included newline, keep it; otherwise keep trailing
                # space if present.
                if token_value.endswith("\n"):
                    self._parts.append("\n")
                elif token_value.endswith(" "):
                    self._parts.append(" ")
                return

            first_char = token_value[0] if token_value else ""
            if first_char in self._NO_SPACE_BEFORE:
                self._trim_trailing_space()
            if token_value.startswith("\n"):
                self._trim_trailing_space()
            self._no_space_after = False
            self._parts.append(token_value)
        else:
            first_char = token_value[0] if token_value else ""
            should_suppress_leading_space = first_char in self._NO_SPACE_BEFORE

            if should_suppress_leading_space:
                self._trim_trailing_space()

            self._parts.append(token_value)

            if token_value in self._NO_SPACE_AFTER:
                self._no_space_after = True
            else:
                self._no_space_after = False
                self._parts.append(" ")

        if self._preserve_comments:
            self._emit_inline_comments_after_token(token)

    def _build_handler_map(self) -> dict[str, TreeHandler]:
        """Builds a map of tree node types to their respective handlers.

        Subclasses can override this method to add or modify handlers.

        Note: Grammar rules not listed here use the default behavior (traverse
        children and emit tokens). This is intentional for:
        - Simple pass-through rules (base_decl, prefix_decl, source_selector, etc.)
        - Sub-rules handled by parent handlers (numeric_literal_*, true, false)
        - Expression sub-rules (numeric_expression_equals, etc.) which are
          children of rules that already have handlers
        """
        cls = self.__class__
        return {
            "unit": {"enter": None, "exit": None},
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
                "exit": cls._property_list_path_not_empty_other_exit,
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
        self, node: Tree[Any], child_type: str | type, index: int = 0
    ) -> Tree[Any] | Token | None:
        """Safely find a child of a specific type (Tree data or Token type)."""
        count = 0
        for child in node.children:
            match = False
            if isinstance(child_type, str):
                if (
                    isinstance(child, Tree)
                    and child.data == child_type
                    or isinstance(child, Token)
                    and child.type == child_type
                ):
                    match = True
            elif isinstance(child, child_type):
                match = True

            if match:
                if count == index:
                    return child
                count += 1
        return None

    def _find_token(self, node: Tree[Any], value: str) -> Token | None:
        """Find a token child with a specific value (case-insensitive)."""
        for child in node.children:
            if isinstance(child, Token) and child.value.lower() == value.lower():
                return child
        return None

    def _insert_data_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _delete_data_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _delete_where_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _modify_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        items: list[Tree[Any] | Token] = []
        children = tree.children
        i = 0
        while i < len(children):
            child = children[i]
            if isinstance(child, Token) and child.value.lower() == "with":
                prefix = (
                    self._indent_prefix()
                    if self._at_line_start()
                    else f"\n{self._indent_prefix()}"
                )
                items.append(Token("RAW", prefix))
                items.append(child)
                if i + 1 < len(children):
                    items.append(children[i + 1])
                    i += 1
            elif isinstance(child, Token) and child.value.lower() == "where":
                items.append(Token("RAW", f"\n{self._indent_prefix()}"))
                items.append(child)
            else:
                items.append(child)
            i += 1

        for item in reversed(items):
            self._stack.append((item, TraversalPhase.ENTER, context))
        return True

    def _delete_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        delete_token = self._find_token(tree, "DELETE")
        if delete_token:
            self._emit_anchored_comments_for_token(delete_token)
            self._trim_trailing_space()
            if not self._at_line_start():
                self._parts.append("\n")
            delete_value = self._format_keyword_value(delete_token.value)
            self._parts.append(f"{self._indent_prefix()}{delete_value} ")

        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not delete_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _insert_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        insert_token = self._find_token(tree, "INSERT")
        if insert_token:
            self._emit_anchored_comments_for_token(insert_token)
            self._trim_trailing_space()
            if not self._at_line_start():
                self._parts.append("\n")
            insert_value = self._format_keyword_value(insert_token.value)
            self._parts.append(f"{self._indent_prefix()}{insert_value} ")

        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not insert_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _using_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _quad_data_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        self._open_brace()
        self._indent += 1
        # Robustly find the child to traverse (the ones inside braces)
        # Assuming structure: LEFT_CURLY_BRACE quads RIGHT_CURLY_BRACE
        # We want to traverse 'quads'
        quads = self._safe_get_child_by_type(tree, "quads")
        if quads:
            self._stack.append((quads, TraversalPhase.ENTER, context))
        return True

    def _quad_data_exit(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        self._indent -= 1
        self._trim_trailing_space()
        self._parts.append(f"\n{self._indent_prefix()}}}")

    def _quad_pattern_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        self._open_brace()
        self._indent += 1
        # Robustly find 'quads'
        quads = self._safe_get_child_by_type(tree, "quads")
        if quads:
            self._stack.append((quads, TraversalPhase.ENTER, context))
        return True

    def _quad_pattern_exit(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        self._indent -= 1
        self._trim_trailing_space()
        self._parts.append(f"\n{self._indent_prefix()}}}")

    def _quads_not_triples_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        """Handles quads that are not triples, manually injecting braces and indent.

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
                            Token("RAW", f"\n{self._indent_prefix()}}}"),
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

    def _update_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        """Handles the top-level update node.

        Injects semicolons between operations.
        """
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token) and child.value == ";":
                self._stack.append((Token("RAW", ";\n"), TraversalPhase.ENTER, context))
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _load_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _clear_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _drop_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _add_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _move_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _copy_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _create_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _graph_ref_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _graph_ref_all_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _graph_or_default_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _prologue_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
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
            base_node = _safe_get_child(base_decl, 0, Tree, "base_decl")
            base_token = _safe_get_child(base_node, 0, Token, "base")
            iriref_token = _safe_get_child(base_decl, 1, Token, "base_decl.iriref")
            self._emit_anchored_comments_for_token(base_token)
            base_value = self._format_keyword_value(base_token.value)
            self._parts.append(f"{base_value} {iriref_token.value}\n")

        for prefix_decl in prefix_decls:
            prefix_node = _safe_get_child(prefix_decl, 0, Tree, "prefix_decl")
            prefix_token = _safe_get_child(prefix_node, 0, Token, "prefix")
            pname_ns_node = _safe_get_child(
                prefix_decl, 1, Tree, "prefix_decl.pname_ns"
            )
            pname_ns_token = _safe_get_child(pname_ns_node, 0, Token, "pname_ns")
            iriref_token = _safe_get_child(prefix_decl, 2, Token, "prefix_decl.iriref")
            self._emit_anchored_comments_for_token(prefix_token)
            prefix_value = self._format_keyword_value(prefix_token.value)
            self._parts.append(
                f"{prefix_value} {pname_ns_token.value} {iriref_token.value}\n"
            )

        self._parts.append("\n")
        return True

    def _select_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
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
                # Preserve the original token instance so comment anchoring works.
                self._stack.append((token, TraversalPhase.ENTER, context))
                self._stack.append(
                    (Token("RAW", self._indent_prefix()), TraversalPhase.ENTER, context)
                )
            elif token.type == "ASTERIX":
                # Ensure space before ASTERIX (e.g., "SELECT *" not "SELECT*")
                # Use SELECT_ASTERIX type to avoid _NO_SPACE_BEFORE stripping
                self._stack.append(
                    (Token("SELECT_ASTERIX", "*"), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((token, TraversalPhase.ENTER, context))

        return True

    def _where_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        where_token = self._find_token(tree, "WHERE")
        if where_token:
            self._emit_anchored_comments_for_token(where_token)
            self._trim_trailing_space()
            where_value = self._format_keyword_value(where_token.value)
            if self._at_line_start():
                self._parts.append(f"{self._indent_prefix()}{where_value} ")
            else:
                self._parts.append(f"\n{self._indent_prefix()}{where_value} ")

        # Traverse any children that are Trees (graph pattern)
        # Note: if there is a where token, the pattern is usually next, but we just
        # traverse all children except the where token? Actually existing logic pushed
        # child[1]. Let's iterate and push non-WHERE children.
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not where_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _dataset_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # Robustly find FROM or NAMED
        from_token = self._find_token(tree, "FROM")
        named_token = self._find_token(tree, "NAMED")

        # Each FROM clause should start on a new line
        self._trim_trailing_space()
        if not self._at_line_start():
            self._parts.append("\n")

        if from_token:
            self._emit_anchored_comments_for_token(from_token)
            from_value = self._format_keyword_value(from_token.value)
            self._parts.append(f"{from_value} ")
        if named_token:
            self._emit_anchored_comments_for_token(named_token)
            named_value = self._format_keyword_value(named_token.value)
            self._parts.append(f"{named_value} ")

        # Traverse source selector (usually second child)
        # We can just push all children that are not the FROM/NAMED tokens
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not from_token and child is not named_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _dataset_clause_exit(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        self._trim_trailing_space()

    def _group_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        group_token = self._find_token(tree, "GROUP")
        by_token = self._find_token(tree, "BY")

        prefix = ""
        if group_token:
            self._emit_anchored_comments_for_token(group_token)
            prefix += f"{self._format_keyword_value(group_token.value)} "
        if by_token:
            self._emit_anchored_comments_for_token(by_token)
            prefix += f"{self._format_keyword_value(by_token.value)} "

        # GROUP BY is a solution modifier and should always start on its own line.
        self._trim_trailing_space()
        if self._at_line_start():
            self._parts.append(f"{self._indent_prefix()}{prefix}")
        else:
            self._parts.append(f"\n{self._indent_prefix()}{prefix}")

        # Traverse children in reverse order, excluding keywords
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not group_token and child is not by_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _having_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        having_token = self._find_token(tree, "HAVING")
        if having_token:
            self._emit_anchored_comments_for_token(having_token)
            self._trim_trailing_space()
            having_value = self._format_keyword_value(having_token.value)
            if self._at_line_start():
                self._parts.append(f"{self._indent_prefix()}{having_value} ")
            else:
                self._parts.append(f"\n{self._indent_prefix()}{having_value} ")

        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not having_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _order_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        order_token = self._find_token(tree, "ORDER")
        by_token = self._find_token(tree, "BY")

        prefix = ""
        if order_token:
            self._emit_anchored_comments_for_token(order_token)
            prefix += f"{self._format_keyword_value(order_token.value)} "
        if by_token:
            self._emit_anchored_comments_for_token(by_token)
            prefix += f"{self._format_keyword_value(by_token.value)} "

        self._trim_trailing_space()
        if self._at_line_start():
            self._parts.append(f"{self._indent_prefix()}{prefix}")
        else:
            self._parts.append(f"\n{self._indent_prefix()}{prefix}")

        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if child is not order_token and child is not by_token:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _limit_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # INTEGER is a token type, not value. The value is variable.
        # But wait, limit_clause grammar is: /LIMIT/i INTEGER
        # So we have 2 children: Token(LIMIT), Token(INTEGER)

        # We can just append all children values since they are tokens
        self._trim_trailing_space()
        self._parts.append(f"\n{self._indent_prefix()}")
        for child in tree.children:
            if isinstance(child, Token):
                child_value = self._format_keyword_value(child.value)
                self._parts.append(f"{child_value} ")
        return True

    def _offset_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # Same as limit: /OFFSET/i INTEGER
        self._trim_trailing_space()
        self._parts.append(f"\n{self._indent_prefix()}")
        for child in tree.children:
            if isinstance(child, Token):
                child_value = self._format_keyword_value(child.value)
                self._parts.append(f"{child_value} ")
        return True

    def _construct_construct_template_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            self._stack.append((tree.children[i], TraversalPhase.ENTER, context))
        return True

    def _construct_triples_template_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        """Handles the CONSTRUCT triples template.

        This complex handler manages the optional 'WHERE' keyword and the braces
        around the triples template. It explicitly pushes tokens and the
        triples_template node to the stack with proper indentation context.
        """
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                if child.value.lower() == "where":
                    self._stack.append(
                        (
                            Token(
                                "WHERE",
                                f"\n{self._indent_prefix()}{child.value}",
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
                            Token("RAW", f"\n{self._indent_prefix()}}}"),
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
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        verb_object_lists = [
            c
            for c in tree.children
            if isinstance(c, Tree) and c.data == "verb_object_list"
        ]
        for i in range(len(verb_object_lists) - 1, -1, -1):
            self._stack.append((verb_object_lists[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append(
                    (
                        Token("RAW", f";\n{self._indent_prefix()}"),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
        return True

    def _construct_triples_template_exit(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        pass

    def _construct_template_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        self._parts.append(" {\n")
        self._indent += 1
        for child in reversed(tree.children):
            if isinstance(child, Tree) and child.data == "construct_triples":
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _construct_template_exit(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._indent -= 1
        self._trim_trailing_space()
        self._parts.append(f"\n{self._indent_prefix()}}}")

    def _construct_triples_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        self._stack.append((tree, TraversalPhase.EXIT, context))
        if len(tree.children) == 2:
            self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
            self._stack.append(
                (Token("DOT_NEWLINE", " .\n"), TraversalPhase.ENTER, context)
            )
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _group_graph_pattern_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._open_brace_index += 1
        inline = self._inline_after_open_brace.get(self._open_brace_index, [])
        if self._is_empty_group_graph_pattern(tree) and not inline:
            if self._stack and self._stack[-1][0] is tree:
                node, phase, _ctx = self._stack[-1]
                if phase == TraversalPhase.EXIT:
                    self._stack.pop()
            if self._at_line_start():
                self._parts.append(f"{self._indent_prefix()}{{}}")
            else:
                self._parts.append("{}")
            return

        if self._at_line_start():
            self._parts.append(f"{self._indent_prefix()}{{")
        else:
            self._parts.append("{")

        if inline:
            for c in inline:
                self._parts.append(f" {c}")
        self._parts.append("\n")
        self._indent += 1

    def _group_graph_pattern_exit(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._indent -= 1
        self._trim_trailing_space()
        if self._at_line_start():
            self._parts.append(f"{self._indent_prefix()}}}")
        else:
            self._parts.append(f"\n{self._indent_prefix()}}}")

    def _is_empty_group_graph_pattern(self, tree: Tree[Any]) -> bool:
        for child in tree.children:
            if isinstance(child, Tree):
                if child.data == "sub_select":
                    return False
                if child.data == "group_graph_pattern_sub":
                    return len(child.children) == 0
                return False
        return False

    def _group_graph_pattern_sub_other_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        if not self._at_line_start():
            self._trim_trailing_space()
            self._parts.append("\n")

        # `group_graph_pattern_sub_other` has the grammar shape:
        #   graph_pattern_not_triples DOT? triples_block?
        #
        # When a `graph_pattern_not_triples` (e.g. inline_data / VALUES) is followed
        # by DOT and/or a `triples_block`, ensure we start the following part on a
        # new line so we don't end up with `}  ?s ?p ?o`.
        children_to_emit: list[Tree[Any] | Token] = []
        for i, child in enumerate(tree.children):
            children_to_emit.append(child)
            if (
                i == 0
                and isinstance(child, Tree)
                and child.data == "graph_pattern_not_triples"
                and i + 1 < len(tree.children)
            ):
                next_child = tree.children[i + 1]
                if (isinstance(next_child, Token) and next_child.type == "DOT") or (
                    isinstance(next_child, Tree) and next_child.data == "triples_block"
                ):
                    # Use RAW newline so token handling trims trailing whitespace.
                    children_to_emit.append(Token("RAW", "\n"))

        for child in reversed(children_to_emit):
            if isinstance(child, Token) and child.type == "DOT":
                self._stack.append(
                    (
                        Token("DOT_NEWLINE", f"{self._indent_prefix()}.\n"),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _triples_block_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        self._stack.append((tree, TraversalPhase.EXIT, context))
        if len(tree.children) == 2:
            self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
            self._stack.append(
                (Token("DOT_NEWLINE", " .\n"), TraversalPhase.ENTER, context)
            )
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _optional_graph_pattern_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        optional_token = tree.children[0]
        if isinstance(optional_token, Token):
            self._emit_anchored_comments_for_token(optional_token)
        assert isinstance(optional_token, Token)
        optional_value = self._format_keyword_value(optional_token.value)
        self._parts.append(f"{self._indent_prefix()}{optional_value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _minus_graph_pattern_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        minus_token = tree.children[0]
        if isinstance(minus_token, Token):
            self._emit_anchored_comments_for_token(minus_token)
        assert isinstance(minus_token, Token)
        minus_value = self._format_keyword_value(minus_token.value)
        self._parts.append(f"{self._indent_prefix()}{minus_value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _graph_graph_pattern_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        graph_token = tree.children[0]
        if isinstance(graph_token, Token):
            self._emit_anchored_comments_for_token(graph_token)
        assert isinstance(graph_token, Token)
        graph_value = self._format_keyword_value(graph_token.value)
        self._parts.append(f"{self._indent_prefix()}{graph_value} ")
        self._stack.append((tree.children[2], TraversalPhase.ENTER, context))
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _group_or_union_graph_pattern_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token) and child.value.lower() == "union":
                # Preserve original token instance for comment anchoring.
                self._stack.append((child, TraversalPhase.ENTER, context))
                # Put UNION on its own line at the current indentation level.
                # Note: this is computed during ENTER, before children are emitted,
                # so we must include the newline unconditionally to avoid
                # `}    UNION {`.
                self._stack.append(
                    (
                        Token("RAW", f"\n{self._indent_prefix()}"),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _service_graph_pattern_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token) and child.value.lower() == "service":
                # Preserve original token instance for comment anchoring.
                self._stack.append((child, TraversalPhase.ENTER, context))
                self._stack.append(
                    (Token("RAW", self._indent_prefix()), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _filter_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        filter_token = tree.children[0]
        if isinstance(filter_token, Token):
            self._emit_anchored_comments_for_token(filter_token)
        assert isinstance(filter_token, Token)
        filter_value = self._format_keyword_value(filter_token.value)
        self._parts.append(f"{self._indent_prefix()}{filter_value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _bind_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        bind_token = _safe_get_child(tree, 0, Token, "bind")
        expression = _safe_get_child(tree, 1, Tree, "bind.expression")
        as_token = _safe_get_child(tree, 2, Token, "bind")
        var = _safe_get_child(tree, 3, Tree, "bind.var")

        self._emit_anchored_comments_for_token(bind_token)
        bind_value = self._format_keyword_value(bind_token.value)
        as_value = self._format_keyword_value(as_token.value)
        self._parts.append(f"{self._indent_prefix()}{bind_value} (")
        self._stack.append((Token("RPAR", ") "), TraversalPhase.ENTER, context))
        self._stack.append((var, TraversalPhase.ENTER, context))
        self._stack.append(
            (Token("RAW", f" {as_value} "), TraversalPhase.ENTER, context)
        )
        self._stack.append((expression, TraversalPhase.ENTER, context))
        return True

    def _inline_data_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        values_token = tree.children[0]
        if isinstance(values_token, Token):
            self._emit_anchored_comments_for_token(values_token)
        assert isinstance(values_token, Token)
        values_value = self._format_keyword_value(values_token.value)
        self._parts.append(f"{self._indent_prefix()}{values_value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _values_clause_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        if not tree.children:
            return True
        values_token = tree.children[0]
        if isinstance(values_token, Token):
            self._emit_anchored_comments_for_token(values_token)
        assert isinstance(values_token, Token)
        values_value = self._format_keyword_value(values_token.value)
        self._parts.append(f"{values_value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _triples_same_subject_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        self._parts.append(self._indent_prefix())
        return False

    def _triples_same_subject_path_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        self._parts.append(self._indent_prefix())
        return False

    def _triples_template_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
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

    def _triples_template_exit(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        if context.get("indent_inc"):
            self._indent -= 1

    def _property_list_path_not_empty_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            self._stack.append((tree.children[i], TraversalPhase.ENTER, context))
        return True

    def _property_list_path_not_empty_other_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        self._indent += 1
        if self._pending_inline_comments_before_semicolon:
            self._parts.append(";")
            for c in self._pending_inline_comments_before_semicolon:
                self._parts.append(f" {c}")
            self._parts.append("\n")
            self._parts.append(self._indent_prefix())
            self._pending_inline_comments_before_semicolon = None
        else:
            self._parts.append(f";\n{self._indent_prefix()}")
        return False

    def _property_list_path_not_empty_other_exit(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._indent -= 1

    def _verb_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        val = tree.children[0]
        if isinstance(val, Token) and val.type == "A":
            self._parts.append("a ")
            return True
        return False

    def _object_list_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            self._stack.append((child, TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", ", "), TraversalPhase.ENTER, context))
        return True

    def _object_list_path_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # Avoid introducing double spaces in `?s ?p ?o` patterns: the token handler
        # already emits trailing spaces for most tokens.
        last_char = self._last_char()
        if (
            last_char is None
            or last_char.isspace()
            or last_char in self._NO_SPACE_AFTER
        ):
            return False
        self._parts.append(" ")
        return False

    def _object_list_path_other_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        self._parts.append(", ")
        return False

    def _path_alternative_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
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

    def _path_sequence_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
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

    def _path_elt_or_inverse_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        if len(tree.children) == 2:  # CARET path_elt
            self._parts.append("^")
            self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
            return True
        return False  # path_elt

    def _path_mod_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        self._trim_trailing_space()
        child = tree.children[0]
        assert isinstance(child, Token)
        self._parts.append(child.value)
        return True

    def _path_primary_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
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
        self, tree: Tree[Any], context: dict[str, Any]
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
        self, tree: Tree[Any], context: dict[str, Any]
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

    def _collection_path_enter(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        self._parts.append("(")

    def _collection_path_exit(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        self._parts.append(") ")

    def _blank_node_property_list_path_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._parts.append("[\n")
        self._indent += 1
        self._parts.append(self._indent_prefix())

    def _blank_node_property_list_path_exit(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._indent -= 1
        self._trim_trailing_space()
        self._parts.append(f"\n{self._indent_prefix()}] ")

    def _collection_enter(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        self._parts.append("(")

    def _collection_exit(self, tree: Tree[Any], context: dict[str, Any]) -> None:
        self._parts.append(") ")

    def _blank_node_property_list_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._parts.append("[\n")
        self._indent += 1
        self._parts.append(self._indent_prefix())

    def _blank_node_property_list_exit(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> None:
        self._indent -= 1
        self._trim_trailing_space()
        self._parts.append(f"\n{self._indent_prefix()}] ")

    def _conditional_or_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _conditional_and_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _relational_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _additive_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
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

    def _multiplicative_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
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

    def _unary_expression_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (Token("RAW", child.value), TraversalPhase.ENTER, context)
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _primary_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        return False

    def _bracketted_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        self._parts.append("(")
        self._stack.append((Token("RAW", ")"), TraversalPhase.ENTER, context))
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _built_in_call_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _aggregate_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _function_call_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # function_call: iri arg_list
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _arg_list_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # arg_list: "(" ( /DISTINCT/i? expression ( "," expression )* )? ")"
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                token_value = self._raw_token_value(child.value)
                self._stack.append(
                    (Token("RAW", token_value), TraversalPhase.ENTER, context)
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

    def _substring_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _str_replace_expression_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _regex_expression_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        exprs = [
            c for c in tree.children if isinstance(c, Tree) and c.data == "expression"
        ]
        regex_token = tree.children[0]
        assert isinstance(regex_token, Token)
        regex_value = self._format_keyword_value(regex_token.value)
        self._parts.append(regex_value)

        self._stack.append((Token("RAW", ") "), TraversalPhase.ENTER, context))
        for i in range(len(exprs) - 1, -1, -1):
            self._stack.append((exprs[i], TraversalPhase.ENTER, context))
            if i > 0:
                self._stack.append((Token("RAW", ", "), TraversalPhase.ENTER, context))
        self._parts.append("(")
        return True

    def _exists_func_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        exists_token = tree.children[0]
        assert isinstance(exists_token, Token)
        self._emit_anchored_comments_for_token(exists_token)
        exists_value = self._format_keyword_value(exists_token.value)
        # `EXISTS` is an expression (used inside FILTER/HAVING/etc), so it should not
        # inject indentation mid-line. It also requires a space before the following
        # group graph pattern: `EXISTS { ... }`.
        self._parts.append(f"{exists_value} ")
        self._stack.append((tree.children[1], TraversalPhase.ENTER, context))
        return True

    def _not_exists_func_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        not_token = tree.children[0]
        exists_token = tree.children[1]
        assert isinstance(not_token, Token)
        assert isinstance(exists_token, Token)
        self._emit_anchored_comments_for_token(not_token)
        self._emit_anchored_comments_for_token(exists_token)
        not_value = self._format_keyword_value(not_token.value)
        exists_value = self._format_keyword_value(exists_token.value)
        # `NOT EXISTS` is an expression (used inside FILTER/HAVING/etc), so it should
        # not inject indentation mid-line. It also requires a space before the
        # following group graph pattern: `NOT EXISTS { ... }`.
        self._parts.append(f"{not_value} {exists_value} ")
        self._stack.append((tree.children[2], TraversalPhase.ENTER, context))
        return True

    def _expression_list_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
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
        self, tree: Tree[Any], context: dict[str, Any]
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

    def _group_condition_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _having_condition_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _order_condition_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token):
                self._stack.append(
                    (
                        Token("RAW", self._raw_token_value(child.value)),
                        TraversalPhase.ENTER,
                        context,
                    )
                )
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _constraint_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False

    def _string_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        child = _safe_get_child(tree, 0, Token, "string")
        self._emit_anchored_comments_for_token(child)
        self._parts.append(f"{child.value} ")
        self._emit_inline_comments_after_token(child)
        return True

    def _iri_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # Preserve comment anchoring by emitting comments before the underlying token.
        if not tree.children:
            raise SerializerError(f"iri node has no children: {tree}")

        value = tree.children[0]
        if isinstance(value, Token):
            self._emit_anchored_comments_for_token(value)
            self._parts.append(f"{value.value} ")
            self._emit_inline_comments_after_token(value)
            return True
        if isinstance(value, Tree) and value.data == "prefixed_name":
            tok = _safe_get_child(value, 0, Token, "prefixed_name")
            self._emit_anchored_comments_for_token(tok)
            self._parts.append(f"{tok.value} ")
            self._emit_inline_comments_after_token(tok)
            return True

        # Fallback (shouldn't happen with current grammar).
        self._parts.append(f"{get_iri(tree)} ")
        return True

    def _select_clause_expression_as_var_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        # select_clause_expression_as_var: "(" expression /AS/i var ")"

        self._parts.append("(")
        self._stack.append((Token("RAW", ") "), TraversalPhase.ENTER, context))
        self._stack.append((tree.children[2], TraversalPhase.ENTER, context))
        as_token = tree.children[1]
        assert isinstance(as_token, Token)
        self._stack.append(
            (
                Token("RAW", f" {self._format_keyword_value(as_token.value)} "),
                TraversalPhase.ENTER,
                context,
            )
        )
        self._stack.append((tree.children[0], TraversalPhase.ENTER, context))
        return True

    def _var_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        child = _safe_get_child(tree, 0, Token, "var")
        self._emit_anchored_comments_for_token(child)
        self._parts.append(f"{child.value} ")
        self._emit_inline_comments_after_token(child)
        return True

    def _rdf_literal_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        # Anchor to the opening string token of the literal.
        string_node = _safe_get_child(tree, 0, Tree, "rdf_literal.string")
        value_token = _safe_get_child(string_node, 0, Token, "rdf_literal.string.value")
        self._emit_anchored_comments_for_token(value_token)
        self._parts.append(f"{get_rdf_literal(tree)} ")
        self._emit_inline_comments_after_token(value_token)
        return True

    def _numeric_literal_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        child_tree = _safe_get_child(tree, 0, Tree, "numeric_literal")
        val = _safe_get_child(child_tree, 0, Token, "numeric_literal.value")
        self._emit_anchored_comments_for_token(val)
        self._parts.append(f"{val.value} ")
        self._emit_inline_comments_after_token(val)
        return True

    def _boolean_literal_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        child_tree = _safe_get_child(tree, 0, Tree, "boolean_literal")
        val = _safe_get_child(child_tree, 0, Token, "boolean_literal.value")
        self._emit_anchored_comments_for_token(val)
        self._parts.append(f"{val.value} ")
        self._emit_inline_comments_after_token(val)
        return True

    def _blank_node_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        child = _safe_get_child(tree, 0, Token, "blank_node")
        self._emit_anchored_comments_for_token(child)
        self._parts.append(f"{child.value} ")
        self._emit_inline_comments_after_token(child)
        return True

    def _anon_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        self._parts.append("[] ")
        return True

    def _nil_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        self._parts.append("() ")
        return True

    def _undef_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        self._parts.append("UNDEF ")
        return True

    def _iriref_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        child = _safe_get_child(tree, 0, Token, "iriref")
        self._emit_anchored_comments_for_token(child)
        self._parts.append(f"{child.value} ")
        self._emit_inline_comments_after_token(child)
        return True

    def _prefixed_name_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        child = _safe_get_child(tree, 0, Token, "prefixed_name")
        self._emit_anchored_comments_for_token(child)
        self._parts.append(f"{child.value} ")
        self._emit_inline_comments_after_token(child)
        return True

    def _inline_data_one_var_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        # Format as:
        # VALUES ?v {
        #     <v1>
        #     <v2>
        # }
        self._stack.append((tree, TraversalPhase.EXIT, context))

        var_node = next(
            (
                c
                for c in tree.children
                if isinstance(c, Tree) and getattr(c, "data", None) == "var"
            ),
            None,
        )
        values = [
            c
            for c in tree.children
            if isinstance(c, Tree) and getattr(c, "data", None) == "data_block_value"
        ]

        # Closing brace. If we emitted at least one value, the last value will have
        # already ended the line with '\n'. If empty, force a newline after '{'.
        if values:
            self._stack.append(
                (
                    Token("RAW", f"{self._indent_prefix()}}}"),
                    TraversalPhase.ENTER,
                    context,
                )
            )
        else:
            self._stack.append(
                (
                    Token("RAW", f"\n{self._indent_prefix()}}}"),
                    TraversalPhase.ENTER,
                    context,
                )
            )

        # Emit each value on its own line.
        for v in reversed(values):
            # Newline trims trailing space from the value emitter.
            self._stack.append((Token("RAW", "\n"), TraversalPhase.ENTER, context))
            self._stack.append((v, TraversalPhase.ENTER, context))
            self._stack.append(
                (Token("RAW", self._indent_prefix(1)), TraversalPhase.ENTER, context)
            )

        # Opening brace
        self._stack.append((Token("RAW", "{\n"), TraversalPhase.ENTER, context))

        # Variable (e.g. ?g)
        if var_node is not None:
            self._stack.append((var_node, TraversalPhase.ENTER, context))

        return True

    def _inline_data_full_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        """Handles the full form of inline data (VALUES clause).

        This handler manually traverses children to correctly handle the structure:
        VALUES data_block_value_group { ( ... ) }
        It manages the braces and parentheses explicitly via RAW tokens.
        """
        # Normalize any trailing space after VALUES so we can control spacing
        # around the header parentheses deterministically.
        self._trim_trailing_space()

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
                            Token("RAW", f"{self._indent_prefix()}}}"),
                            TraversalPhase.ENTER,
                            context,
                        )
                    )
                elif child.value == "(":
                    # Ensure exactly one space before the opening paren.
                    self._stack.append(
                        (Token("RAW", " ("), TraversalPhase.ENTER, context)
                    )
                elif child.value == ")":
                    # Trim trailing space inside the list, then add ') '.
                    self._stack.append(
                        (Token("RAW", ") "), TraversalPhase.ENTER, context)
                    )
                elif child.value == "()":
                    # NIL header (rare): keep one leading space.
                    self._stack.append(
                        (Token("RAW", " () "), TraversalPhase.ENTER, context)
                    )
                else:
                    self._stack.append((child, TraversalPhase.ENTER, context))
            else:
                self._stack.append((child, TraversalPhase.ENTER, context))
        return True

    def _data_block_value_group_enter(
        self, tree: Tree[Any], context: dict[str, Any]
    ) -> bool:
        # Format rows as:
        #     (<v1> <v2>)
        # Each group is on its own line.
        nil_token = next(
            (
                c
                for c in tree.children
                if isinstance(c, Token) and (c.type == "NIL" or c.value == "()")
            ),
            None,
        )
        if nil_token is not None:
            self._stack.append(
                (
                    Token("RAW", f"{self._indent_prefix(1)}()\n"),
                    TraversalPhase.ENTER,
                    context,
                )
            )
            return True

        # Close paren + newline (will trim trailing space).
        self._stack.append((Token("RAW", ")\n"), TraversalPhase.ENTER, context))

        # Push values inside the row.
        for i in range(len(tree.children) - 1, -1, -1):
            child = tree.children[i]
            if isinstance(child, Token) and child.value in ("(", ")"):
                continue
            self._stack.append((child, TraversalPhase.ENTER, context))

        # Open paren with indentation included (avoid trimming indentation).
        self._stack.append(
            (Token("RAW", f"{self._indent_prefix(1)}("), TraversalPhase.ENTER, context)
        )
        return True

    def _data_block_value_enter(self, tree: Tree[Any], context: dict[str, Any]) -> bool:
        return False
