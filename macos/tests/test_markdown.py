#!/usr/bin/env python3
"""Offline tests for markdown intake (papir/markdown.py and the send hook)."""

import os
import pathlib
import tempfile
import unittest
from unittest import mock

from papir import markdown
from papir.papir import UnsupportedType, _format_for, papirSend


class RenderTests(unittest.TestCase):
    # -- block structure --------------------------------------------------
    def test_headings(self):
        self.assertEqual(markdown.to_html("# One"), "<h1>One</h1>")
        self.assertEqual(markdown.to_html("### Three ###"), "<h3>Three</h3>")
        self.assertEqual(markdown.to_html("Title\n====="), "<h1>Title</h1>")
        self.assertEqual(markdown.to_html("Sub\n---"), "<h2>Sub</h2>")
        # `#hashtag` is text, not a heading
        self.assertEqual(markdown.to_html("#nope"), "<p>#nope</p>")

    def test_paragraphs_and_hard_breaks(self):
        self.assertEqual(markdown.to_html("one\n\ntwo"), "<p>one</p>\n<p>two</p>")
        self.assertEqual(markdown.to_html("one  \ntwo"), "<p>one<br /> two</p>")
        self.assertEqual(markdown.to_html("one\\\ntwo"), "<p>one<br /> two</p>")

    def test_rule(self):
        self.assertEqual(markdown.to_html("---"), "<hr />")
        self.assertEqual(markdown.to_html("* * *"), "<hr />")

    def test_fenced_code_is_literal(self):
        html = markdown.to_html("```python\nif a < b: print('&')\n```")
        self.assertIn('<pre><code class="language-python">', html)
        self.assertIn("if a &lt; b: print(&#x27;&amp;&#x27;)", html.replace("'", "&#x27;"))
        self.assertNotIn("<p>", html)

    def test_fence_keeps_reference_looking_lines(self):
        html = markdown.to_html("```\n[x]: https://nope.test\n```")
        self.assertIn("[x]: https://nope.test", html)

    def test_indented_code(self):
        self.assertEqual(markdown.to_html("    a < b\n    c"),
                         "<pre><code>a &lt; b\nc</code></pre>")

    def test_quote(self):
        html = markdown.to_html("> quoted **bold**\n\n> second")
        self.assertEqual(html.count("<blockquote>"), 2)
        self.assertIn("<strong>bold</strong>", html)

    def test_lists(self):
        html = markdown.to_html("- a\n- b")
        self.assertEqual(html, "<ul>\n<li>a</li>\n<li>b</li>\n</ul>")
        html = markdown.to_html("1. one\n2. two")
        self.assertIn("<ol>", html)
        self.assertIn("<li>one</li>", html)

    def test_nested_list_stays_nested(self):
        html = markdown.to_html("- a\n  - b\n  - c\n- d")
        self.assertEqual(html.count("<ul>"), 2)
        self.assertLess(html.index("<li>b</li>"), html.index("<li>d</li>"))

    def test_task_list_glyphs(self):
        html = markdown.to_html("- [ ] todo\n- [x] done")
        self.assertIn("\u2610 todo", html)
        self.assertIn("\u2611 done", html)

    def test_table_after_a_list_is_its_own_block(self):
        html = markdown.to_html("- item\n\n| A | B |\n| --- | --- |\n| 1 | 2 |")
        self.assertTrue(html.startswith("<ul>\n<li>item</li>\n</ul>\n<table>"), html)

    def test_table(self):
        html = markdown.to_html("| A | B |\n| --- | --- |\n| 1 | 2 |")
        self.assertIn("<th>A</th><th>B</th>", html)
        self.assertIn("<td>1</td><td>2</td>", html)

    def test_ragged_table_rows_pad_to_header_width(self):
        html = markdown.to_html("| A | B |\n| --- | --- |\n| 1 |\n| 1 | 2 | 3 |")
        self.assertEqual(html.count("<td>"), 4)

    # -- inline -----------------------------------------------------------
    def test_emphasis(self):
        self.assertEqual(markdown.to_html("*a*"), "<p><em>a</em></p>")
        self.assertEqual(markdown.to_html("**a**"), "<p><strong>a</strong></p>")
        self.assertEqual(markdown.to_html("***a***"), "<p><strong><em>a</em></strong></p>")
        self.assertEqual(markdown.to_html("~~gone~~"), "<p><del>gone</del></p>")
        self.assertEqual(markdown.to_html("_a_ and __b__"), "<p><em>a</em> and <strong>b</strong></p>")
        # intraword underscores are file names, not emphasis
        self.assertEqual(markdown.to_html("snake_case_name"), "<p>snake_case_name</p>")

    def test_code_span(self):
        self.assertEqual(markdown.to_html("`a < b`"), "<p><code>a &lt; b</code></p>")

    def test_escapes_are_literal(self):
        self.assertEqual(markdown.to_html(r"\*not\*"), "<p>*not*</p>")

    def test_links(self):
        html = markdown.to_html("[site](https://x.test 'T')")
        self.assertIn('<a href="https://x.test" title="T">site</a>', html)
        self.assertIn('<a href="https://x.test">https://x.test</a>',
                      markdown.to_html("<https://x.test>"))
        self.assertIn('href="mailto:me@x.test"', markdown.to_html("<me@x.test>"))
        self.assertIn('<a href="https://x.test">https://x.test</a>',
                      markdown.to_html("see (https://x.test)"))

    def test_reference_links(self):
        html = markdown.to_html("a [ref] b\n\n[ref]: https://x.test 'T'")
        self.assertIn('<a href="https://x.test" title="T">ref</a>', html)
        self.assertNotIn("[ref]:", html)

    def test_unknown_reference_stays_text(self):
        self.assertEqual(markdown.to_html("[missing]"), "<p>[missing]</p>")

    def test_images(self):
        absolute = markdown.to_html("![alt](https://x.test/a.png)")
        self.assertIn('<img src="https://x.test/a.png" alt="alt" />', absolute)
        # a local image cannot travel through the converter: keep the words
        local = markdown.to_html("![diagram](img/diagram.png)")
        self.assertIn("<em>[Image: diagram]</em>", local)
        unnamed = markdown.to_html("![](img/diagram.png)")
        self.assertIn("[Image: diagram.png]", unnamed)

    def test_code_inside_a_link_label(self):
        self.assertEqual(markdown.to_html("[the `code` link](https://x.test)"),
                         '<p><a href="https://x.test">the <code>code</code> link</a></p>')

    def test_image_inside_a_link(self):
        html = markdown.to_html("[![alt](https://x.test/a.png)](https://x.test)")
        self.assertIn('<a href="https://x.test"><img src="https://x.test/a.png" alt="alt" /></a>', html)

    def test_no_placeholders_leak_into_output(self):
        for text in ("`a` [b](c)", "![x](img/p.png)", "*a* `b` [c](https://d.test)"):
            self.assertNotIn("\x00", markdown.to_html(text))

    def test_html_is_escaped_but_tags_pass_through(self):
        self.assertEqual(markdown.to_html("a < b & c"), "<p>a &lt; b &amp; c</p>")
        self.assertEqual(markdown.to_html("AT&amp;T"), "<p>AT&amp;T</p>")
        self.assertEqual(markdown.to_html("x <span>y</span>"), "<p>x <span>y</span></p>")

    def test_raw_html_block(self):
        html = markdown.to_html("<div>\n<b>hi</b>\n</div>\n\nafter")
        self.assertIn("<div>\n<b>hi</b>\n</div>", html)
        self.assertIn("<p>after</p>", html)

    # -- document ---------------------------------------------------------
    def test_document_wrapper(self):
        html = markdown.document("<p>x</p>", 'Notes & "quotes"')
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn("<title>Notes &amp; &quot;quotes&quot;</title>", html)
        self.assertIn("<p>x</p>", html)

    def test_empty_input(self):
        self.assertEqual(markdown.to_html(""), "")

    def test_crlf_and_tabs(self):
        html = markdown.to_html("# Hi\r\n\r\n- a\r\n- b")
        self.assertEqual(html, "<h1>Hi</h1>\n<ul>\n<li>a</li>\n<li>b</li>\n</ul>")


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = pathlib.Path(self.tmp.name)

    def test_looks_markdown(self):
        for name in ("a.md", "a.MD", "a.markdown", "a.mkd"):
            self.assertTrue(markdown.looks_markdown(name), name)
        for name in ("a.pdf", "a.txt", "a.mdx", "md"):
            self.assertFalse(markdown.looks_markdown(name), name)

    def test_render_uses_stem_as_title(self):
        source = self.folder / "notes.md"
        source.write_text("# Heading\n\nbody", encoding="utf-8")
        self.assertIn("<title>notes</title>", markdown.render(source))

    def test_render_survives_bom_and_bad_bytes(self):
        source = self.folder / "bom.md"
        source.write_bytes("\ufeff# Hi".encode("utf-8"))
        self.assertIn("<h1>Hi</h1>", markdown.render(source))
        bad = self.folder / "bad.md"
        bad.write_bytes(b"# Hi \xff\xfe")
        self.assertIn("<h1>Hi", markdown.render(bad))

    def test_converted_keeps_stem_and_cleans_up(self):
        source = self.folder / "report.md"
        source.write_text("# Report", encoding="utf-8")
        with markdown.converted(source, title="Report") as prepared:
            self.assertEqual(prepared.name, "report.html")
            self.assertIn("<h1>Report</h1>", prepared.read_text(encoding="utf-8"))
            location = prepared
        self.assertFalse(location.exists())
        self.assertFalse(location.parent.exists())
        self.assertTrue(source.exists(), "the original markdown must be left alone")


