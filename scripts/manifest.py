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

import argparse
import datetime
import os
import re
import sys

from utils import human_size as human
from utils import sha256_file as sha256

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
                "mtime": datetime.datetime.fromtimestamp(
                    st.st_mtime, tz=datetime.timezone.utc
                )
                .date()
                .isoformat(),
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
        f"_Manifest wygenerowany "
        f"{datetime.datetime.now(tz=datetime.timezone.utc).date().isoformat()} "
        f"skryptem `manifest.py`. "
        f"Plików: {len(data)}. Pominięto `index.md` i `SHA256SUMS.txt` (pliki robocze teczki, "
        f"nie dowody). Opisy plików prowadź w tabeli powyżej manifestu._"
    )
    return "\n".join(L)


def parse_sha256sums(text: str) -> dict[str, str]:
    """Parse SHA256SUMS.txt-format text ('<sha>  <rel path>' per line) into {rel: sha}.

    Blank lines are ignored — a trailing newline in the file would otherwise crash
    the `sha, rel = line.split(None, 1)` unpack.

    >>> parse_sha256sums("abc123  a.txt\\n\\ndef456  b/c.txt\\n")
    {'a.txt': 'abc123', 'b/c.txt': 'def456'}
    >>> parse_sha256sums("")
    {}
    """
    recorded = {}
    for line in text.splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        sha, rel = line.split(None, 1)
        recorded[rel] = sha
    return recorded


def compare_manifest(actual: dict[str, str], recorded: dict[str, str]) -> dict:
    """Compare actual file checksums against a recorded SHA256SUMS.txt snapshot.

    Returns {'missing': [rel...], 'mismatched': [(rel, recorded_sha, actual_sha)...],
    'new': [rel...]} — files only in `recorded`, files in both with a different hash,
    and files only in `actual`, respectively.

    >>> compare_manifest({'a.txt': 's1'}, {'a.txt': 's1'})
    {'missing': [], 'mismatched': [], 'new': []}
    >>> compare_manifest({}, {'a.txt': 's1'})
    {'missing': ['a.txt'], 'mismatched': [], 'new': []}
    >>> compare_manifest({'a.txt': 's2'}, {'a.txt': 's1'})
    {'missing': [], 'mismatched': [('a.txt', 's1', 's2')], 'new': []}
    >>> compare_manifest({'b.txt': 's1'}, {})
    {'missing': [], 'mismatched': [], 'new': ['b.txt']}
    """
    missing, mismatched = [], []
    for rel, sha in recorded.items():
        if rel not in actual:
            missing.append(rel)
        elif actual[rel] != sha:
            mismatched.append((rel, sha, actual[rel]))
    new = [rel for rel in actual if rel not in recorded]
    return {"missing": missing, "mismatched": mismatched, "new": new}


def insert_or_replace_block(text: str, block: str, start: str, end: str) -> str:
    """Replace the `start`/`end`-delimited block in `text` with `block`, or append it
    under a new "## Manifest plików" heading if the markers aren't present yet.

    `block` is expected to already contain `start`/`end` itself (see `main()`'s
    "wstaw" command) — this function only locates what to replace, it doesn't
    construct the markers.

    >>> insert_or_replace_block("# Sprawa\\n\\ntreść\\n", "<S>\\nBLOK\\n<E>", "<S>", "<E>")
    '# Sprawa\\n\\ntreść\\n\\n## Manifest plików\\n\\n<S>\\nBLOK\\n<E>\\n'
    >>> insert_or_replace_block("przed\\n<S>\\nstare\\n<E>\\npo", "<S>\\nnowe\\n<E>", "<S>", "<E>")
    'przed\\n<S>\\nnowe\\n<E>\\npo'
    """
    if start in text and end in text:
        return re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            lambda _: block,
            text,
            flags=re.DOTALL,
        )
    return text.rstrip() + "\n\n## Manifest plików\n\n" + block + "\n"


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
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Zapisano {p} ({len(lines)} plików)")

    elif a.cmd == "sprawdz":
        root = a.arg1
        actual = {r["rel"]: r["sha"] for r in rows(root)}
        bad = missing = new = 0
        p = os.path.join(root, "SHA256SUMS.txt")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                recorded = parse_sha256sums(f.read())
            diff = compare_manifest(actual, recorded)
            for rel in diff["missing"]:
                print(f"BRAK PLIKU: {rel}")
            for rel, sha_recorded, sha_actual in diff["mismatched"]:
                print(
                    f"NIEZGODNA SUMA: {rel}\n  w SHA256SUMS: {sha_recorded}\n  faktyczna:    {sha_actual}"
                )
            for rel in diff["new"]:
                print(
                    f"NOWY PLIK (brak w SHA256SUMS — uruchom `manifest.py sumy`): {rel}"
                )
            missing, bad, new = (
                len(diff["missing"]),
                len(diff["mismatched"]),
                len(diff["new"]),
            )
        else:
            print(f"(brak {p} — pomijam porównanie z plikiem sum)")
        idx = os.path.join(root, "index.md")
        if os.path.exists(idx):
            with open(idx, encoding="utf-8") as f:
                txt = f.read()
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
        with open(idx, encoding="utf-8") as f:
            txt = f.read()
        block = f"{START}\n{table(root)}\n{END}"
        txt = insert_or_replace_block(txt, block, START, END)
        with open(idx, "w", encoding="utf-8") as f:
            f.write(txt)
        print(f"Zaktualizowano manifest w {idx}")


if __name__ == "__main__":
    main()
