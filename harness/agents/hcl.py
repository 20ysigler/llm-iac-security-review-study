"""
Minimal HCL top-level block splitter, used by the chunked orchestration pattern.

This is deliberately not a full HCL parser. It needs to do exactly one thing
reliably: divide a .tf file into top-level blocks without ever splitting one in
half, so that a chunk handed to a model is always syntactically whole.

Two things in the TerraGoat corpus break naive brace counting, and both are
handled here:

  1. Heredocs. `user_data` in ec2.tf embeds a shell script containing unbalanced
     braces and lines that begin at column 0. Brace counting inside a heredoc
     would desynchronise the parser for the rest of the file.
  2. Braces inside quoted strings and after `#` / `//` comments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEREDOC_START = re.compile(r"<<-?\s*([A-Za-z_][A-Za-z0-9_]*)")
_BLOCK_HEAD = re.compile(r'^\s*([a-z][a-z0-9_]*)\s*(.*?)\{\s*$')
_LABEL = re.compile(r'"([^"]*)"')


@dataclass
class Block:
    kind: str            # resource | data | variable | output | provider | locals | ...
    labels: list[str]    # e.g. ["aws_s3_bucket", "financials"]
    text: str            # the block's source, verbatim
    start_line: int

    @property
    def address(self) -> str:
        """Terraform address for resources; a readable label otherwise."""
        if self.kind == "resource" and len(self.labels) >= 2:
            return f"{self.labels[0]}.{self.labels[1]}"
        if self.kind == "data" and len(self.labels) >= 2:
            return f"data.{self.labels[0]}.{self.labels[1]}"
        if self.labels:
            return f"{self.kind}.{self.labels[0]}"
        return self.kind


def _strip_for_counting(line: str) -> str:
    """Remove quoted strings and trailing comments so braces can be counted."""
    out, i, in_str, esc = [], 0, False, False
    while i < len(line):
        ch = line[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "#":
                break
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            else:
                out.append(ch)
        i += 1
    return "".join(out)


def split_blocks(source: str) -> list[Block]:
    """
    Split a .tf file into top-level blocks, in file order.

    Guaranteed lossless: "".join(b.text for b in split_blocks(src)) == src,
    provided the file contains at least one block. Inter-block whitespace and
    comments are attached to the preceding block (or to the following one, for
    material before the first block), so no character is dropped and chunking
    can never silently lose a line of configuration.
    """
    lines = source.splitlines(keepends=True)
    blocks: list[Block] = []
    pending: list[str] = []      # material between blocks, not yet assigned
    cur: list[str] = []          # the block currently being accumulated
    depth = 0
    heredoc: str | None = None
    in_block = False
    kind, labels, start = "", [], 0

    def close() -> None:
        nonlocal cur, in_block, depth, kind, labels
        blocks.append(Block(kind=kind, labels=labels,
                            text="".join(cur), start_line=start))
        cur, in_block, depth, kind, labels = [], False, 0, "", []

    for idx, line in enumerate(lines, start=1):
        if in_block:
            cur.append(line)
            if heredoc is not None:
                if line.strip() == heredoc:
                    heredoc = None
                continue
            hd = _HEREDOC_START.search(line)
            if hd:
                heredoc = hd.group(1)
                continue
            counted = _strip_for_counting(line)
            depth += counted.count("{") - counted.count("}")
            if depth <= 0:
                close()
            continue

        m = _BLOCK_HEAD.match(line)
        if not m:
            pending.append(line)
            continue

        # A new top-level block starts here.
        if pending and blocks:
            blocks[-1].text += "".join(pending)
            pending = []
        kind = m.group(1)
        labels = _LABEL.findall(m.group(2))
        start = idx
        cur = pending + [line]
        pending = []
        in_block = True
        depth = 0
        hd = _HEREDOC_START.search(line)
        if hd:
            heredoc = hd.group(1)
        else:
            counted = _strip_for_counting(line)
            depth += counted.count("{") - counted.count("}")
            if depth <= 0:
                close()

    if pending:
        if blocks:
            blocks[-1].text += "".join(pending)
        elif cur:
            cur.extend(pending)
    if in_block and cur:      # unterminated block at EOF
        close()
    return blocks


def manifest(blocks: list[Block]) -> str:
    """Human-readable inventory of the whole file, injected into every chunk."""
    lines = []
    for b in blocks:
        if b.kind in ("resource", "data"):
            lines.append(f"  {b.address}")
    for b in blocks:
        if b.kind not in ("resource", "data"):
            lines.append(f"  {b.address}")
    return "\n".join(lines)


def chunk_blocks(blocks: list[Block], budget: int) -> list[str]:
    """
    Group consecutive whole blocks into chunks of at most `budget` characters.

    A single block larger than the budget becomes its own chunk rather than
    being split, since a truncated resource is not reviewable.
    """
    chunks: list[str] = []
    cur: list[str] = []
    size = 0
    for b in blocks:
        n = len(b.text)
        if cur and size + n > budget:
            chunks.append("".join(cur))
            cur, size = [], 0
        cur.append(b.text)
        size += n
    if cur:
        chunks.append("".join(cur))
    return chunks
