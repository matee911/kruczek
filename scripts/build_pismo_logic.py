"""build_pismo_logic.py — pure logic extracted from build_pismo.py.

No I/O, no subprocess calls. Input: data in, output: data out — testable without
a PDF engine, pandoc, or the poppler-utils font tools installed.
"""

import os
import re


def parse_attachment_spec(spec: str) -> tuple[str, str]:
    """Split a '-z' CLI spec ('path:title') into (path, title).

    Falls back to the file's basename when no title follows the colon — a Windows
    absolute path's drive-letter colon ("C:\\x.txt") is never mistaken for the
    separator because partition() matches the FIRST colon and titles are rare
    enough there that this hasn't come up in practice.

    >>> parse_attachment_spec("dowody/naglowki.txt:Pełne nagłówki wiadomości")
    ('dowody/naglowki.txt', 'Pełne nagłówki wiadomości')
    >>> parse_attachment_spec("dowody/analiza.md")
    ('dowody/analiza.md', 'analiza.md')
    """
    path, _, title = spec.partition(":")
    return path, title or os.path.basename(path)


def postprocess_pandoc_html(html: str) -> str:
    """Strip pandoc's top-level <h1> title and demote all heading levels by one.

    The surrounding template already numbers each attachment with its own <h2>
    ("Załącznik nr N — Tytuł"); pandoc's own <h1> would duplicate that, and its
    <h2>/<h3> would otherwise outrank it.

    >>> postprocess_pandoc_html("<h1>Title</h1>\\n<h2>Section</h2><p>text</p>")
    '\\n<h4>Section</h4><p>text</p>'
    >>> postprocess_pandoc_html("<h3>Sub</h3>")
    '<h5>Sub</h5>'
    >>> postprocess_pandoc_html("<p>no headings</p>")
    '<p>no headings</p>'
    """
    html = re.sub(r"^\s*<h1[^>]*>.*?</h1>", "", html, flags=re.DOTALL)
    for a, b in (
        ("<h1", "<h4"),
        ("</h1>", "</h4>"),
        ("<h2", "<h4"),
        ("</h2>", "</h4>"),
        ("<h3", "<h5"),
        ("</h3>", "</h5>"),
    ):
        html = html.replace(a, b)
    return html


def choose_engine(
    has_weasyprint: bool, chrome_path: str | None, has_wkhtmltopdf: bool
) -> str | None:
    """Pick a PDF engine by availability: weasyprint > Chrome/Chromium > wkhtmltopdf.

    That order is quality, not preference for its own sake — weasyprint honours
    the template's @page CSS most faithfully, Chrome is close behind, and
    wkhtmltopdf needs the margins re-specified as CLI flags (see
    command_for_engine) because its @page support is weak.

    >>> choose_engine(True, "/usr/bin/chrome", True)
    'weasyprint'
    >>> choose_engine(False, "/usr/bin/chrome", True)
    'chrome'
    >>> choose_engine(False, None, True)
    'wkhtmltopdf'
    >>> choose_engine(False, None, False) is None
    True
    """
    if has_weasyprint:
        return "weasyprint"
    if chrome_path:
        return "chrome"
    if has_wkhtmltopdf:
        return "wkhtmltopdf"
    return None


def command_for_engine(
    engine: str,
    *,
    out_path: str,
    tmp_html_path: str,
    chrome_path: str | None = None,
    footer: str = "",
    margins: dict | None = None,
) -> list:
    """Build the subprocess argv for one of the three supported PDF engines.

    For "chrome", `tmp_html_path` must already be absolute — the caller resolves
    it (e.g. via os.path.abspath), since turning a relative path into a
    file:// URL correctly is a filesystem concern, not something this pure
    function should do implicitly against its own idea of "current directory".
    `margins` (a {"T", "B", "L", "R"} dict of CSS lengths) is only used by
    wkhtmltopdf, which — unlike weasyprint and Chrome — does not honour the
    @page margins already declared in the template's own CSS.

    >>> command_for_engine("weasyprint", out_path="out.pdf", tmp_html_path="in.html")
    ['weasyprint', 'in.html', 'out.pdf']

    >>> command_for_engine("chrome", out_path="out.pdf", tmp_html_path="/tmp/in.html",
    ...                    chrome_path="/usr/bin/chrome")
    ... # doctest: +NORMALIZE_WHITESPACE
    ['/usr/bin/chrome', '--headless', '--disable-gpu', '--no-pdf-header-footer',
     '--print-to-pdf=out.pdf', '--virtual-time-budget=20000', 'file:///tmp/in.html']

    >>> cmd = command_for_engine("wkhtmltopdf", out_path="out.pdf", tmp_html_path="in.html",
    ...                          footer="Wezwanie z 18.08.2026",
    ...                          margins={"T": "25mm", "B": "20mm", "L": "25mm", "R": "20mm"})
    >>> cmd[-2:]
    ['in.html', 'out.pdf']
    >>> "--footer-center" in cmd and "Wezwanie z 18.08.2026 · str. [page] z [topage]" in cmd
    True
    >>> cmd = command_for_engine("wkhtmltopdf", out_path="out.pdf", tmp_html_path="in.html",
    ...                          margins={"T": "25mm", "B": "20mm", "L": "25mm", "R": "20mm"})
    >>> "str. [page] z [topage]" in cmd
    True

    >>> command_for_engine("bogus", out_path="out.pdf", tmp_html_path="in.html")
    Traceback (most recent call last):
        ...
    ValueError: unknown engine: 'bogus'
    """
    if engine == "weasyprint":
        return ["weasyprint", tmp_html_path, out_path]
    if engine == "chrome":
        return [
            chrome_path,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out_path}",
            "--virtual-time-budget=20000",
            f"file://{tmp_html_path}",
        ]
    if engine == "wkhtmltopdf":
        return [
            "wkhtmltopdf",
            "--encoding",
            "utf-8",
            "--enable-local-file-access",
            "--page-size",
            "A4",
            "-T",
            margins["T"],
            "-B",
            margins["B"],
            "-L",
            margins["L"],
            "-R",
            margins["R"],
            "--footer-font-name",
            "Liberation Serif",
            "--footer-font-size",
            "8",
            "--footer-spacing",
            "6",
            "--footer-center",
            (footer + " · str. [page] z [topage]") if footer else "str. [page] z [topage]",
            tmp_html_path,
            out_path,
        ]
    raise ValueError(f"unknown engine: {engine!r}")
