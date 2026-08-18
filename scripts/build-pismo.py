#!/usr/bin/env python3
"""build-pismo.py — składa pismo w PDF razem z wdrukowanymi załącznikami.

Marginesy 25/20/25/20 mm (góra/dół/lewy/prawy) — spełniają jednocześnie:
  * Envelo neoList: min. 8 mm góra/dół, 15 mm boki
  * PUH e-Doręczenia: min. 10 mm góra, 8 mm dół, 15 mm boki
  * ISO 838 (dziurki do ~16 mm od krawędzi) — lewy 25 mm zostawia zapas na wpięcie akt
Prawy górny róg stron nieparzystych zostaje wolny (Envelo drukuje tam kod 15×15 mm
dla maszyn kopertujących, 22 mm od górnej krawędzi).

Użycie:
    build-pismo.py pismo.html -o wyjscie.pdf \\
        -z dowody/naglowki.txt:"Pełne nagłówki wiadomości" \\
        -z dowody/analiza.md:"Analiza techniczna" \\
        --stopka "Wezwanie z 18.08.2026"

Wymaga: wkhtmltopdf (albo weasyprint). Dla .md dodatkowo pandoc.
"""
import argparse, os, html as H, re, subprocess, shutil, sys, hashlib

PRE_EXT = {".txt", ".eml", ".log", ".csv", ".json", ".msg", ".ini", ".xml"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MARGINS = {"T": "25mm", "B": "20mm", "L": "25mm", "R": "20mm"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def human(n):
    for u in ("B", "KB", "MB"):
        if n < 1024 or u == "MB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def render_md(path):
    if not shutil.which("pandoc"):
        return "<pre>" + H.escape(open(path, encoding="utf-8").read()) + "</pre>"
    out = subprocess.run(["pandoc", "-f", "markdown", "-t", "html5", path],
                         capture_output=True, text=True, check=True).stdout
    out = re.sub(r"^\s*<h1[^>]*>.*?</h1>", "", out, flags=re.S)
    for a, b in (("<h1", "<h4"), ("</h1>", "</h4>"), ("<h2", "<h4"), ("</h2>", "</h4>"),
                 ("<h3", "<h5"), ("</h3>", "</h5>")):
        out = out.replace(a, b)
    return out


def render_attachment(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".md":
        return render_md(path)
    if ext in IMG_EXT:
        import base64, mimetypes
        mt = mimetypes.guess_type(path)[0] or "image/png"
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        return f'<img src="data:{mt};base64,{b64}" style="max-width:100%">'
    if ext in PRE_EXT or ext == ".html":
        return "<pre>" + H.escape(open(path, encoding="utf-8", errors="replace").read()) + "</pre>"
    return (f'<p><i>Załącznik w postaci pliku binarnego <code>{H.escape(os.path.basename(path))}</code> '
            f'({human(os.path.getsize(path))}) — dołączony osobno w <code>dowody.zip</code>. '
            f'Suma kontrolna SHA-256: <code>{sha(path)}</code></i></p>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("szablon")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("-z", "--zalacznik", action="append", default=[],
                    help="ścieżka:Tytuł załącznika (można podać wielokrotnie)")
    ap.add_argument("--stopka", default="")
    ap.add_argument("--keep-html", action="store_true")
    a = ap.parse_args()

    tpl = open(a.szablon, encoding="utf-8").read()

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
            f'rozmiar: {human(os.path.getsize(path))} &nbsp;·&nbsp; SHA-256: {s}</p>\n'
            f'<div class="zal-tresc">{render_attachment(path)}</div>\n</div>')
        lista.append(f'<li>{H.escape(tytul)} <span class="male">(plik <code>'
                     f'{H.escape(os.path.basename(path))}</code>)</span></li>')

    tpl = tpl.replace("<!--KRUCZEK:ZALACZNIKI-->", "\n".join(blocks))
    tpl = tpl.replace("<!--KRUCZEK:LISTA_ZALACZNIKOW-->",
                      "\n".join(lista) or "<li>brak</li>")

    tmp = a.out + ".build.html"
    open(tmp, "w", encoding="utf-8").write(tpl)

    if shutil.which("wkhtmltopdf"):
        cmd = ["wkhtmltopdf", "--encoding", "utf-8", "--enable-local-file-access",
               "--page-size", "A4", "--dpi", "300",
               "-T", MARGINS["T"], "-B", MARGINS["B"], "-L", MARGINS["L"], "-R", MARGINS["R"],
               "--footer-font-name", "Liberation Serif", "--footer-font-size", "8",
               "--footer-spacing", "6",
               "--footer-center", (a.stopka + " · str. [page] z [topage]") if a.stopka
                                  else "str. [page] z [topage]",
               tmp, a.out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("wkhtmltopdf: " + (r.stderr or "")[-800:])
    elif shutil.which("weasyprint"):
        subprocess.run(["weasyprint", tmp, a.out], check=True)
    else:
        sys.exit("BŁĄD: brak wkhtmltopdf i weasyprint — zainstaluj jedno z nich.")

    if not a.keep_html:
        os.remove(tmp)

    # ---------- raport ----------
    pages = "?"
    if shutil.which("pdfinfo"):
        m = re.search(r"Pages:\s+(\d+)",
                      subprocess.run(["pdfinfo", a.out], capture_output=True, text=True).stdout)
        if m:
            pages = m.group(1)

    print(f"Zapisano:  {a.out}")
    print(f"Stron:     {pages}")
    print(f"Rozmiar:   {human(os.path.getsize(a.out))}")
    print(f"SHA-256:   {sha(a.out)}")
    print(f"Marginesy: góra {MARGINS['T']} · dół {MARGINS['B']} · lewy {MARGINS['L']} · prawy {MARGINS['R']}")

    if zal_info:
        print("\nZałączniki wdrukowane w PDF:")
        for i, tytul, plik, s in zal_info:
            print(f"  {i}. {tytul}  [{plik}]  {s[:16]}…")

    # kontrola wymogów print&mail
    print("\nKontrola wymogów wysyłki papierowej:")
    ok = True
    size_mb = os.path.getsize(a.out) / 1024 / 1024
    print(f"  {'OK ' if size_mb <= 2 else 'UWAGA'} rozmiar {size_mb:.2f} MB (Envelo neoList: max 2 MB, PUH: max 15 MB)")
    ok &= size_mb <= 2
    if pages != "?":
        kartek = (int(pages) + 1) // 2
        print(f"  {'OK ' if kartek <= 98 else 'UWAGA'} {pages} stron = {kartek} kartek dwustronnie (max 98 kartek)")
        ok &= kartek <= 98
    if shutil.which("pdffonts"):
        out = subprocess.run(["pdffonts", a.out], capture_output=True, text=True).stdout
        lines = out.splitlines()
        # kolumny mają stałą szerokość; "type" bywa dwuwyrazowe ("CID TrueType"),
        # więc pozycję kolumny emb bierzemy z nagłówka, nie ze split()
        col = lines[0].index("emb") if lines and "emb" in lines[0] else None
        rows = [l for l in lines[2:] if l.strip()]
        if col is None:
            print("  ?   nie udało się odczytać nagłówka pdffonts — sprawdź osadzenie fontów ręcznie")
        else:
            nieosadzone = [l[:36].strip() for l in rows if l[col:col + 3].strip() != "yes"]
            if nieosadzone:
                print(f"  UWAGA fonty NIEOSADZONE: {', '.join(nieosadzone)} — Envelo i PUH tego nie przyjmą")
                ok = False
            else:
                print(f"  OK  wszystkie fonty osadzone ({len(rows)})")
    if not ok:
        print("\n  → Popraw powyższe przed wysyłką przez Envelo / e-Doręczenia.")

    print("\nZanim przekażesz pismo użytkownikowi: uruchom kontrolę spójności")
    print(f"  kontrola-pisma.py {a.out} --sprawa <katalog-sprawy>")


if __name__ == "__main__":
    main()
