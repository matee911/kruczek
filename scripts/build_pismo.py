#!/usr/bin/env python3
"""build_pismo.py — składa pismo w PDF razem z wdrukowanymi załącznikami.

Marginesy 25/20/25/20 mm (góra/dół/lewy/prawy) — spełniają jednocześnie:
  * Envelo neoList: min. 8 mm góra/dół, 15 mm boki
  * PUH e-Doręczenia: min. 10 mm góra, 8 mm dół, 15 mm boki
  * ISO 838 (dziurki do ~16 mm od krawędzi) — lewy 25 mm zostawia zapas na wpięcie akt
Prawy górny róg stron nieparzystych zostaje wolny (Envelo drukuje tam kod 15×15 mm
dla maszyn kopertujących, 22 mm od górnej krawędzi).

Użycie:
    build_pismo.py pismo.html -o wyjscie.pdf \\
        -z dowody/naglowki.txt:"Pełne nagłówki wiadomości" \\
        -z dowody/analiza.md:"Analiza techniczna" \\
        --stopka "Wezwanie z 18.08.2026"

Wymaga jeden z: weasyprint, Chrome/Chromium, wkhtmltopdf (próbowane w tej kolejności —
żaden nie jest zakładany jako "ten jeden słuszny", bo różni użytkownicy mają różne
narzędzia zainstalowane). Dla .md dodatkowo pandoc.

Marginesy 25/20/25/20 mm są ustawione w templates/pismo.html jako reguła CSS @page —
weasyprint i Chrome ją honorują. wkhtmltopdf ma słabe wsparcie @page, więc dostaje
też te same wartości jako flagi CLI (MARGINS niżej) — trzymaj je zsynchronizowane
z @page w szablonie, jeśli zmieniasz jedno albo drugie.
"""

import argparse
import html as H
import os
import re
import shutil
import subprocess
import sys

from utils import human_size as human
from utils import sha256_file as sha

