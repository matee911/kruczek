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
    WYNIKI_SPRAWY,
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


def utworz_sprawe(tytul: str, strona_przeciwna: str, wlasciciel: str) -> Sprawa:
    """Nowa sprawa w pamięci (bez zapisu): walidacja, stałe id, właściciel jako opiekun."""
    tytul = _niepusty("tytuł", tytul)
    strona_przeciwna = _niepusty("strona przeciwna", strona_przeciwna)
    wlasciciel = _niepusty("właściciel", wlasciciel)
    return Sprawa(id=uuid.uuid4().hex, tytul=tytul, wlasciciel=wlasciciel, strona_przeciwna=strona_przeciwna,
                  uczestnicy=[Uczestnik(wlasciciel, "opiekun")])


def nowa_sprawa(katalog: Path, tytul: str, strona_przeciwna: str, wlasciciel: str) -> Sprawa:
    sprawa = utworz_sprawe(tytul, strona_przeciwna, wlasciciel)
    zapisz_nowa(katalog, sprawa)
    return sprawa


def dopisz_watek(s: Sprawa, id: str, adresat: str) -> Watek:
    id = _niepusty("id wątku", id)
    adresat = _niepusty("adresat", adresat)
    if any(w.id == id for w in s.watki):
        raise BladSprawy(f"wątek {id!r} już istnieje")
    watek = Watek(id, adresat)
    s.watki.append(watek)
    return watek


def dodaj_watek(katalog: Path, id: str, adresat: str) -> None:
    zmien(katalog, lambda s: dopisz_watek(s, id, adresat))


def dopisz_zdarzenie(s: Sprawa, typ: str, data: dt.date, kalendarz: Kalendarz, dzis: dt.date, *,
                     watek: str | None = None, opis: str = "", dowody: Sequence[str] = (),
                     termin: SpecTerminu | None = None, dotyczy: str | None = None) -> list[str]:
    """Dopisuje zdarzenie do sprawy w pamięci i stosuje reguły. Błąd = sprawa bez zmian
    (walidacja przed pierwszą mutacją; reguły walidują przed swoją)."""
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
    if watek is not None:
        s.znajdz_watek(watek)
    z = Zdarzenie(kolejne_id("z", s.zdarzenia), data, typ, opis, watek, list(dowody))
    s.zdarzenia.append(z)
    try:
        return [f"zdarzenie {z.id}: {typ} {data.isoformat()}", *zastosuj(s, z, termin, kalendarz, dotyczy=dotyczy)]
    except BladSprawy:
        s.zdarzenia.remove(z)
        raise


def dodaj_zdarzenie(katalog: Path, typ: str, data: dt.date, kalendarz: Kalendarz, dzis: dt.date, *,
                    watek: str | None = None, opis: str = "", dowody: Sequence[str] = (),
                    termin: SpecTerminu | None = None, dotyczy: str | None = None) -> list[str]:
    return zmien(katalog, lambda s: dopisz_zdarzenie(s, typ, data, kalendarz, dzis, watek=watek, opis=opis,
                                                     dowody=dowody, termin=termin, dotyczy=dotyczy))


def dopisz_zadanie(s: Sprawa, opis: str, aktywne_od: dt.date, *, termin: dt.date | None = None,
                   watek: str | None = None) -> Zadanie:
    opis = _niepusty("opis", opis)
    if termin is not None and termin < aktywne_od:
        raise BladSprawy(f"termin zadania {termin} jest wcześniej niż aktywne od {aktywne_od}")
    if watek is not None:
        s.znajdz_watek(watek)
    zadanie = Zadanie(kolejne_id("a", s.zadania), opis, aktywne_od, termin=termin, watek=watek)
    s.zadania.append(zadanie)
    return zadanie


def dodaj_zadanie(katalog: Path, opis: str, aktywne_od: dt.date, *, termin: dt.date | None = None,
                  watek: str | None = None) -> Zadanie:
    return zmien(katalog, lambda s: dopisz_zadanie(s, opis, aktywne_od, termin=termin, watek=watek))


def zamknij_sprawe(katalog: Path, wynik: str) -> None:
    if wynik not in WYNIKI_SPRAWY:
        raise BladSprawy(f"nieznany wynik {wynik!r}; dozwolone: {', '.join(WYNIKI_SPRAWY)}")

    def zmiana(s: Sprawa) -> None:
        if s.zamknieta:
            raise BladSprawy(f"sprawa już zamknięta ({s.wynik})")
        s.zamknieta, s.wynik = True, wynik

    zmien(katalog, zmiana)


def otworz_sprawe(katalog: Path) -> None:
    def zmiana(s: Sprawa) -> None:
        s.zamknieta, s.wynik = False, None

    zmien(katalog, zmiana)


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
