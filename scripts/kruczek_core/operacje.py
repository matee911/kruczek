"""Operacje na teczce — jedyna droga zapisu dla CLI, strony i MCP.

Walidacja wejścia jest tutaj, nie w CLI: strona i MCP dostaną te same komunikaty.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from collections.abc import Sequence
from pathlib import Path

from kruczek_core.dni_wolne import PIERWSZY_ROK, Kalendarz
from kruczek_core.model import (
    TYPY_ZDARZEN,
    ZDARZENIA_PRZYCHODZACE,
    ZDARZENIA_WATKU,
    BladSprawy,
    Sprawa,
    Uczestnik,
    Watek,
    Zadanie,
    Zdarzenie,
    kolejne_id,
)
from kruczek_core.reguly import SpecTerminu, przelicz, zastosuj
from kruczek_core.repozytorium import zapisz_nowa, zmien
from kruczek_core.terminy import koniec_terminu, parsuj_dlugosc


def _niepusty(nazwa: str, wartosc: str) -> str:
    czysta = wartosc.strip()
    if not czysta:
        raise BladSprawy(f"{nazwa} nie może być pusty")
    return czysta


def _sprawdz_termin(termin: SpecTerminu, data: dt.date, kalendarz: Kalendarz) -> SpecTerminu:
    """Długość i podstawa muszą być poprawne, a koniec terminu w obsługiwanym zakresie dat."""
    podstawa = _niepusty("podstawa terminu", termin.podstawa)
    dlugosc = termin.dlugosc.strip()
    try:
        parsuj_dlugosc(dlugosc)
    except ValueError:
        raise BladSprawy(f"nieznana długość terminu {termin.dlugosc!r} — podaj np. 14d, 2t, 1m, 1r") from None
    try:
        koniec_terminu(data, dlugosc, kalendarz) + dt.timedelta(days=1)
    except (ValueError, OverflowError):
        raise BladSprawy(f"termin poza obsługiwanym zakresem dat (obsługiwane lata od {PIERWSZY_ROK}): "
                         f"{dlugosc} od {data}") from None
    return dataclasses.replace(termin, dlugosc=dlugosc, podstawa=podstawa)


def nowa_sprawa(katalog: Path, tytul: str, strona_przeciwna: str, wlasciciel: str) -> Sprawa:
    tytul = _niepusty("tytuł", tytul)
    strona_przeciwna = _niepusty("strona przeciwna", strona_przeciwna)
    wlasciciel = _niepusty("właściciel", wlasciciel)
    sprawa = Sprawa(id=uuid.uuid4().hex, tytul=tytul, wlasciciel=wlasciciel, strona_przeciwna=strona_przeciwna,
                    uczestnicy=[Uczestnik(wlasciciel, "opiekun")])
    zapisz_nowa(katalog, sprawa)
    return sprawa


def dodaj_watek(katalog: Path, id: str, adresat: str) -> None:
    id = _niepusty("id wątku", id)
    adresat = _niepusty("adresat", adresat)

    def zmiana(s: Sprawa) -> None:
        if any(w.id == id for w in s.watki):
            raise BladSprawy(f"wątek {id!r} już istnieje")
        s.watki.append(Watek(id, adresat))

    zmien(katalog, zmiana)


def dodaj_zdarzenie(katalog: Path, typ: str, data: dt.date, kalendarz: Kalendarz, dzis: dt.date, *,
                    watek: str | None = None, opis: str = "", dowody: Sequence[str] = (),
                    termin: SpecTerminu | None = None, dotyczy: str | None = None) -> list[str]:
    if typ not in TYPY_ZDARZEN:
        raise BladSprawy(f"nieznany typ zdarzenia {typ!r}; dozwolone: {', '.join(TYPY_ZDARZEN)}")
    if data > dzis:
        raise BladSprawy(f"data zdarzenia {data} jest w przyszłości — przyszłe rzeczy zapisz jako zadanie")
    if typ in ZDARZENIA_WATKU and watek is None:
        raise BladSprawy(f"zdarzenie {typ!r} wymaga wątku")
    if termin is not None and typ not in ("nadanie", *ZDARZENIA_PRZYCHODZACE):
        raise BladSprawy("termin podaje się przy nadaniu (termin adresata) albo przy odpowiedzi/wpływie (Twój termin)")
    if termin is not None:
        termin = _sprawdz_termin(termin, data, kalendarz)
    if dotyczy is not None:
        dotyczy = _niepusty("dotyczy", dotyczy)

    def zmiana(s: Sprawa) -> list[str]:
        if watek is not None:
            s.znajdz_watek(watek)
        z = Zdarzenie(kolejne_id("z", s.zdarzenia), data, typ, opis, watek, list(dowody))
        s.zdarzenia.append(z)
        return [f"zdarzenie {z.id}: {typ} {data.isoformat()}", *zastosuj(s, z, termin, kalendarz, dotyczy=dotyczy)]

    return zmien(katalog, zmiana)


def dodaj_zadanie(katalog: Path, opis: str, aktywne_od: dt.date, *, termin: dt.date | None = None,
                  watek: str | None = None) -> Zadanie:
    opis = _niepusty("opis", opis)
    if termin is not None and termin < aktywne_od:
        raise BladSprawy(f"termin zadania {termin} jest wcześniej niż aktywne od {aktywne_od}")

    def zmiana(s: Sprawa) -> Zadanie:
        if watek is not None:
            s.znajdz_watek(watek)
        zadanie = Zadanie(kolejne_id("a", s.zadania), opis, aktywne_od, termin=termin, watek=watek)
        s.zadania.append(zadanie)
        return zadanie

    return zmien(katalog, zmiana)


def oznacz_zrobione(katalog: Path, zadanie_id: str, dzis: dt.date) -> Zadanie:
    def zmiana(s: Sprawa) -> Zadanie:
        zadanie = s.znajdz_zadanie(zadanie_id)
        if zadanie.zrobione is not None:
            raise BladSprawy(f"zadanie {zadanie_id} już zrobione ({zadanie.zrobione})")
        zadanie.zrobione = dzis
        return zadanie

    return zmien(katalog, zmiana)


def przelicz_sprawe(katalog: Path, kalendarz: Kalendarz) -> list[str]:
    return zmien(katalog, lambda s: przelicz(s, kalendarz))