PRE_EXT = {".txt", ".eml", ".log", ".csv", ".json", ".msg", ".ini", ".xml"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MARGINS = {"T": "25mm", "B": "20mm", "L": "25mm", "R": "20mm"}

CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def find_chrome():
    """Zwraca ścieżkę do binarki Chrome/Chromium, albo None."""
    for c in CHROME_CANDIDATES:
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            p = shutil.which(c)
            if p:
                return p
    return None


def render_md(path):
    if not shutil.which("pandoc"):
        with open(path, encoding="utf-8") as f:
            return "<pre>" + H.escape(f.read()) + "</pre>"
    out = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "html5", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    out = re.sub(r"^\s*<h1[^>]*>.*?</h1>", "", out, flags=re.DOTALL)
    for a, b in (
        ("<h1", "<h4"),
        ("</h1>", "</h4>"),
        ("<h2", "<h4"),
        ("</h2>", "</h4>"),
        ("<h3", "<h5"),
        ("</h3>", "</h5>"),
    ):
        out = out.replace(a, b)
    return out


def render_attachment(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".md":
        return render_md(path)
    if ext in IMG_EXT:
        import base64
        import mimetypes

        mt = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:{mt};base64,{b64}" style="max-width:100%">'
    if ext in PRE_EXT or ext == ".html":
        with open(path, encoding="utf-8", errors="replace") as f:
            return "<pre>" + H.escape(f.read()) + "</pre>"
    return (
        f"<p><i>Załącznik w postaci pliku binarnego <code>{H.escape(os.path.basename(path))}</code> "
        f"({human(os.path.getsize(path))}) — dołączony osobno w <code>dowody.zip</code>. "
        f"Suma kontrolna SHA-256: <code>{sha(path)}</code></i></p>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("szablon")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument(
        "-z",
        "--zalacznik",
        action="append",
        default=[],
        help="ścieżka:Tytuł załącznika (można podać wielokrotnie)",
    )
    ap.add_argument("--stopka", default="")
    ap.add_argument("--keep-html", action="store_true")
    a = ap.parse_args()

    with open(a.szablon, encoding="utf-8") as f:
        tpl = f.read()

    blocks, lista, zal_info = [], [], []
    for i, spec in enumerate(a.zalacznik, 1):
        path, _, tytul = spec.partition(":")
        tytul = tytul or os.path.basename(path)
        if not os.path.exists(path):
            sys.exit(f"BŁĄD: brak pliku załącznika: {path}")
        s = sha(path)
        zal_info.append((i, tytul, os.path.basename(path), s))
        blocks.append(
            f'<div class="pb zal-strona">\n'
            f'<h2 class="bez-numeru">Załącznik nr {i} — {H.escape(tytul)}</h2>\n'
            f'<p class="zal-meta">plik: {H.escape(os.path.basename(path))} &nbsp;·&nbsp; '
            f"rozmiar: {human(os.path.getsize(path))} &nbsp;·&nbsp; SHA-256: {s}</p>\n"
            f'<div class="zal-tresc">{render_attachment(path)}</div>\n</div>'
        )
        lista.append(
            f'<li>{H.escape(tytul)} <span class="male">(plik <code>'
            f"{H.escape(os.path.basename(path))}</code>)</span></li>"
        )

    tpl = tpl.replace("<!--KRUCZEK:ZALACZNIKI-->", "\n".join(blocks))
    tpl = tpl.replace(
        "<!--KRUCZEK:LISTA_ZALACZNIKOW-->", "\n".join(lista) or "<li>brak</li>"
    )

    tmp = a.out + ".build.html"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(tpl)

    chrome = find_chrome()
    if shutil.which("weasyprint"):
        engine = "weasyprint"
        subprocess.run(["weasyprint", tmp, a.out], check=True)
    elif chrome:
        engine = "chrome"
        # Marginesy i rozmiar strony bierze z @page w szablonie — Chrome headless
        # nie ma prostych flag CLI na marginesy (tylko przez DevTools Protocol),
        # ale poprawnie honoruje CSS paged media, więc @page wystarczy.
        cmd = [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={a.out}",
            "--virtual-time-budget=20000",
            f"file://{os.path.abspath(tmp)}",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0 or not os.path.exists(a.out):
            sys.exit("Chrome/Chromium headless: " + (r.stderr or "")[-800:])
    elif shutil.which("wkhtmltopdf"):
        engine = "wkhtmltopdf"
        # Bez --dpi: w praktyce łamał @page i ściskał strony (18 stron wychodziło
        # jako 8, tekst wylewał się poza wiersz). wkhtmltopdf i tak nie honoruje
        # @page z szablonu, więc marginesy dostaje tu jawnie jako flagi CLI.
        cmd = [
            "wkhtmltopdf",
            "--encoding",
            "utf-8",
            "--enable-local-file-access",
            "--page-size",
            "A4",
            "-T",
            MARGINS["T"],
            "-B",
            MARGINS["B"],
            "-L",
            MARGINS["L"],
            "-R",
            MARGINS["R"],
            "--footer-font-name",
            "Liberation Serif",
            "--footer-font-size",
            "8",
            "--footer-spacing",
            "6",
            "--footer-center",
            (a.stopka + " · str. [page] z [topage]")
            if a.stopka
            else "str. [page] z [topage]",
            tmp,
            a.out,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            sys.exit("wkhtmltopdf: " + (r.stderr or "")[-800:])
    else:
        sys.exit(
            "BŁĄD: brak silnika PDF (weasyprint / Chrome lub Chromium / wkhtmltopdf).\n"
            "Zainstaluj jedno z nich:\n"
            "  macOS:  brew install weasyprint         (albo zainstaluj Google Chrome)\n"
            "  Linux:  sudo apt install weasyprint      (albo: sudo apt install chromium,"
            " albo: pip install weasyprint)\n"
            "Potem uruchom ponownie. Pełną listę zależności sprawdza "
            "${CLAUDE_PLUGIN_ROOT}/scripts/check-deps.sh."
        )

    if not a.keep_html:
        os.remove(tmp)

    # ---------- raport ----------
    pages = "?"
    if shutil.which("pdfinfo"):
        m = re.search(
            r"Pages:\s+(\d+)",
            subprocess.run(
                ["pdfinfo", a.out], capture_output=True, text=True, check=False
            ).stdout,
        )
        if m:
            pages = m.group(1)

    print(f"Zapisano:  {a.out}")
    print(f"Silnik:    {engine}")
    print(f"Stron:     {pages}")
    print(f"Rozmiar:   {human(os.path.getsize(a.out))}")
    print(f"SHA-256:   {sha(a.out)}")
    print(
        f"Marginesy: góra {MARGINS['T']} · dół {MARGINS['B']} · lewy {MARGINS['L']} · prawy {MARGINS['R']}"
    )

    if zal_info:
        print("\nZałączniki wdrukowane w PDF:")
        for i, tytul, plik, s in zal_info:
            print(f"  {i}. {tytul}  [{plik}]  {s[:16]}…")

    # kontrola wymogów print&mail
    print("\nKontrola wymogów wysyłki papierowej:")
    ok = True
    size_mb = os.path.getsize(a.out) / 1024 / 1024
    print(
        f"  {'OK ' if size_mb <= 2 else 'UWAGA'} rozmiar {size_mb:.2f} MB (Envelo neoList: max 2 MB, PUH: max 15 MB)"
    )
    ok &= size_mb <= 2
    if pages != "?":
        kartek = (int(pages) + 1) // 2
        print(
            f"  {'OK ' if kartek <= 98 else 'UWAGA'} {pages} stron = {kartek} kartek dwustronnie (max 98 kartek)"
        )
        ok &= kartek <= 98
    if shutil.which("pdffonts"):
        out = subprocess.run(
            ["pdffonts", a.out], capture_output=True, text=True, check=False
        ).stdout
        lines = out.splitlines()
        # kolumny mają stałą szerokość; "type" bywa dwuwyrazowe ("CID TrueType"),
        # więc pozycję kolumny emb bierzemy z nagłówka, nie ze split()
        col = lines[0].index("emb") if lines and "emb" in lines[0] else None
        rows = [l for l in lines[2:] if l.strip()]
        if col is None:
            print(
                "  ?   nie udało się odczytać nagłówka pdffonts — sprawdź osadzenie fontów ręcznie"
            )
        else:
            nieosadzone = [
                l[:36].strip() for l in rows if l[col : col + 3].strip() != "yes"
            ]
            if nieosadzone:
                print(
                    f"  UWAGA fonty NIEOSADZONE: {', '.join(nieosadzone)} — Envelo i PUH tego nie przyjmą"
                )
                ok = False
            else:
                print(f"  OK  wszystkie fonty osadzone ({len(rows)})")
    if not ok:
        print("\n  → Popraw powyższe przed wysyłką przez Envelo / e-Doręczenia.")

    print("\nZanim przekażesz pismo użytkownikowi: uruchom kontrolę spójności")
    print(f"  kontrola_pisma.py {a.out} --sprawa <katalog-sprawy>")


if __name__ == "__main__":
    main()
