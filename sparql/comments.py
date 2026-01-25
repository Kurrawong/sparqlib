from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from lark import Lark, Token, Tree

_GRAMMAR = files(__package__).joinpath("grammar.lark").read_text(encoding="utf-8")
_COMMENT_LEXER_GRAMMAR = (
    _GRAMMAR.replace("%ignore /[ \\t\\n]/+ | COMMENT", "%ignore /[ \\t\\n]/+")
    + "\ncomment_unit: (COMMENT | unit)*\n"
)
_COMMENT_LEXER = Lark(
    _COMMENT_LEXER_GRAMMAR,
    start="comment_unit",
    propagate_positions=True,
    lexer="basic",
)


@dataclass(frozen=True)
class RawComment:
    value: str
    start_pos: int | None
    end_pos: int | None
    line: int | None
    column: int | None
    inline: bool
    after_open_brace_index: int | None
    after_close_paren_index: int | None


def _pos_start(token: Token) -> int | None:
    # Lark versions differ in which attributes are present.
    return getattr(token, "start_pos", None) or getattr(token, "pos_in_stream", None)


def _pos_end(token: Token) -> int | None:
    return getattr(token, "end_pos", None)


def _end_pos_fallback(token: Token) -> int | None:
    """Best-effort token end position when end_pos isn't available."""
    end = _pos_end(token)
    if end is not None:
        return end
    start = _pos_start(token)
    if start is None:
        return None
    val = getattr(token, "value", "")
    return start + len(val)


def _iter_tokens(tree: Tree[Any]) -> Iterable[Token]:
    stack: list[Any] = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, Token):
            yield node
        elif isinstance(node, Tree) and node.children:
            for child in reversed(node.children):
                if child is not None:
                    stack.append(child)


def _significant_tokens_in_source_order(tree: Tree[Any]) -> list[Token]:
    tokens = [t for t in _iter_tokens(tree) if t.type != "COMMENT"]

    # Sort by stream position if available, otherwise fall back to (line, column)
    # while preserving traversal order as a final tie-breaker.
    indexed = list(enumerate(tokens))

    def key(item: tuple[int, Token]) -> tuple[int, int, int]:
        i, t = item
        start = _pos_start(t)
        if start is not None:
            return (0, start, i)
        line = getattr(t, "line", 0) or 0
        col = getattr(t, "column", 0) or 0
        # Combine line/col into a stable sortable integer-ish tuple.
        return (1, line * 1_000_000 + col, i)

    indexed.sort(key=key)
    return [t for _, t in indexed]


def scan_raw_comments(source: str) -> list[RawComment]:
    """Collect raw '# ...' comments with stream positions via Lark lexing."""
    raw: list[RawComment] = []
    tokens = list(_COMMENT_LEXER.lex(source))

    open_brace_index = 0
    close_paren_index = 0

    for token in tokens:
        if token.type == "LEFT_CURLY_BRACE":
            open_brace_index += 1
        elif token.type == "RIGHT_PARENTHESIS":
            close_paren_index += 1

        if token.type != "COMMENT":
            continue

        start_pos = _pos_start(token)
        end_pos = _end_pos_fallback(token)
        line = getattr(token, "line", None)
        column = getattr(token, "column", None)
        value = token.value

        if start_pos is None:
            line_start_pos = 0
        else:
            line_start_pos = source.rfind("\n", 0, start_pos) + 1
        prefix = source[line_start_pos:start_pos] if start_pos is not None else ""
        inline = prefix.strip(" \t") != ""

        last_non_ws = prefix.rstrip(" \t")[-1:] if inline else ""

        after_open_brace_index = open_brace_index if last_non_ws == "{" else None
        after_close_paren_index = close_paren_index if last_non_ws == ")" else None

        raw.append(
            RawComment(
                value=value,
                start_pos=start_pos,
                end_pos=end_pos,
                line=line,
                column=column,
                inline=inline,
                after_open_brace_index=after_open_brace_index,
                after_close_paren_index=after_close_paren_index,
            )
        )

    return raw


def attach_comments(tree: Tree[Any], raw_comments: list[RawComment]) -> None:
    """Attach comment metadata to a parsed tree for later serialization.

    This does not change the tree structure; it records comments and anchors them
    to the nearest significant token (or EOF) using stream positions.
    """
    tokens = _significant_tokens_in_source_order(tree)
    token_starts: list[int | None] = [_pos_start(t) for t in tokens]
    token_ends: list[int | None] = [_end_pos_fallback(t) for t in tokens]
    token_lines: list[int | None] = [getattr(t, "line", None) for t in tokens]

    comments_by_index: dict[int, list[str]] = {}
    inline_after_token: dict[int, list[str]] = {}
    inline_after_open_brace: dict[int, list[str]] = {}
    inline_after_close_paren: dict[int, list[str]] = {}
    eof_comments: list[str] = []

    for c in raw_comments:
        if c.after_open_brace_index is not None:
            inline_after_open_brace.setdefault(c.after_open_brace_index, []).append(
                c.value
            )
            continue
        if c.after_close_paren_index is not None:
            inline_after_close_paren.setdefault(c.after_close_paren_index, []).append(
                c.value
            )
            continue

        if c.inline:
            # Anchor inline comments to the nearest preceding token (by end_pos).
            c_start = c.start_pos
            if c_start is not None and c.line is not None:
                best: int | None = None
                for i in range(len(tokens) - 1, -1, -1):
                    end = token_ends[i]
                    if token_lines[i] == c.line and end is not None and end <= c_start:
                        best = i
                        break
                if best is not None:
                    inline_after_token.setdefault(best, []).append(c.value)
                    continue
            if c_start is not None:
                # Fallback without line constraint.
                best2: int | None = None
                for i in range(len(tokens) - 1, -1, -1):
                    end = token_ends[i]
                    if end is not None and end <= c_start:
                        best2 = i
                        break
                if best2 is not None:
                    inline_after_token.setdefault(best2, []).append(c.value)
                    continue
            # Fall back to EOF if we can't find a reasonable anchor.
            eof_comments.append(c.value)
            continue

        # Prefer anchoring based on end_pos; if unavailable, fall back to start_pos.
        c_end = c.end_pos if c.end_pos is not None else c.start_pos

        anchor_idx: int | None = None
        if c_end is not None:
            for i, t_start in enumerate(token_starts):
                if t_start is not None and t_start >= c_end:
                    anchor_idx = i
                    break

        if anchor_idx is None:
            # Comment at EOF (or no usable positions).
            eof_comments.append(c.value)
        else:
            comments_by_index.setdefault(anchor_idx, []).append(c.value)

    # Store metadata for the serializer.
    tree.meta.sparql_comments_raw = raw_comments  # type: ignore[attr-defined]
    tree.meta.sparql_comments = {**comments_by_index, "eof": eof_comments}  # type: ignore[attr-defined]
    tree.meta.sparql_comment_token_ids = [id(t) for t in tokens]  # type: ignore[attr-defined]
    tree.meta.sparql_inline_comments_after_token = inline_after_token  # type: ignore[attr-defined]
    tree.meta.sparql_inline_comments_after_open_brace = inline_after_open_brace  # type: ignore[attr-defined]
    tree.meta.sparql_inline_comments_after_close_paren = inline_after_close_paren  # type: ignore[attr-defined]