class FormatTests(unittest.TestCase):
    def test_format_map(self):
        self.assertEqual(_format_for("a.md"), "MD")
        self.assertEqual(_format_for("a.MDOWN"), "MD")
        self.assertEqual(_format_for("a.pdf"), "PDF")

    def test_unknown_extension_raises_unsupported(self):
        with self.assertRaises(UnsupportedType):
            _format_for("a.zip")
        # still a ValueError for anyone catching the broad type
        with self.assertRaises(ValueError):
            _format_for("a.zip")

    def test_explicit_format_override_wins(self):
        self.assertEqual(_format_for("a.md", "HTML"), "HTML")


class SendHookTests(unittest.TestCase):
    """papirSend must upload HTML, keep the title, and clean up the temp file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "PAPIR_CLIENT", None)
        self.client = pathlib.Path(self.tmp.name) / "client.json"
        self.client.write_text(
            '{"version": 1, "device_info": {"device_serial_number": "ABC", "device_name": "t"}}',
            encoding="utf-8")
        os.environ["PAPIR_CLIENT"] = str(self.client)
        self.source = pathlib.Path(self.tmp.name) / "Reading Notes.md"
        self.source.write_text("# Bookmarks\n\n- one\n- two", encoding="utf-8")

    def send(self, **kwargs):
        seen = {}

        def upload(url, size, handle, on_progress=None):
            seen["payload"] = handle.read()
            seen["size"] = size

        def deliver(info, token, targets, author, title, fmt, archive=True, force_convert=False):
            seen["fmt"] = fmt
            seen["title"] = title
            return "SKU-1"

        with mock.patch("papir.api.get_upload_url", return_value=("https://up", "tok")), \
                mock.patch("papir.api.upload_file", side_effect=upload), \
                mock.patch("papir.api.send_to_kindle", side_effect=deliver):
            seen["sku"] = papirSend(str(self.source), target="library", **kwargs)
        return seen

    def test_markdown_is_converted_to_html(self):
        seen = self.send(author="bmd")
        self.assertEqual(seen["sku"], "SKU-1")
        self.assertEqual(seen["fmt"], "HTML")
        self.assertEqual(seen["title"], "Reading Notes")
        self.assertEqual(seen["size"], len(seen["payload"]))
        body = seen["payload"].decode()
        self.assertIn("<h1>Bookmarks</h1>", body)
        self.assertIn("<li>one</li>", body)
        self.assertNotIn("Reading Notes.md", body)

    def test_explicit_title_and_author_win(self):
        seen = self.send(title="Chosen Title", author="deCapital")
        self.assertEqual(seen["title"], "Chosen Title")

    def test_temp_html_is_removed_after_send(self):
        before = set(pathlib.Path(tempfile.gettempdir()).glob("papir-md-*"))
        self.send()
        after = set(pathlib.Path(tempfile.gettempdir()).glob("papir-md-*"))
        self.assertEqual(before, after, "conversion left a temp folder behind")

    def test_other_formats_are_untouched(self):
        pdf = pathlib.Path(self.tmp.name) / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        self.source = pdf
        seen = self.send()
        self.assertEqual(seen["fmt"], "PDF")
        self.assertEqual(seen["title"], "report")
        self.assertEqual(seen["payload"], b"%PDF-1.4 fake")

    def test_empty_markdown_is_rejected_before_conversion(self):
        empty = pathlib.Path(self.tmp.name) / "empty.md"
        empty.write_text("", encoding="utf-8")
        self.source = empty
        with self.assertRaises(ValueError):
            self.send()


if __name__ == "__main__":
    unittest.main()
