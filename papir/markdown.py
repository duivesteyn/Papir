#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Markdown intake: render .md to the HTML Amazon's converter already accepts.
# Stdlib only — papir ships with requests and nothing else.
#
# # bmd 2026

"""Markdown to HTML for the Send to Kindle path.

Amazon has no markdown intake, but it does accept HTML and turns it into
reflowable Kindle text. This module is deliberately small and dependency-free:
a block pass for headings, paragraphs, lists, quotes, fenced code, tables and
rules, then an inline pass for emphasis, code spans, links and images.

Deliberate limits, so nothing silently goes missing:

* images that are not absolute http(s)/data URLs are replaced with their alt
  text — Amazon's converter cannot fetch files from your disk;
* raw HTML in the markdown is passed through untouched, as CommonMark allows;
* tables, task lists and nested lists degrade gracefully but do not try to be
  pixel-accurate on a 6" screen.
"""

import contextlib
import html
import itertools
import re
import shutil
import tempfile
from pathlib import Path

EXTENSIONS = {"md", "markdown", "mdown", "mkd", "mdwn", "mkdn"}

_SERIAL = itertools.count()
_ENTITY = re.compile(r"&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]{1,31});")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*([^`\s]*)[ \t]*$")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*))?$")
_HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_LIST = re.compile(
    r"^(?P<indent> {0,3})(?P<marker>[-*+]|(?P<num>\d{1,9})[.)])(?P<space>[ \t]+)(?P<text>.*)$"
)
_QUOTE = re.compile(r"^ {0,3}>[ \t]?(.*)$")
_HTML_BLOCK = re.compile(r"^ {0,3}<(?:/?[A-Za-z][A-Za-z0-9]*)(?:[ \t>/]|$)|^ {0,3}<!--")
_REFDEF = re.compile(
    r"^ {0,3}\[([^\]]+)\]:[ \t]*<?([^\s>]+)>?"
    r"(?:[ \t]+(?:\"([^\"]*)\"|'([^']*)'|\(([^)]*)\)))?[ \t]*$"
)
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_DELIM_CELL = re.compile(r"^:?-+:?$")
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>~|])")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1", re.S)
_IMAGE = re.compile(
    r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+(?:\"([^\"]*)\"|'([^']*)'|\(([^)]*)\)))?\s*\)"
)
_INLINE_LINK = re.compile(
    r"\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+(?:\"([^\"]*)\"|'([^']*)'|\(([^)]*)\)))?\s*\)"
)
_FULL_REF = re.compile(r"\[([^\]]*)\]\[([^\]]*)\]")
_AUTOLINK = re.compile(r"<((?:https?|mailto):[^<>\s]+)>")
_EMAIL = re.compile(r"<([^<>\s@]+@[^<>\s]+\.[A-Za-z]{2,})>")
_RAW_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_BARE_URL = re.compile(r"(?<![\w\"'=])https?://[^\s<>\x00)\]]+")
_TASK = re.compile(r"^\[([ xX])\][ \t]+")


# -- text helpers ---------------------------------------------------------

def _escape(text):
    """Escape &, < and > but leave valid character entities alone."""
    out, start = [], 0
    for match in _ENTITY.finditer(text):
        out.append(html.escape(text[start:match.start()], quote=False))
        out.append(match.group(0))
        start = match.end()
    out.append(html.escape(text[start:], quote=False))
    return "".join(out)


def _attr(text):
    """A quoted attribute value."""
    return html.escape(text or "", quote=True)


def _emphasis(text):
    """Wrap emphasis markers. Runs after escaping, so generated tags survive."""
    text = re.sub(r"\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*", r"<strong><em>\1</em></strong>", text, flags=re.S)
    text = re.sub(r"(?<![\w])___(?=\S)(.+?)(?<=\S)___(?![\w])",
                  r"<strong><em>\1</em></strong>", text, flags=re.S)
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text, flags=re.S)
    text = re.sub(r"(?<![\w])__(?=\S)(.+?)(?<=\S)__(?![\w])", r"<strong>\1</strong>", text, flags=re.S)
    text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", text, flags=re.S)
    text = re.sub(r"(?<!\*)\*(?=\S)(.+?)(?<=\S)\*(?!\*)", r"<em>\1</em>", text, flags=re.S)
    text = re.sub(r"(?<![\w])_(?=\S)(.+?)(?<=\S)_(?![\w])", r"<em>\1</em>", text, flags=re.S)
    return text


def _restore(text, serial, pieces):
    """Put the protected fragments back, including ones nested in a link label."""
    pattern = re.compile(r"\x00%d:(\d+)\x00" % serial)
    for _ in range(len(pieces) + 2):
        restored = pattern.sub(lambda m: pieces[int(m.group(1))], text)
        if restored == text:
            break
        text = restored
    return text


def _inline(text, refs=None):
    """Render one line of inline markdown to HTML."""
    refs = refs or {}
    pieces = []
    # A link label is rendered by a nested call; its placeholders must not
    # collide with the ones this pass already handed out.
    serial = next(_SERIAL)

    def keep(fragment):
        pieces.append(fragment)
        return "\x00%d:%d\x00" % (serial, len(pieces) - 1)

    # Escaped punctuation must not be re-read as markdown.
    text = _ESCAPE.sub(lambda m: keep(_escape(m.group(1))), text)

    def code(m):
        body = m.group(2).replace("\n", " ")
        if len(body) > 2 and body.startswith(" ") and body.endswith(" ") and body.strip():
            body = body[1:-1]
        return keep("<code>" + _escape(body) + "</code>")

    text = _CODE_SPAN.sub(code, text)

    def image(m):
        alt, src = m.group(1), m.group(2)
        title = m.group(3) or m.group(4) or m.group(5) or ""
        if re.match(r"^(?:https?:|data:|//)", src):
            extra = ' title="%s"' % _attr(title) if title else ""
            return keep('<img src="%s" alt="%s"%s />' % (_attr(src), _attr(alt), extra))
        # A local image cannot travel through Amazon's converter; keep the words.
        label = alt.strip() or Path(src).name or "image"
        return keep("<em>[Image: %s]</em>" % _escape(label))

    text = _IMAGE.sub(image, text)

    def link(m):
        label, href = m.group(1), m.group(2)
        title = m.group(3) or m.group(4) or m.group(5) or ""
        extra = ' title="%s"' % _attr(title) if title else ""
        return keep('<a href="%s"%s>%s</a>' % (_attr(href), extra, _inline(label, refs)))

    text = _INLINE_LINK.sub(link, text)

    def full_ref(m):
        label = (m.group(2) or m.group(1)).strip().lower()
        if label in refs:
            href, title = refs[label]
            extra = ' title="%s"' % _attr(title) if title else ""
            return keep('<a href="%s"%s>%s</a>' % (_attr(href), extra, _inline(m.group(1), refs)))
        return m.group(0)

    text = _FULL_REF.sub(full_ref, text)

    def shortcut_ref(m):
        label = m.group(1).strip().lower()
        if label in refs:
            href, title = refs[label]
            extra = ' title="%s"' % _attr(title) if title else ""
            return keep('<a href="%s"%s>%s</a>' % (_attr(href), extra, _inline(m.group(1), refs)))
        return m.group(0)

    text = re.sub(r"\[([^\]]+)\](?!\()", shortcut_ref, text)

    text = _AUTOLINK.sub(
        lambda m: keep('<a href="%s">%s</a>' % (_attr(m.group(1)), _escape(m.group(1)))), text)
    text = _EMAIL.sub(
        lambda m: keep('<a href="mailto:%s">%s</a>' % (_attr(m.group(1)), _escape(m.group(1)))), text)
    text = _RAW_TAG.sub(lambda m: keep(m.group(0)), text)

    def bare_url(m):
        url = m.group(0)
        trailing = ""
        while url and url[-1] in ".,;:!?)]'":
            trailing = url[-1] + trailing
            url = url[:-1]
        return keep('<a href="%s">%s</a>' % (_attr(url), _escape(url))) + _escape(trailing)

    text = _BARE_URL.sub(bare_url, text)

    # Everything left is literal text.
    text = _escape(text)
    text = _emphasis(text)
    return _restore(text, serial, pieces)


# -- block helpers --------------------------------------------------------

def _strip_hashes(text):
    return re.sub(r"[ \t]+#+[ \t]*$", "", (text or "").strip()).strip()


def _split_row(line):
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.replace("\\|", "|").strip() for cell in _CELL_SPLIT.split(body)]


def _is_table_start(lines, index):
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    head, delim = _split_row(lines[index]), _split_row(lines[index + 1])
    return bool(delim) and len(head) == len(delim) and all(_DELIM_CELL.match(c) for c in delim)


def _starts_block(line):
    return bool(
        _FENCE.match(line)
        or _ATX.match(line)
        or _HR.match(line)
        or _LIST.match(line)
        or _QUOTE.match(line)
        or _HTML_BLOCK.match(line)
        or (line.startswith("    ") and line.strip())
    )


def _take_references(lines):
    """Pull `[label]: url "title"` definitions out, ignoring fenced code."""
    refs, kept, fence = {}, [], None
    for line in lines:
        match = _FENCE.match(line)
        if match:
            fence = None if fence and line.strip().startswith(fence) else (fence or match.group(1))
            kept.append(line)
            continue
        if fence:
            kept.append(line)
            continue
        match = _REFDEF.match(line)
        if match:
            refs[match.group(1).strip().lower()] = (
                match.group(2), match.group(3) or match.group(4) or match.group(5) or "")
            continue
        kept.append(line)
    return kept, refs


def _fenced_code(lines, index, out):
    match = _FENCE.match(lines[index])
    fence, lang = match.group(1), (match.group(2) or "").strip()
    closer = re.compile(r"^ {0,3}" + re.escape(fence[0]) + "{%d,}[ \t]*$" % len(fence))
    body = []
    index += 1
    while index < len(lines):
        if closer.match(lines[index]):
            index += 1
            break
        body.append(lines[index])
        index += 1
    style = ' class="language-%s"' % _attr(lang) if lang else ""
    out.append("<pre><code%s>%s</code></pre>" % (style, html.escape("\n".join(body), quote=False)))
    return index


def _indented_code(lines, index, out):
    body = []
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            body.append("")
            index += 1
            continue
        if not line.startswith("    "):
            break
        body.append(line[4:])
        index += 1
    while body and not body[-1].strip():
        body.pop()
    out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(body), quote=False))
    return index


def _raw_html(lines, index, out):
    body = []
    while index < len(lines) and lines[index].strip():
        body.append(lines[index])
        index += 1
    out.append("\n".join(body))
    return index


def _quote(lines, index, out):
    body = []
    while index < len(lines):
        match = _QUOTE.match(lines[index])
        if match:
            body.append(match.group(1))
            index += 1
            continue
        line = lines[index]
        # Lazy continuation: a wrapped paragraph line without its `>`.
        if line.strip() and body and body[-1].strip() and not _starts_block(line) \
                and not _is_table_start(lines, index):
            body.append(line.strip())
            index += 1
            continue
        break
    inner = _blocks(body, {})
    out.append("<blockquote>\n%s\n</blockquote>" % "\n".join(inner))
    return index


def _table(lines, index, out):
    head = _split_row(lines[index])
    index += 2  # skip the header row and the delimiter row
    rows = []
    while index < len(lines):
        line = lines[index]
        if not line.strip() or "|" not in line or _starts_block(line):
            break
        rows.append(_split_row(line))
        index += 1
    out.append("<table>")
    out.append("<thead><tr>%s</tr></thead>" % "".join(
        "<th>%s</th>" % _inline(cell) for cell in head))
    if rows:
        out.append("<tbody>")
        for row in rows:
            width = len(head)
            row = (row + [""] * width)[:width]
            out.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _inline(cell) for cell in row))
        out.append("</tbody>")
    out.append("</table>")
    return index


def _list(lines, index, out):
    first = _LIST.match(lines[index])
    ordered = first.group("num") is not None
    indent = len(first.group("indent"))
    cut = indent + 2
    items, body, pending_blank = [], [], False

    def flush():
        nonlocal body, pending_blank
        items.append(body)
        body, pending_blank = [], False

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            if body:
                pending_blank = True
            index += 1
            continue
        match = _LIST.match(line)
        lead = len(line) - len(line.lstrip(" "))
        if match and len(match.group("indent")) == indent and \
                (match.group("num") is not None) == ordered:
            if body or items:
                flush()
            body = [match.group("text")]
            index += 1
            continue
        if lead >= cut:
            if pending_blank:
                body.append("")
                pending_blank = False
            body.append(line[cut:])
            index += 1
            continue
        if lead > indent:
            if pending_blank:
                body.append("")
                pending_blank = False
            body.append(line.lstrip(" "))
            index += 1
            continue
        # A blank line ends the item unless the next line is indented under it,
        # so only an unbroken wrapped line counts as a lazy continuation.
        if body and not pending_blank and not _starts_block(line) \
                and not _is_table_start(lines, index):
            body.append(line.strip())
            index += 1
            continue
        break

    if body:
        flush()

    tag = "ol" if ordered else "ul"
    out.append("<%s>" % tag)
    for lines_in_item in items:
        if lines_in_item:
            lines_in_item[0] = _TASK.sub(
                lambda m: "\u2611 " if m.group(1).lower() == "x" else "\u2610 ", lines_in_item[0])
        inner = _blocks(lines_in_item, {})
        if len(inner) == 1 and inner[0].startswith("<p>") and inner[0].endswith("</p>"):
            out.append("<li>%s</li>" % inner[0][3:-4])
        elif inner:
            out.append("<li>\n%s\n</li>" % "\n".join(inner))
        else:
            out.append("<li></li>")
    out.append("</%s>" % tag)
    return index


def _hard_break(line):
    """Split a line into its text and whether markdown asked for a line break."""
    text = line.strip()
    hard = line.endswith("  ") or text.endswith("\\")
    if text.endswith("\\"):
        text = text[:-1].rstrip()
    return text, hard


def _paragraph(lines, index, out, refs):
    parts, index_count = [], len(lines)
    while index < index_count:
        line = lines[index]
        if not line.strip():
            break
        if parts and _starts_block(line):
            break
        if not parts:
            text, hard = _hard_break(line)
            parts.append((text, hard))
            index += 1
            if index < index_count:
                setext = _SETEXT.match(lines[index])
                if setext:
                    level = 1 if setext.group(1)[0] == "=" else 2
                    out.append("<h%d>%s</h%d>" % (
                        level, _inline(parts[0][0], refs), level))
                    return index + 1
            continue
        text, hard = _hard_break(line)
        parts.append((text, hard))
        index += 1

    rendered = []
    for position, (text, hard) in enumerate(parts):
        piece = _inline(text, refs)
        if hard and position < len(parts) - 1:
            piece += "<br />"
        rendered.append(piece)
    out.append("<p>%s</p>" % " ".join(rendered))
    return index


def _blocks(lines, refs):
    out, index = [], 0
    total = len(lines)
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if _FENCE.match(line):
            index = _fenced_code(lines, index, out)
        elif _ATX.match(line):
            match = _ATX.match(line)
            level = len(match.group(1))
            out.append("<h%d>%s</h%d>" % (level, _inline(_strip_hashes(match.group(2)), refs), level))
            index += 1
        elif _HR.match(line):
            out.append("<hr />")
            index += 1
        elif _LIST.match(line):
            index = _list(lines, index, out)
        elif _QUOTE.match(line):
            index = _quote(lines, index, out)
        elif _is_table_start(lines, index):
            index = _table(lines, index, out)
        elif _HTML_BLOCK.match(line):
            index = _raw_html(lines, index, out)
        elif line.startswith("    "):
            index = _indented_code(lines, index, out)
        else:
            index = _paragraph(lines, index, out, refs)
    return out


# -- public API -----------------------------------------------------------

def looks_markdown(path):
    """True for the markdown extensions we convert."""
    return Path(str(path)).suffix.lower().lstrip(".") in EXTENSIONS


def to_html(text):
    """Render a markdown fragment (no document wrapper)."""
    normalised = text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
    lines, refs = _take_references(normalised.split("\n"))
    return "\n".join(_blocks(lines, refs)).strip()


def document(body, title=""):
    """Wrap a fragment in the minimal HTML shell Amazon's converter likes."""
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        "<title>%s</title></head><body>\n%s\n</body></html>\n" % (_attr(title), body)
    )


def render(path, title=None):
    """Read a markdown file and return a complete HTML document."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = source.read_text(encoding="utf-8", errors="replace")
    return document(to_html(text), title or source.stem)


@contextlib.contextmanager
def converted(source, title=None):
    """Yield a temporary HTML file for a markdown source, then clean up.

    The temporary file keeps the source's stem so Papir derives the same
    title it would have used for the original document.
    """
    folder = Path(tempfile.mkdtemp(prefix="papir-md-"))
    try:
        stem = Path(str(source)).stem or "document"
        target = folder / (stem + ".html")
        target.write_text(render(source, title=title), encoding="utf-8")
        yield target
    finally:
        shutil.rmtree(folder, ignore_errors=True)
