"""Koniec terminu — art. 111, 112, 115 k.c.; art. 57 § 1–4 k.p.a.; art. 165 § 1 k.p.c.
(odsyła do prawa cywilnego). Stan sprawdzony w tekstach jednolitych ELI 2026-10-08.

k.c. i k.p.a. różnią się tylko dla lat, gdy dnia brak (29 lutego): k.c. bierze ostatni
dzień miesiąca, k.p.a. dzień go poprzedzający — oba to 28 lutego. Dlatego nie ma osobnego
„reżimu”: jedna funkcja liczy dla wszystkich trzech ustaw.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re

from kruczek_core.dni_wolne import Kalendarz

_DLUGOSC = re.compile(r"^(\d+)([dtmr])$")


def parsuj_dlugosc(tekst: str) -> tuple[int, str]:
    """'14d' → (14, 'd'). Jednostki: d — dni, t — tygodnie, m — miesiące, r — lata.

    >>> parsuj_dlugosc("14d")
    (14, 'd')
    >>> parsuj_dlugosc("1m")
    (1, 'm')
    """
    m = _DLUGOSC.match(tekst.strip())
    if not m or int(m.group(1)) == 0:
        raise ValueError(f"nieznana długość terminu: {tekst!r} (np. 14d, 2t, 1m, 1r)")
    return int(m.group(1)), m.group(2)


def _dodaj_miesiace(d: dt.date, n: int) -> dt.date:
    """Ten sam dzień miesiąca, a gdy go brak — ostatni dzień miesiąca (art. 112 k.c.).

    >>> _dodaj_miesiace(dt.date(2026, 1, 31), 1)
    datetime.date(2026, 2, 28)
    """
    rok, miesiac = divmod(d.month - 1 + n, 12)
    rok += d.year
    miesiac += 1
    return dt.date(rok, miesiac, min(d.day, calendar.monthrange(rok, miesiac)[1]))


def koniec_nominalny(start: dt.date, dlugosc: str) -> dt.date:
    """Koniec przed przesunięciem z soboty/dnia wolnego. Dnia zdarzenia nie liczy się
    (art. 111 § 2 k.c.), więc 14 dni od 8.10 to 22.10."""
    n, jednostka = parsuj_dlugosc(dlugosc)
    if jednostka == "d":
        return start + dt.timedelta(days=n)
    if jednostka == "t":
        return start + dt.timedelta(weeks=n)
    if jednostka == "m":
        return _dodaj_miesiace(start, n)
    return _dodaj_miesiace(start, 12 * n)


def koniec_terminu(start: dt.date, dlugosc: str, kalendarz: Kalendarz) -> dt.date:
    """Koniec terminu po przesunięciu na pierwszy dzień niebędący sobotą ani dniem wolnym."""
    d = koniec_nominalny(start, dlugosc)
    while kalendarz.czy_przesuwa(d):
        d += dt.timedelta(days=1)
    return d
