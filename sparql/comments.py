from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from lark import Token, Tree


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


def _iter_tokens(tree: Tree) -> Iterable[Token]:
    stack: list[Any] = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, Token):
            yield node
        elif isinstance(node, Tree) and node.children:
            for child in reversed(node.children):
                if child is not None:
                    stack.append(child)


def _significant_tokens_in_source_order(tree: Tree) -> list[Token]:
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
    """Collect raw '# ...' comments with stream positions (single pass).

    This scanner intentionally ignores '#' that occur within:
    - IRIREFs (`<...>`)
    - quoted string literals (single/double and long forms)
    - escaped sequences like '\\#'
    """
    raw: list[RawComment] = []
    n = len(source)
    i = 0
    line = 1
    col = 1

    def advance(ch: str) -> None:
        nonlocal line, col
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1

    in_iriref = False
    str_mode: str | None = None  # "s", "d", "ls", "ld"
    open_brace_index = 0
    last_open_brace_index = 0
    close_paren_index = 0
    last_close_paren_index = 0
    last_line_start_pos = 0

    while i < n:
        ch = source[i]

        # Handle "escaped comment marker" conservatively
        if ch == "\\" and i + 1 < n:
            # Skip the escaped char as a unit.
            advance(ch)
            i += 1
            advance(source[i])
            i += 1
            continue

        if in_iriref:
            advance(ch)
            i += 1
            if ch == ">":
                in_iriref = False
            continue

        if str_mode is not None:
            # Long strings end on triple quotes.
            if str_mode == "ls" and source.startswith("'''", i):
                for _ in range(3):
                    advance("'")
                i += 3
                str_mode = None
                continue
            if str_mode == "ld" and source.startswith('"""', i):
                for _ in range(3):
                    advance('"')
                i += 3
                str_mode = None
                continue

            # Short strings end on a matching quote.
            if str_mode == "s" and ch == "'":
                advance(ch)
                i += 1
                str_mode = None
                continue
            if str_mode == "d" and ch == '"':
                advance(ch)
                i += 1
                str_mode = None
                continue

            advance(ch)
            i += 1
            continue

        # Not inside IRI or string
        if ch == "<":
            in_iriref = True
            advance(ch)
            i += 1
            continue

        if source.startswith("'''", i):
            str_mode = "ls"
            for _ in range(3):
                advance("'")
            i += 3
            continue
        if source.startswith('"""', i):
            str_mode = "ld"
            for _ in range(3):
                advance('"')
            i += 3
            continue
        if ch == "'":
            str_mode = "s"
            advance(ch)
            i += 1
            continue
        if ch == '"':
            str_mode = "d"
            advance(ch)
            i += 1
            continue

        if ch == "\n":
            last_line_start_pos = i + 1
            advance(ch)
            i += 1
            continue

        if ch == "{":
            open_brace_index += 1
            last_open_brace_index = open_brace_index
            advance(ch)
            i += 1
            continue

        if ch == ")":
            close_paren_index += 1
            last_close_paren_index = close_paren_index
            advance(ch)
            i += 1
            continue

        if ch == "}":
            advance(ch)
            i += 1
            continue

        if ch == "#":
            start_pos = i
            start_line = line
            start_col = col

            # Consume until newline or EOF.
            j = i
            while j < n and source[j] != "\n":
                j += 1
            value = source[i:j]

            # Determine inline-ness based on whether there is non-whitespace before '#'
            # on the same line (ignoring tabs/spaces).
            prefix = source[last_line_start_pos:start_pos]
            inline = prefix.strip(" \t") != ""

            # Special-case: comment immediately after '{' (ignoring whitespace),
            # e.g. "WHERE { # comment"
            after_open_brace_index: int | None = None
            if inline:
                k = start_pos - 1
                while k >= last_line_start_pos and source[k] in (" ", "\t"):
                    k -= 1
                if k >= last_line_start_pos and source[k] == "{":
                    after_open_brace_index = last_open_brace_index or None
            after_close_paren_index: int | None = None
            if inline:
                k = start_pos - 1
                while k >= last_line_start_pos and source[k] in (" ", "\t"):
                    k -= 1
                if k >= last_line_start_pos and source[k] == ")":
                    after_close_paren_index = last_close_paren_index or None

            raw.append(
                RawComment(
                    value=value,
                    start_pos=start_pos,
                    end_pos=j,
                    line=start_line,
                    column=start_col,
                    inline=inline,
                    after_open_brace_index=after_open_brace_index,
                    after_close_paren_index=after_close_paren_index,
                )
            )

            # Advance over the comment text (but not the newline).
            while i < j:
                advance(source[i])
                i += 1
            continue

        advance(ch)
        i += 1

    return raw


def attach_comments(tree: Tree, raw_comments: list[RawComment]) -> None:
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
            inline_after_open_brace.setdefault(c.after_open_brace_index, []).append(c.value)
            continue
        if c.after_close_paren_index is not None:
            inline_after_close_paren.setdefault(c.after_close_paren_index, []).append(c.value)
            continue

        if c.inline:
            # Anchor inline comments to the nearest preceding token (by end_pos).
            c_start = c.start_pos
            if c_start is not None and c.line is not None:
                best: int | None = None
                for i in range(len(tokens) - 1, -1, -1):
                    end = token_ends[i]
                    if (
                        token_lines[i] == c.line
                        and end is not None
                        and end <= c_start
                    ):
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

