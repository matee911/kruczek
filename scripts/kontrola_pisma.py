#!/usr/bin/env python3
"""kontrola_pisma.py — mechaniczna kontrola gotowego pisma przed przekazaniem użytkownikowi.

Sprawdza to, co da się sprawdzić bez czytania ze zrozumieniem:
  * czy nie zostały niewypełnione pola [w nawiasach] i placeholdery
  * czy numeracja załączników jest ciągła i bez dziur
  * czy każde odesłanie "zał. N" / "Załącznik nr N" w treści ma odpowiadający załącznik
  * czy tytuły załączników na liście zgadzają się z tytułami na stronach załączników
  * czy każda suma SHA-256 podana w piśmie odpowiada istniejącemu plikowi w sprawie
  * czy pliki w dowody.zip pokrywają się z załącznikami
  * czy numeracja ustępów jest ciągła (bez powtórzeń i przeskoków)
  * czy nie ma dwóch różnych numeracji na tym samym poziomie
  * wymogi print&mail: rozmiar, liczba kartek, osadzenie fontów

Nie ocenia treści ani prawa — od tego jest recenzent (opus).

Użycie:
    kontrola_pisma.py pismo.pdf --sprawa <katalog-sprawy> [--zip dowody.zip]
Kod wyjścia: 0 = brak błędów blokujących, 1 = są błędy.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

from kontrola_logika import (
    find_attachment_list_items,
    find_attachment_page_headers,
    find_cross_references,
    find_numbering_gaps_and_duplicates,
    find_paragraph_numbering_issues,
    find_placeholders,
    find_sha256_hashes,
    titles_match,
)
from utils import evaluate_print_mail_requirements, parse_unembedded_fonts
from utils import sha256_file as sha


def tekst_pdf(p):
    if not shutil.which("pdftotext"):
        sys.exit(
            "BŁĄD: brak pdftotext (pakiet poppler-utils) — nie da się skontrolować pisma."
        )
    return subprocess.run(
        ["pdftotext", "-layout", p, "-"], capture_output=True, text=True, check=False
    ).stdout


def main():
    BLAD, OSTRZ = [], []

    def b(msg):
        BLAD.append(msg)

    def o(msg):
        OSTRZ.append(msg)

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument(
        "--sprawa", required=True, help="katalog sprawy (z ARCHIWUM/ i index.md)"
    )
    ap.add_argument("--zip", default=None, help="ścieżka do dowody.zip")
    ap.add_argument(
        "--html",
        default=None,
        help='źródłowy HTML pisma — pozwala wykryć pola class="fill" dokładnie, '
        "zamiast zgadywać po nawiasach w PDF",
    )
    a = ap.parse_args()

    if not os.path.exists(a.pdf):
        sys.exit(f"BŁĄD: brak pliku {a.pdf}")
    t = tekst_pdf(a.pdf)

    # ---- 1. niewypełnione pola --------------------------------------------
    if a.html and os.path.exists(a.html):
        with open(a.html, encoding="utf-8") as f:
            h = re.sub(r"<!--.*?-->", "", f.read(), flags=re.DOTALL)
        fill = [
            x.strip()
            for x in re.findall(r'class="fill[^"]*"[^>]*>([^<]{0,120})', h)
            if x.strip()
        ]
        if fill:
            b(
                f'Pola oznaczone class="fill" nadal niewypełnione ({len(fill)}): '
                + " · ".join(dict.fromkeys(fill))[:600]
            )
        else:
            print('  wszystkie pola class="fill" wypełnione')
    else:
        puste = find_placeholders(t)
        if puste:
            b(
                f"Niewypełnione pola ({len(puste)}): "
                + " · ".join(dict.fromkeys(puste))[:600]
            )
            o(
                "Podaj --html <źródło pisma>, żeby wykryć pola dokładnie zamiast heurystycznie"
            )
    for wzor in ("XXX", "TODO", "TBD", "Lorem ipsum", "…uzupełnij", "wpisz "):
        if wzor.lower() in t.lower():
            b(f"W piśmie został placeholder: „{wzor}”")

    # ---- 2. załączniki: numeracja, odesłania, tytuły -----------------------
    strony = find_attachment_page_headers(t)
    lista = find_attachment_list_items(t)
    nr_stron = [int(n) for n, _ in strony]
    nr_listy = [int(n) for n, _ in lista]

    if nr_stron:
        braki, dup = find_numbering_gaps_and_duplicates(nr_stron)
        if braki:
            b(f"Dziury w numeracji stron załączników: brak nr {braki}")
        if dup:
            b(f"Powtórzone numery załączników: {dup}")
    if nr_listy and nr_stron and set(nr_listy) != set(nr_stron):
        b(
            f"Lista załączników {sorted(set(nr_listy))} nie zgadza się ze stronami załączników "
            f"{sorted(set(nr_stron))}"
        )

    tyt_stron = {int(n): re.sub(r"\s+", " ", s).strip() for n, s in strony}
    tyt_listy = {int(n): re.sub(r"\s+", " ", s).strip() for n, s in lista}
    for n in sorted(set(tyt_stron) & set(tyt_listy)):
        if not titles_match(tyt_stron[n], tyt_listy[n]):
            b(
                f"Załącznik nr {n}: tytuł na liście („{tyt_listy[n]}”)"
                f" różni się od tytułu na stronie załącznika („{tyt_stron[n]}”)"
            )

    odeslania = find_cross_references(t)
    brak = sorted(odeslania - set(nr_stron)) if nr_stron else sorted(odeslania)
    if brak:
        b(f"Treść odsyła do załączników, których nie ma w piśmie: nr {brak}")
    nieuzyte = sorted(set(nr_stron) - odeslania)
    if nieuzyte:
        o(
            f"Załączniki dołączone, ale nieprzywołane w treści: nr {nieuzyte} "
            f"— dowód, do którego pismo się nie odwołuje, nic nie wnosi"
        )

    # ---- 3. sumy kontrolne --------------------------------------------------
    sumy_w_pismie = find_sha256_hashes(t)
    realne = {}
    for root, dirs, files in os.walk(a.sprawa):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for fn in files:
            p = os.path.join(root, fn)
            if os.path.isfile(p) and not os.path.islink(p):
                try:
                    realne[sha(p)] = os.path.relpath(p, a.sprawa)
                except OSError:
                    pass
    for s in sorted(sumy_w_pismie - set(realne)):
        b(f"Suma SHA-256 podana w piśmie nie odpowiada żadnemu plikowi w sprawie: {s}")
    if sumy_w_pismie & set(realne):
        print(f"  potwierdzone sumy kontrolne: {len(sumy_w_pismie & set(realne))}")

    # ---- 4. dowody.zip ------------------------------------------------------
    if a.zip:
        if not os.path.exists(a.zip):
            b(f"Wskazany {a.zip} nie istnieje")
        else:
            with zipfile.ZipFile(a.zip) as z:
                nazwy = [n for n in z.namelist() if not n.endswith("/")]
            if not nazwy:
                b("dowody.zip jest pusty")
            z_test = None
            with zipfile.ZipFile(a.zip) as z:
                z_test = z.testzip()
            if z_test:
                b(f"dowody.zip uszkodzony przy pliku {z_test}")
            print(f"  dowody.zip: {len(nazwy)} plików")
            if "SHA256SUMS.txt" not in [os.path.basename(n) for n in nazwy]:
                o(
                    "dowody.zip nie zawiera SHA256SUMS.txt — dołóż, żeby odbiorca mógł zweryfikować"
                )

    # ---- 5. numeracja ustępów ----------------------------------------------
    dup_ust, skoki = find_paragraph_numbering_issues(t)
    if dup_ust:
        b(
            f"Numery ustępów powtarzają się: {dup_ust} — to najczęstszy błąd, "
            f"czytelnik nie wie, do którego punktu odsyła pismo"
        )
    if skoki:
        o(f"Przeskoki w numeracji ustępów: {skoki}")

    # ---- 6. wymogi print&mail ----------------------------------------------
    mb = os.path.getsize(a.pdf) / 1048576
    pages = None
    if shutil.which("pdfinfo"):
        m = re.search(
            r"Pages:\s+(\d+)",
            subprocess.run(
                ["pdfinfo", a.pdf], capture_output=True, text=True, check=False
            ).stdout,
        )
        if m:
            pages = int(m.group(1))
    for r in evaluate_print_mail_requirements(mb, pages):
        if r["check"] == "size" and not r["ok"]:
            o(
                f"PDF ma {r['size_mb']:.2f} MB — Envelo neoList przyjmuje max "
                f"{r['max_size_mb']} MB (PUH: 15 MB)"
            )
        elif r["check"] == "sheets" and not r["ok"]:
            b(f"{r['pages']} stron = {r['sheets']} kartek — limit to {r['max_sheets']} kartek")
    if shutil.which("pdffonts"):
        out = subprocess.run(
            ["pdffonts", a.pdf], capture_output=True, text=True, check=False
        ).stdout
        nie = parse_unembedded_fonts(out)
        if nie:
            b(
                f"Fonty nieosadzone w PDF: {', '.join(nie)} — Envelo i e-Doręczenia odrzucą plik"
            )

    # ---- 7. podpis ----------------------------------------------------------
    if not re.search(r"(Z powa[żz]aniem|podpis|_{5,}|…{3,})", t, re.IGNORECASE):
        o("W piśmie nie widać bloku podpisu — sprawdź, czy jest miejsce na podpis")

    # ---- raport -------------------------------------------------------------
    print()
    if BLAD:
        print(f"BŁĘDY BLOKUJĄCE ({len(BLAD)}):")
        for x in BLAD:
            print("  ✗ " + x)
    if OSTRZ:
        print(f"\nOSTRZEŻENIA ({len(OSTRZ)}):")
        for x in OSTRZ:
            print("  ! " + x)
    if not BLAD and not OSTRZ:
        print("OK — kontrola mechaniczna bez zastrzeżeń.")
    elif not BLAD:
        print("\nBrak błędów blokujących.")
    print(
        "\nTo kontrola mechaniczna. Merytorykę, prawo i język sprawdza /kruczek:recenzja."
    )
    sys.exit(1 if BLAD else 0)


if __name__ == "__main__":
    main()
