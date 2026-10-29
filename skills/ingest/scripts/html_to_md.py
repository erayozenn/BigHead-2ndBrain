#!/usr/bin/env python3
"""HTML -> markdown for web captures (ingest skill). Standard library only.

Usage:
  html_to_md.py <in.html> --out <out.md> [--selector SEL]

Keeps the article body: the first element matching --selector, else the first match from
DEFAULT_SELECTORS, else <body>. Selector forms: tag, .class, #id, tag.class, tag#id.
Drops navigation, scripts, buttons, forms, SVG and hidden elements. Maps headings, paragraphs,
lists, links, images, emphasis, code, pre, blockquotes, tables (cell paragraphs -> <br>),
definition lists and details/summary. Writes UTF-8 with LF line endings.

Prints JSON: selector used, words, estimated tokens, and a warning when the body is so short
that the page is probably rendered by JavaScript (then capture another way).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_SELECTORS = [
    "div.devsite-article-body",  # Google developer docs
    "article",
    "main",
    "div.markdown-body",  # GitHub-rendered markdown
    "div#content",
]
SKIP = {
    "script", "style", "noscript", "template", "nav", "aside", "header", "footer", "button",
    "svg", "form", "input", "select", "textarea", "iframe", "canvas", "dialog",
}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
        "track", "wbr"}
BLOCK = {"p", "div", "section", "figure", "figcaption", "ul", "ol", "li", "table", "pre",
         "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "dl", "dt", "dd", "details",
         "summary", "hr", "main", "article"}
# Opening tag X implicitly closes an open element in AUTOCLOSE[X] (HTML optional end tags).
AUTOCLOSE = {
    "p": {"p"}, "li": {"li", "p"}, "dt": {"dt", "dd", "p"}, "dd": {"dt", "dd", "p"},
    "td": {"td", "th", "p"}, "th": {"td", "th", "p"}, "tr": {"tr", "td", "th", "p"},
    "option": {"option"},
}
MIN_WORDS = 100
INDENT = "\x00"  # list indentation survives line normalization, becomes spaces at the end
PRE = "\x01"     # placeholder delimiter for preformatted blocks


class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict[str, str]):
        self.tag = tag
        self.attrs = attrs
        self.children: list[Node | str] = []


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        closes = AUTOCLOSE.get(tag, set()) | ({"p"} if tag in BLOCK else set())
        while len(self.stack) > 1 and self.stack[-1].tag in closes:
            self.stack.pop()
        node = Node(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _matches(node: Node, sel: str) -> bool:
    m = re.fullmatch(r"([a-z0-9]*)(?:([.#])([\w-]+))?", sel.strip().lower())
    if not m or not (m.group(1) or m.group(3)):
        raise ValueError(f"unsupported selector: {sel!r} (use tag, .class, #id, tag.class, tag#id)")
    tag, kind, name = m.groups()
    if tag and node.tag != tag:
        return False
    if kind == ".":
        return name in node.attrs.get("class", "").lower().split()
    if kind == "#":
        return node.attrs.get("id", "").lower() == name
    return True


def find(node: Node, sel: str) -> Node | None:
    if node.tag != "#root" and _matches(node, sel):
        return node
    for child in node.children:
        if isinstance(child, Node):
            hit = find(child, sel)
            if hit:
                return hit
    return None


def _hidden(node: Node) -> bool:
    a = node.attrs
    style = a.get("style", "").replace(" ", "").lower()
    return "hidden" in a or a.get("aria-hidden") == "true" or "display:none" in style


def _normalize(text: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _wrap(inner: str, mark: str) -> str:
    core = inner.strip()
    if not core:
        return inner
    lead = " " if inner[:1].isspace() else ""
    trail = " " if inner[-1:].isspace() else ""
    return f"{lead}{mark}{core}{mark}{trail}"


class Renderer:
    def __init__(self):
        self.pre_blocks: list[str] = []

    def children(self, node: Node, in_cell: bool = False) -> str:
        return "".join(self.render(c, in_cell) for c in node.children)

    def render(self, node: Node | str, in_cell: bool = False) -> str:
        if isinstance(node, str):
            return re.sub(r"\s+", " ", node)
        tag = node.tag
        if tag in SKIP or _hidden(node):
            return ""
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = _normalize(self.children(node)).replace("\n", " ")
            return f"\n\n{'#' * int(tag[1])} {text}\n\n" if text else ""
        if tag in ("strong", "b"):
            return _wrap(self.children(node, in_cell), "**")
        if tag in ("em", "i"):
            return _wrap(self.children(node, in_cell), "*")
        if tag == "code":
            return _wrap(self.children(node, in_cell), "`")
        if tag == "a":
            text = self.children(node, in_cell)
            href = node.attrs.get("href", "")
            if not text.strip():
                return text
            return f"[{text.strip()}]({href})" if href else text
        if tag == "img":
            src = node.attrs.get("src") or node.attrs.get("data-src", "")
            return f"![{node.attrs.get('alt', '')}]({src})" if src else ""
        if tag == "br":
            return "<br>" if in_cell else "\n"
        if tag == "hr":
            return "\n\n---\n\n"
        if tag == "pre":
            self.pre_blocks.append(_text(node).strip("\n"))
            return f"\n\n{PRE}{len(self.pre_blocks) - 1}{PRE}\n\n"
        if tag in ("ul", "ol"):
            return "\n\n" + self.list_block(node) + "\n\n"
        if tag == "table":
            return "\n\n" + self.table(node) + "\n\n"
        if tag == "blockquote":
            body = _normalize(self.children(node))
            return "\n\n" + "\n".join("> " + ln for ln in body.split("\n")) + "\n\n"
        if tag in ("summary", "dt", "figcaption"):
            text = _normalize(self.children(node)).replace("\n", " ")
            mark = "*" if tag == "figcaption" else "**"
            return f"\n\n{mark}{text}{mark}\n\n" if text else ""
        if tag in BLOCK or tag in ("li", "tr", "td", "th"):
            return "\n\n" + self.children(node, in_cell) + "\n\n"
        return self.children(node, in_cell)

    def list_block(self, node: Node) -> str:
        items, n = [], 0
        for child in node.children:
            if not (isinstance(child, Node) and child.tag == "li") or _hidden(child):
                continue
            n += 1
            body = _normalize(self.children(child))
            if not body:
                continue
            marker = f"{n}. " if node.tag == "ol" else "- "
            pad = INDENT * len(marker)
            lines = body.split("\n")
            items.append(marker + lines[0] + "".join(
                "\n" + (pad + ln if ln else "") for ln in lines[1:]))
        return "\n".join(items)

    def table(self, node: Node) -> str:
        rows = []
        for tr in _descendants(node, "tr"):
            cells = [c for c in tr.children if isinstance(c, Node) and c.tag in ("td", "th")]
            row = []
            for cell in cells:
                text = _normalize(self.children(cell, in_cell=True))
                text = re.sub(r"\s*\n+\s*", "<br>", text).replace("|", "\\|")
                row.append(text)
            if any(row):
                rows.append(row)
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
        out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(out)


def _descendants(node: Node, tag: str):
    for child in node.children:
        if isinstance(child, Node):
            if child.tag == tag:
                yield child
            elif child.tag != "table":  # rows of nested tables stay with their own table
                yield from _descendants(child, tag)


def _text(node: Node | str) -> str:
    if isinstance(node, str):
        return node
    if node.tag == "br":
        return "\n"
    return "".join(_text(c) for c in node.children)


def convert(html: str, selector: str | None) -> tuple[str, str]:
    builder = TreeBuilder()
    builder.feed(html)
    builder.close()
    candidates = [selector] if selector else DEFAULT_SELECTORS
    body, used = None, None
    for sel in candidates:
        body = find(builder.root, sel)
        if body:
            used = sel
            break
    if body is None:
        if selector:
            raise LookupError(f"selector {selector!r} matched nothing")
        body, used = find(builder.root, "body") or builder.root, "body"
    renderer = Renderer()
    md = _normalize(renderer.render(body)).replace(INDENT, " ")
    md = re.sub(PRE + r"(\d+)" + PRE,
                lambda m: "```\n" + renderer.pre_blocks[int(m.group(1))] + "\n```", md)
    return md + "\n", used


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("html", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--selector", help="CSS-like selector for the article body")
    args = ap.parse_args()
    try:
        md, used = convert(args.html.read_text(encoding="utf-8", errors="replace"), args.selector)
    except (LookupError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.out.write_text(md, encoding="utf-8", newline="\n")
    words = len(md.split())
    report = {"out": str(args.out), "selector": used, "words": words, "est_tokens": len(md) // 4}
    if words < MIN_WORDS:
        report["warning"] = ("very little text: the page is probably rendered by JavaScript, "
                             "or the selector missed the body; try --selector or another capture")
    print(json.dumps(report))  # ASCII-escaped: Windows consoles may not be UTF-8
    return 0


if __name__ == "__main__":
    sys.exit(main())
