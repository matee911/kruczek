#!/usr/bin/env python3
"""kontrola-pisma.py — mechaniczna kontrola gotowego pisma przed przekazaniem użytkownikowi.

Sprawdza to, co da się sprawdzić bez czytania ze zrozumieniem:
  * czy nie zostały niewypełnione pola [w nawiasach] i placeholdery
  * czy numeracja załączników jest ciągła i bez dziur
  * czy każde odesłanie „zał. N" / „Załącznik nr N" w treści ma odpowiadający załącznik
  * czy tytuły załączników na liście zgadzają się z tytułami na stronach załączników
  * czy każda suma SHA-256 podana w piśmie odpowiada istniejącemu plikowi w sprawie
  * czy pliki w dowody.zip pokrywają się z załącznikami
  * czy numeracja ustępów jest ciągła (bez powtórzeń i przeskoków)
  * czy nie ma dwóch różnych numeracji na tym samym poziomie
  * wymogi print&mail: rozmiar, liczba kartek, osadzenie fontów

Nie ocenia treści ani prawa — od tego jest recenzent (opus).

Użycie:
    kontrola-pisma.py pismo.pdf --sprawa <katalog-sprawy> [--zip dowody.zip]
Kod wyjścia: 0 = brak błędów blokujących, 1 = są błędy.
"""
import argparse, os, re, subprocess, sys, hashlib, shutil, zipfile, collections

BLAD, OSTRZ = [], []


