#!/usr/bin/env python3
"""dane_nadawcy_status.py — sprawdza, które krytyczne pola w dane-nadawcy.md są wypełnione.

Nie wypisuje wartości pól (tylko status) — żeby dane osobowe nie przeciekały do
CLAUDE.md, który bywa commitowany. Używane przez gen-claude-md.sh.

Użycie:
    dane_nadawcy_status.py <sciezka-do-dane-nadawcy.md>
Wyjście: jedna linia na pole krytyczne — "OK <pole>" albo "BRAK <pole>".
Jeśli plik nie istnieje: "BRAK <pole>" dla każdego krytycznego pola + "BRAK-PLIK".
"""

import re
import sys

# Zgodne z "Minimum potrzebne do pisania pism" w skills/dane-nadawcy/SKILL.md
KRYTYCZNE = [
    "Imię i nazwisko",
    "Do korespondencji",
    "Miejscowość w nagłówku pism",
    "E-mail w sprawach spornych",
]
WARUNKOWE_PRZEDSIEBIORCA = ["NIP"]

HEADER_KOMORKI = {
    "Pole",
    "Rodzaj",
    "Kanał",
    "Pytanie",
    "Wartość",
    "Adres",
    "Odpowiedź",
    "Uwagi",
}


def split_row(line: str) -> list[str]:
    """
    Dzieli wiersz tabeli markdown na komórki, respektując \\| jako znak ucieczki.

    >>> split_row("| Komórka 1 | Komórka 2 \\\\| z pionową kreską |")
    ['Komórka 1', 'Komórka 2 | z pionową kreską']
    >>> split_row("")
    []
    >>> split_row("|")
    []
    >>> split_row("| Komórka 1 | Komórka 2 |")
    ['Komórka 1', 'Komórka 2']
    """
    parts = re.split(r"(?<!\\)\|", line)
    return [p.replace("\\|", "|").strip() for p in parts if p.strip()]


def parsuj(text: str) -> dict[str, str]:
    r"""
    Parsuje tabelę w markdown i zwraca słownik {pole: wartość}.

    >>> parsuj("| Pole | Wartość |\n| --- | --- |\n| Imię i nazwisko | Jan Kowalski |\n")
    {'Imię i nazwisko': 'Jan Kowalski'}
    >>> parsuj("| Pole | Wartość |\n| --- | --- |\n| Imię i nazwisko | Jan Kowalski |\n| Do korespondencji | <brak> |\n")
    {'Imię i nazwisko': 'Jan Kowalski', 'Do korespondencji': '<brak>'}
    """
    wartosci: dict[str, str] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) < 2:
            continue
        pole, wartosc = cells[0], cells[1]
        pole = re.sub(r"\*\*", "", pole).strip()
        if pole in HEADER_KOMORKI or set(pole) <= set("-: "):
            continue
        wartosci[pole] = wartosc.strip()
    return wartosci


def puste(wartosc: str) -> bool:
    """
    Zwraca True, jeśli wartość jest pusta lub wygląda jak <brak> / <nie dotyczy>.

    >>> puste("<brak>")
    True
    >>> puste("<nie dotyczy>")
    True
    >>> puste("Jan Kowalski")
    False
    >>> puste("")
    True
    """
    return not wartosc or re.fullmatch(r"<.*>?", wartosc) is not None


def znajdz(wartosci: dict[str, str], pole: str) -> str:
    """
    Dopasowuje nazwę pola z KRYTYCZNE do klucza w tabeli — nagłówki w pliku bywają
    dłuższe (dopisek w nawiasie, np. 'Do korespondencji (na ten adres...)').

    >>> znajdz({'Do korespondencji (na ten adres...)': 'ul. Przykładowa 1'}, 'Do korespondencji')
    'ul. Przykładowa 1'
    >>> znajdz({'Imię i nazwisko': 'Jan Kowalski'}, 'Imię i nazwisko')
    'Jan Kowalski'
    >>> znajdz({'Imię i nazwisko': 'Jan Kowalski'}, 'Do korespondencji')
    ''
    """
    if pole in wartosci:
        return wartosci[pole]
    for k, v in wartosci.items():
        if k == pole or k.startswith((pole + " ", pole + "(")):
            return v
    return ""


def main():
    if len(sys.argv) != 2:
        sys.exit("Użycie: dane_nadawcy_status.py <plik>")

    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        for pole in KRYTYCZNE:
            print(f"BRAK {pole}")
        print("BRAK-PLIK")
        return

    wartosci = parsuj(text)
    # Charakter wystąpienia (konsument / przedsiębiorca / w cudzym imieniu) jest cechą
    # pojedynczej sprawy, nie tego pliku — zob. pole "Występuję jako" w index.md sprawy.
    # Tutaj jedyne, co da się stwierdzić, to czy użytkownik w ogóle wypełnił sekcję
    # działalności gospodarczej; jeśli tak, NIP staje się polem krytycznym.
    ma_dzialalnosc = any(
        not puste(znajdz(wartosci, p))
        for p in ("Firma", "Forma prawna", "REGON", "KRS")
    )
    pola = list(KRYTYCZNE)
    if ma_dzialalnosc:
        pola += WARUNKOWE_PRZEDSIEBIORCA

    for pole in pola:
        w = znajdz(wartosci, pole)
        print(("BRAK " if puste(w) else "OK ") + pole)


if __name__ == "__main__":
    main()
