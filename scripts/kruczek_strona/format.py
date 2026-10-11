"""Tekst dla strony: daty dd.mm.rrrr, odmiana liczebników, długość terminu słownie, data z formularza,
polecenia do wklejenia w rozmowie z Claude. Nic tu nie liczy terminów — daty przychodzą z kruczek_core."""

from __future__ import annotations

import calendar
import datetime as dt
import re
import shlex

from kruczek_core.dni_wolne import PIERWSZY_ROK
from kruczek_core.terminy import parsuj_dlugosc

DNI_TYGODNIA = ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")
MIESIACE = ("Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień",
            "Październik", "Listopad", "Grudzień")
_DATA = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
_JEDNOSTKI = {"d": ("dzień", "dni", "dni"), "t": ("tydzień", "tygodnie", "tygodni"),
              "m": ("miesiąc", "miesiące", "miesięcy"), "r": ("rok", "lata", "lat")}


def data_pl(d: dt.date) -> str:
    """
    >>> data_pl(dt.date(2026, 9, 5))
    '05.09.2026'
    """
    return d.strftime("%d.%m.%Y")


def dzien_tygodnia(d: dt.date) -> str:
    """
    >>> dzien_tygodnia(dt.date(2026, 10, 9))
    'piątek'
    """
    return DNI_TYGODNIA[d.weekday()]


def odmiana(n: int, formy: tuple[str, str, str]) -> str:
    """Liczba z rzeczownikiem: (1, 2–4, 5+) z wyjątkiem 12–14.

    >>> [odmiana(n, ("sprawa", "sprawy", "spraw")) for n in (1, 2, 5, 12, 22, 25)]
    ['1 sprawa', '2 sprawy', '5 spraw', '12 spraw', '22 sprawy', '25 spraw']
    """
    return f"{n} {formy[_numer_formy(n)]}"


def _numer_formy(n: int) -> int:
    """Indeks formy liczebnika: 0 dla 1, 1 dla 2–4 (bez 12–14), 2 w pozostałych przypadkach."""
    if n == 1:
        return 0
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return 1
    return 2


def dni(n: int) -> str:
    """
    >>> dni(1), dni(4)
    ('1 dzień', '4 dni')
    """
    return odmiana(n, _JEDNOSTKI["d"])


def zostalo(n: int) -> str:
    """Ile dni do terminu (n ≥ 0).

    >>> [zostalo(n) for n in (0, 1, 4, 7, 22)]
    ['to dziś', 'został 1 dzień', 'zostały 4 dni', 'zostało 7 dni', 'zostały 22 dni']
    """
    if n == 0:
        return "to dziś"
    return f"{('został', 'zostały', 'zostało')[_numer_formy(n)]} {dni(n)}"


def temu(n: int) -> str:
    """
    >>> [temu(n) for n in (0, 1, 7)]
    ['dziś', 'wczoraj', '7 dni temu']
    """
    return {0: "dziś", 1: "wczoraj"}.get(n, f"{dni(n)} temu")


def za(n: int) -> str:
    """
    >>> [za(n) for n in (1, 11)]
    ['jutro', 'za 11 dni']
    """
    return "jutro" if n == 1 else f"za {dni(n)}"


def dlugosc_slownie(dlugosc: str) -> str:
    """Długość terminu z sprawa.json słownie.

    >>> [dlugosc_slownie(x) for x in ("14d", "1t", "2t", "1m", "3m", "1r", "5r")]
    ['14 dni', '1 tydzień', '2 tygodnie', '1 miesiąc', '3 miesiące', '1 rok', '5 lat']
    """
    n, jednostka = parsuj_dlugosc(dlugosc)
    return odmiana(n, _JEDNOSTKI[jednostka])


def data_doreczenia(tekst: str, dzis: dt.date) -> dt.date:
    """Data z pola „Data doręczenia” (dd.mm.rrrr). Błąd = ValueError z tekstem dla człowieka:
    co jest nie tak i jak to poprawić.

    >>> data_doreczenia(" 9.10.2026 ", dt.date(2026, 10, 9))
    datetime.date(2026, 10, 9)
    >>> data_doreczenia("31.09.2026", dt.date(2026, 10, 9))
    Traceback (most recent call last):
    ValueError: Wrzesień 2026 ma 30 dni. Sprawdź dzień w potwierdzeniu odbioru.
    >>> data_doreczenia("01.01.0000", dt.date(2026, 10, 9))
    Traceback (most recent call last):
    ValueError: Rok musi być 2000 albo późniejszy. Sprawdź rok w potwierdzeniu odbioru.
    """
    tekst = tekst.strip()
    if not tekst:
        raise ValueError("Wpisz datę doręczenia. Bez niej termin jest tylko szacunkiem.")
    m = _DATA.match(tekst)
    if not m:
        raise ValueError("Wpisz datę jako dd.mm.rrrr, np. 29.09.2026.")
    dzien, miesiac, rok = (int(x) for x in m.groups())
    if rok < PIERWSZY_ROK:  # kalendarz dni wolnych nie obsługuje wcześniejszych lat; rok 0 to błąd datetime
        raise ValueError(f"Rok musi być {PIERWSZY_ROK} albo późniejszy. Sprawdź rok w potwierdzeniu odbioru.")
    if not 1 <= miesiac <= 12:
        raise ValueError("Miesiąc to liczba od 01 do 12. Wpisz datę jako dd.mm.rrrr.")
    ile = calendar.monthrange(rok, miesiac)[1]
    if not 1 <= dzien <= ile:
        raise ValueError(f"{MIESIACE[miesiac - 1]} {rok} ma {dni(ile)}. Sprawdź dzień w potwierdzeniu odbioru.")
    data = dt.date(rok, miesiac, dzien)
    if data > dzis:
        raise ValueError(f"Data jest z przyszłości. Wpisz dzień, w którym pismo odebrano — najpóźniej {data_pl(dzis)}.")
    return data


def polecenie(skill: str, klucz: str) -> str:
    """Polecenie dla Claude; klucz ze spacją w cudzysłowie.

    >>> polecenie("eskalacja", "sprawa-a"), polecenie("eskalacja", "podprojekt/sprawa b")
    ('/kruczek:eskalacja sprawa-a', "/kruczek:eskalacja 'podprojekt/sprawa b'")
    """
    return f"/kruczek:{skill} {shlex.quote(klucz)}"


def odswiez_index_w_sprawie(klucz: str) -> str:
    """Prośba do Claude o odświeżenie tabel index.md (nie ma na to osobnego polecenia /kruczek:).

    >>> odswiez_index_w_sprawie("sprawa-a")
    'Odśwież index.md w sprawie sprawa-a (teczka.py renderuj)'
    """
    return f"Odśwież index.md w sprawie {klucz} (teczka.py renderuj)"


def dalej_ze_sprawa(klucz: str) -> str:
    """
    >>> dalej_ze_sprawa("sprawa-a")
    'Dalej ze sprawą sprawa-a'
    """
    return f"Dalej ze sprawą {klucz}"