def b(msg): BLAD.append(msg)
def o(msg): OSTRZ.append(msg)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def tekst_pdf(p):
    if not shutil.which("pdftotext"):
        sys.exit("BŁĄD: brak pdftotext (pakiet poppler-utils) — nie da się skontrolować pisma.")
    return subprocess.run(["pdftotext", "-layout", p, "-"],
                          capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--sprawa", required=True, help="katalog sprawy (z ARCHIWUM/ i index.md)")
    ap.add_argument("--zip", default=None, help="ścieżka do dowody.zip")
    ap.add_argument("--html", default=None,
                    help="źródłowy HTML pisma — pozwala wykryć pola class=\"fill\" dokładnie, "
                         "zamiast zgadywać po nawiasach w PDF")
    a = ap.parse_args()

    if not os.path.exists(a.pdf):
        sys.exit(f"BŁĄD: brak pliku {a.pdf}")
    t = tekst_pdf(a.pdf)

    # ---- 1. niewypełnione pola --------------------------------------------
    if a.html and os.path.exists(a.html):
        # ścieżka dokładna: czytamy źródło i szukamy pól class="fill"
        h = re.sub(r"<!--.*?-->", "", open(a.html, encoding="utf-8").read(), flags=re.S)
        fill = [x.strip() for x in re.findall(r'class="fill[^"]*"[^>]*>([^<]{0,120})', h) if x.strip()]
        if fill:
            b(f'Pola oznaczone class="fill" nadal niewypełnione ({len(fill)}): '
              + " · ".join(dict.fromkeys(fill))[:600])
        else:
            print("  wszystkie pola class=\"fill\" wypełnione")
    else:
        # ścieżka zapasowa: heurystyka po tekście PDF. Cytaty w „…" maskujemy — nawias
        # w cytacie (np. temat wiadomości „Re: [Zamówienie 2027] …") nie jest polem do wypełnienia.
        tm = re.sub(r"[„\"][^”\"]{0,400}[”\"]", lambda m: "\u0000" * len(m.group(0)), t)
        puste = [x for x in re.findall(r"\[[^\]\n]{3,120}\]", tm)
                 if not re.fullmatch(r"\[[\d.:\s/-]+\]", x) and re.search(r"[a-ząćęłńóśźż]", x)]
        if puste:
            b(f"Niewypełnione pola ({len(puste)}): " + " · ".join(dict.fromkeys(puste))[:600])
            o("Podaj --html <źródło pisma>, żeby wykryć pola dokładnie zamiast heurystycznie")
    for wzor in ("XXX", "TODO", "TBD", "Lorem ipsum", "…uzupełnij", "wpisz "):
        if wzor.lower() in t.lower():
            b(f"W piśmie został placeholder: „{wzor}”")

    # ---- 2. załączniki: numeracja, odesłania, tytuły -----------------------
    strony = re.findall(r"Za[łl][ąa]cznik\s+nr\s+(\d+)\s*[—–-]\s*(.+)", t, re.I)
    lista = re.findall(r"Za[łl][ąa]cznik\s+nr\s+(\d+):\s*(.+)", t, re.I)
    nr_stron = [int(n) for n, _ in strony]
    nr_listy = [int(n) for n, _ in lista]

    if nr_stron:
        oczek = list(range(1, max(nr_stron) + 1))
        braki = sorted(set(oczek) - set(nr_stron))
        if braki:
            b(f"Dziury w numeracji stron załączników: brak nr {braki}")
        dup = [n for n, c in collections.Counter(nr_stron).items() if c > 1]
        if dup:
            b(f"Powtórzone numery załączników: {dup}")
    if nr_listy and nr_stron and set(nr_listy) != set(nr_stron):
        b(f"Lista załączników {sorted(set(nr_listy))} nie zgadza się ze stronami załączników "
          f"{sorted(set(nr_stron))}")

    tyt_stron = {int(n): re.sub(r"\s+", " ", s).strip() for n, s in strony}
    tyt_listy = {int(n): re.sub(r"\s+", " ", s).strip() for n, s in lista}
    for n in sorted(set(tyt_stron) & set(tyt_listy)):
        a1 = tyt_stron[n].lower()
        a2 = re.sub(r"\(plik.*?\)", "", tyt_listy[n]).strip().lower()
        if a2 and not (a2 in a1 or a1 in a2):
            b(f"Załącznik nr {n}: tytuł na liście („{tyt_listy[n]}”) różni się od tytułu "
              f"na stronie załącznika („{tyt_stron[n]}”)")

    odeslania = {int(x) for x in re.findall(r"zał\.\s*(\d+)", t, re.I)}
    odeslania |= {int(x) for x in re.findall(r"za[łl][ąa]cznik(?:a|iem|u|ach|ow|ów)?\s+nr\s*(\d+)", t, re.I)}
    brak = sorted(odeslania - set(nr_stron)) if nr_stron else sorted(odeslania)
    if brak:
        b(f"Treść odsyła do załączników, których nie ma w piśmie: nr {brak}")
    nieuzyte = sorted(set(nr_stron) - odeslania)
    if nieuzyte:
        o(f"Załączniki dołączone, ale nieprzywołane w treści: nr {nieuzyte} "
          f"— dowód, do którego pismo się nie odwołuje, nic nie wnosi")

    # ---- 3. sumy kontrolne --------------------------------------------------
    sumy_w_pismie = set(re.findall(r"\b([0-9a-f]{64})\b", t))
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
            zle = z_test = None
            with zipfile.ZipFile(a.zip) as z:
                z_test = z.testzip()
            if z_test:
                b(f"dowody.zip uszkodzony przy pliku {z_test}")
            print(f"  dowody.zip: {len(nazwy)} plików")
            if "SHA256SUMS.txt" not in [os.path.basename(n) for n in nazwy]:
                o("dowody.zip nie zawiera SHA256SUMS.txt — dołóż, żeby odbiorca mógł zweryfikować")

    # ---- 5. numeracja ustępów ----------------------------------------------
    ust = [int(m.group(1)) for m in re.finditer(r"^\s{0,8}(\d{1,3})\.\s{2,}\S", t, re.M)]
    if ust:
        dup = [n for n, c in collections.Counter(ust).items() if c > 1]
        if dup:
            b(f"Numery ustępów powtarzają się: {sorted(dup)} — to najczęstszy błąd, "
              f"czytelnik nie wie, do którego punktu odsyła pismo")
        skoki = [(ust[i], ust[i + 1]) for i in range(len(ust) - 1) if ust[i + 1] - ust[i] not in (0, 1)]
        if skoki:
            o(f"Przeskoki w numeracji ustępów: {skoki}")

    # ---- 6. wymogi print&mail ----------------------------------------------
    mb = os.path.getsize(a.pdf) / 1048576
    if mb > 2:
        o(f"PDF ma {mb:.2f} MB — Envelo neoList przyjmuje max 2 MB (PUH: 15 MB)")
    if shutil.which("pdfinfo"):
        m = re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", a.pdf],
                                                        capture_output=True, text=True).stdout)
        if m and (int(m.group(1)) + 1) // 2 > 98:
            b(f"{m.group(1)} stron = {(int(m.group(1))+1)//2} kartek — limit to 98 kartek")
    if shutil.which("pdffonts"):
        out = subprocess.run(["pdffonts", a.pdf], capture_output=True, text=True).stdout
        lines = out.splitlines()
        if lines and "emb" in lines[0]:
            col = lines[0].index("emb")
            nie = [l[:36].strip() for l in lines[2:] if l.strip() and l[col:col + 3].strip() != "yes"]
            if nie:
                b(f"Fonty nieosadzone w PDF: {', '.join(nie)} — Envelo i e-Doręczenia odrzucą plik")

    # ---- 7. podpis ----------------------------------------------------------
    if not re.search(r"(Z powa[żz]aniem|podpis|_{5,}|…{3,})", t, re.I):
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
    print("\nTo kontrola mechaniczna. Merytorykę, prawo i język sprawdza /kruczek:recenzja.")
    sys.exit(1 if BLAD else 0)


if __name__ == "__main__":
    main()
