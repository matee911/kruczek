"""build_pismo_logic.py — pure logic extracted from build_pismo.py.

No I/O, no subprocess calls. Input: data in, output: data out — testable without
a PDF engine, pandoc, or the poppler-utils font tools installed.
"""

import os
import re
from collections.abc import Sequence
from html.parser import HTMLParser

TRESC_START, TRESC_KONIEC = "<!--KRUCZEK:TRESC:START-->", "<!--KRUCZEK:TRESC:END-->"


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


def flagi_weasyprint(pomoc: str) -> list[str]:
    """Flagi blokujące pobieranie zasobów, jeśli ta wersja weasyprint je zna (wyjście `weasyprint --help`).

    Szablon i załączniki nie potrzebują nic poza `data:` (obrazki wklejone w base64).

    >>> flagi_weasyprint("  --allowed-protocols <allowed-protocols>  Only authorize ...")
    ['--allowed-protocols', 'data']
    >>> flagi_weasyprint("usage: weasyprint [-h] input output")
    []
    """
    return ["--allowed-protocols", "data"] if "--allowed-protocols" in pomoc else []


def command_for_engine(
    engine: str,
    *,
    out_path: str,
    tmp_html_path: str,
    chrome_path: str | None = None,
    footer: str = "",
    margins: dict | None = None,
    weasyprint_flagi: Sequence[str] = (),
) -> list:
    """Build the subprocess argv for one of the three supported PDF engines.

    For "chrome", `tmp_html_path` must already be absolute — the caller resolves
    it (e.g. via os.path.abspath), since turning a relative path into a
    file:// URL correctly is a filesystem concern, not something this pure
    function should do implicitly against its own idea of "current directory".
    `margins` (a {"T", "B", "L", "R"} dict of CSS lengths) is only used by
    wkhtmltopdf, which — unlike weasyprint and Chrome — does not honour the
    @page margins already declared in the template's own CSS. `weasyprint_flagi`
    (see flagi_weasyprint) go after the output path.

    >>> command_for_engine("weasyprint", out_path="out.pdf", tmp_html_path="in.html")
    ['weasyprint', 'in.html', 'out.pdf']
    >>> command_for_engine("weasyprint", out_path="out.pdf", tmp_html_path="in.html",
    ...                    weasyprint_flagi=["--allowed-protocols", "data"])
    ['weasyprint', 'in.html', 'out.pdf', '--allowed-protocols', 'data']

    >>> command_for_engine("chrome", out_path="out.pdf", tmp_html_path="/tmp/in.html",
    ...                    chrome_path="/usr/bin/chrome")
    ... # doctest: +NORMALIZE_WHITESPACE
    ['/usr/bin/chrome', '--headless', '--disable-gpu', '--no-pdf-header-footer',
     '--host-resolver-rules=MAP * ~NOTFOUND', '--print-to-pdf=out.pdf',
     '--virtual-time-budget=20000', 'file:///tmp/in.html']

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
        return ["weasyprint", tmp_html_path, out_path, *weasyprint_flagi]
    if engine == "chrome":
        return [
            chrome_path,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            # Obrona w głąb dla nazw hostów; zasobów z plików i adresów IP pilnuje CSP szablonu.
            "--host-resolver-rules=MAP * ~NOTFOUND",
            f"--print-to-pdf={out_path}",
            "--virtual-time-budget=20000",
            f"file://{tmp_html_path}",
        ]
    if engine == "wkhtmltopdf":
        return [
            "wkhtmltopdf",
            "--encoding",
            "utf-8",
            "--disable-local-file-access",
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


DOZWOLONE_ZNACZNIKI = frozenset(
    "p h1 h2 h3 h4 ol ul li span div b strong i em u br blockquote table thead tbody tr th td sup sub".split()
)
# Drugie sito na surowym tekście — łapie też znacznik niedomknięty na końcu treści, który parser oddałby
# jako tekst, a przeglądarka po wklejeniu przed znacznikiem końca uznałaby za tag. Atrybuty tylko wewnątrz
# `<…`, żeby „one = dwa” w zwykłym zdaniu nie blokowało pisma.
_ZAKAZANE = re.compile(
    r"<\s*/?\s*(script|style|link|img|iframe|object|embed|svg|meta|base|form|input)\b"
    r"|<[^>]*?\b(src|href|style|srcset|on\w+)\s*=",
    re.IGNORECASE,
)


class _KontrolaTresci(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bledy = []

    def handle_starttag(self, tag, attrs):
        if tag not in DOZWOLONE_ZNACZNIKI:
            self.bledy.append(f"<{tag}>")
        self.bledy += [f"atrybut {nazwa} w <{tag}>" for nazwa, _ in attrs if nazwa != "class"]

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag not in DOZWOLONE_ZNACZNIKI:
            self.bledy.append(f"</{tag}>")

    def handle_comment(self, data):
        self.bledy.append("komentarz <!-- -->")

    def handle_decl(self, decl):
        self.bledy.append(f"<!{decl}>")

    def unknown_decl(self, data):
        self.bledy.append(f"<![{data}]>")

    def handle_pi(self, data):
        self.bledy.append(f"<?{data}>")


def sprawdz_tresc(tresc: str) -> None:
    """Treść pisma od agenta: tylko znaczniki tekstu z atrybutem class — bez obrazków, linków, stylów i skryptów.

    Wejście agenta zawiera treść drugiej strony; obrazek z file:// albo https:// silnik PDF pobrałby przy druku.

    >>> sprawdz_tresc('<h1>WEZWANIE</h1><p class="ust">Fakt (zał. 1).</p><ol class="pkt"><li>Żądanie</li></ol>')
    >>> sprawdz_tresc('<img src=file:///etc/hosts>')
    Traceback (most recent call last):
    ...
    ValueError: niedozwolony HTML w treści pisma: <img>, atrybut src w <img>
    >>> sprawdz_tresc('<p class="ust" onclick="x">a</p>')
    Traceback (most recent call last):
    ...
    ValueError: niedozwolony HTML w treści pisma: atrybut onclick w <p>
    >>> sprawdz_tresc('<p>a</p><img src=x')
    Traceback (most recent call last):
    ...
    ValueError: niedozwolony HTML w treści pisma: <img
    >>> sprawdz_tresc('<p>a</p><span class=x src=y')
    Traceback (most recent call last):
    ...
    ValueError: niedozwolony HTML w treści pisma: <span class=x src=
    >>> sprawdz_tresc('<p>Kwota: 100 zł; one = dwa</p>')
    """
    kontrola = _KontrolaTresci()
    kontrola.feed(tresc)
    kontrola.close()
    bledy = list(dict.fromkeys(kontrola.bledy))
    if not bledy and (m := _ZAKAZANE.search(tresc)):
        bledy = [tresc[m.start():m.end()]]
    if bledy:
        raise ValueError("niedozwolony HTML w treści pisma: " + ", ".join(bledy))


def wstaw_tresc(szablon: str, tresc: str) -> str:
    """Treść pisma z pliku agenta między znaczniki szablonu — bez przepisywania przez model.

    >>> wstaw_tresc("A<!--KRUCZEK:TRESC:START-->wzór<!--KRUCZEK:TRESC:END-->B", "<p>nowe</p>")
    'A<!--KRUCZEK:TRESC:START--><p>nowe</p><!--KRUCZEK:TRESC:END-->B'
    >>> wstaw_tresc("bez znaczników", "x")
    Traceback (most recent call last):
    ...
    ValueError: szablon nie ma znaczników treści <!--KRUCZEK:TRESC:START--> … <!--KRUCZEK:TRESC:END-->
    >>> wstaw_tresc("A<!--KRUCZEK:TRESC:START--><!--KRUCZEK:TRESC:END-->B", '<img src="https://x.invalid/a.png">')
    Traceback (most recent call last):
    ...
    ValueError: niedozwolony HTML w treści pisma: <img>, atrybut src w <img>
    """
    sprawdz_tresc(tresc)
    if (
        szablon.count(TRESC_START) != 1
        or szablon.count(TRESC_KONIEC) != 1
        or szablon.index(TRESC_START) > szablon.index(TRESC_KONIEC)
    ):
        raise ValueError(f"szablon nie ma znaczników treści {TRESC_START} … {TRESC_KONIEC}")
    przed, reszta = szablon.split(TRESC_START, 1)
    _, po = reszta.split(TRESC_KONIEC, 1)
    return przed + TRESC_START + tresc + TRESC_KONIEC + po
