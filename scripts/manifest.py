#!/usr/bin/env python3
"""manifest.py — sumy kontrolne i manifest plików sprawy.

Podkomendy:
  skan   <katalog-sprawy>            wypisz tabelę markdown wszystkich plików (ścieżka, data, rozmiar, SHA-256)
  sumy   <katalog-sprawy>            zapisz/odśwież SHA256SUMS.txt w katalogu
  sprawdz <katalog-sprawy>           zweryfikuj pliki względem SHA256SUMS.txt oraz sum wpisanych w index.md
  wstaw  <index.md> <katalog-sprawy> podmień blok manifestu w index.md (między znacznikami)

Znaczniki w index.md:
  <!-- KRUCZEK:MANIFEST:START -->
  ... tabela generowana automatycznie ...
  <!-- KRUCZEK:MANIFEST:END -->
"""

import sys, os, datetime, re, argparse
from utils import sha256_file as sha256, human_size as human

SKIP_DIRS = {".git", "__pycache__", ".DS_Store", "node_modules", ".obsidian"}
# index.md nie wchodzi do manifestu: manifest jest w nim zapisywany, więc jego suma
# zmieniałaby się przy każdym zapisie (odwołanie cykliczne). To plik roboczy sprawy,
# nie dowód. SHA256SUMS.txt z tego samego powodu.
SKIP_FILES = {"SHA256SUMS.txt", "index.md"}
START = "<!-- KRUCZEK:MANIFEST:START -->"
END = "<!-- KRUCZEK:MANIFEST:END -->"


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn in SKIP_FILES or fn.startswith("."):
                continue
            p = os.path.join(dirpath, fn)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            yield p, os.path.relpath(p, root)


def rows(root):
    out = []
    for p, rel in walk(root):
        st = os.stat(p)
        out.append(
            {
                "rel": rel,
                "mtime": datetime.date.fromtimestamp(st.st_mtime).isoformat(),
                "size": human(st.st_size),
                "sha": sha256(p),
            }
        )
    return out


def table(root):
    data = rows(root)
    L = ["| Plik | Data pliku | Rozmiar | SHA-256 |", "|---|---|---|---|"]
    for r in data:
        L.append(f"| `{r['rel']}` | {r['mtime']} | {r['size']} | `{r['sha']}` |")
    L.append("")
    L.append(
        f"_Manifest wygenerowany {datetime.date.today().isoformat()} skryptem `manifest.py`. "
        f"Plików: {len(data)}. Pominięto `index.md` i `SHA256SUMS.txt` (pliki robocze teczki, "
        f"nie dowody). Opisy plików prowadź w tabeli powyżej manifestu._"
    )
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["skan", "sumy", "sprawdz", "wstaw"])
    ap.add_argument("arg1")
    ap.add_argument("arg2", nargs="?")
    a = ap.parse_args()

    if a.cmd == "skan":
        print(table(a.arg1))

    elif a.cmd == "sumy":
        root = a.arg1
        lines = [f"{r['sha']}  {r['rel']}" for r in rows(root)]
        p = os.path.join(root, "SHA256SUMS.txt")
        open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print(f"Zapisano {p} ({len(lines)} plików)")

    elif a.cmd == "sprawdz":
        root = a.arg1
        actual = {r["rel"]: r["sha"] for r in rows(root)}
        bad = missing = new = 0
        p = os.path.join(root, "SHA256SUMS.txt")
        if os.path.exists(p):
            recorded = {}
            for line in open(p, encoding="utf-8"):
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                sha, rel = line.split(None, 1)
                recorded[rel] = sha
            for rel, sha in recorded.items():
                if rel not in actual:
                    print(f"BRAK PLIKU: {rel}")
                    missing += 1
                elif actual[rel] != sha:
                    print(
                        f"NIEZGODNA SUMA: {rel}\n  w SHA256SUMS: {sha}\n  faktyczna:    {actual[rel]}"
                    )
                    bad += 1
            for rel in actual:
                if rel not in recorded:
                    print(
                        f"NOWY PLIK (brak w SHA256SUMS — uruchom `manifest.py sumy`): {rel}"
                    )
                    new += 1
        else:
            print(f"(brak {p} — pomijam porównanie z plikiem sum)")
        idx = os.path.join(root, "index.md")
        if os.path.exists(idx):
            txt = open(idx, encoding="utf-8").read()
            declared = set(re.findall(r"\b([0-9a-f]{64})\b", txt))
            real = set(actual.values())
            for d in sorted(declared - real):
                print(f"SUMA W index.md BEZ ODPOWIADAJĄCEGO PLIKU: {d}")
                bad += 1
            print(
                f"index.md: {len(declared)} sum, wszystkie odnalezione: {not (declared - real)}"
            )
        if bad or missing:
            print(f"PROBLEMY: {bad} niezgodnych, {missing} brakujących, {new} nowych.")
        elif new:
            print(
                f"Sumy zgodne; {new} nowych plików do zaewidencjonowania (`manifest.py sumy`)."
            )
        else:
            print("OK — wszystko się zgadza.")
        sys.exit(1 if (bad or missing) else 0)

    elif a.cmd == "wstaw":
        idx, root = a.arg1, a.arg2
        if not root:
            sys.exit("wstaw wymaga dwóch argumentów: <index.md> <katalog-sprawy>")
        txt = open(idx, encoding="utf-8").read()
        block = f"{START}\n{table(root)}\n{END}"
        if START in txt and END in txt:
            txt = re.sub(
                re.escape(START) + r".*?" + re.escape(END),
                lambda _: block,
                txt,
                flags=re.S,
            )
        else:
            txt = txt.rstrip() + "\n\n## Manifest plików\n\n" + block + "\n"
        open(idx, "w", encoding="utf-8").write(txt)
        print(f"Zaktualizowano manifest w {idx}")


if __name__ == "__main__":
    main()
