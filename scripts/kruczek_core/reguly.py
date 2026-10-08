"""Reguły „zdarzenie → terminy i zadania” (spec §4.2).

Terminy są dwojakie: adresata (do kiedy ma odpowiedzieć na Twoje nadanie) i TWOJE (do kiedy
Ty musisz działać po piśmie, które doszło do Ciebie — np. odwołanie od decyzji). Przegapienie
własnego terminu bywa nieodwracalne, dlatego zadanie dostaje datę końca i wypływa na górę „Teraz”.

Reguły nie znają domyślnych terminów prawnych. Długość i podstawę terminu podaje
wywołujący (skill wie, jaki przepis stosuje) — kod niczego nie zgaduje.

Termin od nadania jest SZACUNKIEM: najwcześniejszy możliwy koniec, bo data doręczenia
nie jest jeszcze znana. Błąd w tę stronę jest bezpieczny (czekasz krócej). Po wpisaniu
doręczenia termin przelicza się od daty doręczenia.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.model import ZDARZENIA_PRZYCHODZACE, BladSprawy, Sprawa, Termin, Zadanie, Zdarzenie, kolejne_id
from kruczek_core.terminy import koniec_terminu

REGULA_DORECZENIE = "sprawdz-doreczenie"
REGULA_ODPOWIEDZ = "sprawdz-odpowiedz"
REGULA_ANALIZA = "przeanalizuj-odpowiedz"

_DZIEN = dt.timedelta(days=1)


@dataclass(frozen=True)
class SpecTerminu:
    dlugosc: str
    podstawa: str


def zastosuj(sprawa: Sprawa, zdarzenie: Zdarzenie, spec: SpecTerminu | None, kalendarz: Kalendarz) -> list[str]:
    if zdarzenie.typ == "nadanie":
        return _po_nadaniu(sprawa, zdarzenie, spec, kalendarz)
    if zdarzenie.typ == "doreczenie":
        return _po_doreczeniu(sprawa, zdarzenie, kalendarz)
    if zdarzenie.typ in ZDARZENIA_PRZYCHODZACE:
        return _po_przychodzacym(sprawa, zdarzenie, spec, kalendarz)
    return []


def _nowe_zadanie(sprawa: Sprawa, opis: str, aktywne_od: dt.date, watek: str | None, regula: str,
                  termin_id: str | None = None, termin: dt.date | None = None) -> Zadanie:
    zadanie = Zadanie(kolejne_id("a", sprawa.zadania), opis, aktywne_od, termin=termin, watek=watek,
                      regula=regula, termin_id=termin_id)
    sprawa.zadania.append(zadanie)
    return zadanie


def _otwarte(sprawa: Sprawa, watek: str | None, regula: str) -> list[Zadanie]:
    return [a for a in sprawa.zadania if a.watek == watek and a.regula == regula and a.zrobione is None]


def _po_nadaniu(sprawa: Sprawa, z: Zdarzenie, spec: SpecTerminu | None, kal: Kalendarz) -> list[str]:
    adresat = sprawa.znajdz_watek(z.watek).adresat if z.watek else "adresat"
    if spec is None:
        _nowe_zadanie(sprawa, "sprawdź datę doręczenia (EPO / Envelo)", z.data + _DZIEN, z.watek, REGULA_DORECZENIE)
        return ["nadanie bez terminu na odpowiedź — nie ma na co czekać; podaj --termin, jeśli pismo go wyznacza"]
    termin = Termin(kolejne_id("t", sprawa.terminy), spec.podstawa, z.id, spec.dlugosc,
                    koniec_terminu(z.data, spec.dlugosc, kal), watek=z.watek, szacunek=True)
    sprawa.terminy.append(termin)
    _nowe_zadanie(sprawa, "sprawdź datę doręczenia (EPO / Envelo)", z.data + _DZIEN, z.watek,
                  REGULA_DORECZENIE, termin.id)
    _nowe_zadanie(sprawa, f"sprawdź, czy {adresat} odpowiedział", termin.data_konca + _DZIEN, z.watek,
                  REGULA_ODPOWIEDZ, termin.id)
    return [f"termin {termin.id}: do {termin.data_konca.isoformat()} (szacunek — liczony od nadania)"]


def _po_doreczeniu(sprawa: Sprawa, z: Zdarzenie, kal: Kalendarz) -> list[str]:
    szacunkowe = [t for t in sprawa.terminy if t.watek == z.watek and t.szacunek and t.czyj == "adresata"]
    if not szacunkowe:
        return ["w wątku nie ma terminu liczonego od nadania — doręczenie zapisane bez przeliczania"]
    termin = szacunkowe[-1]
    nadanie = sprawa.znajdz_zdarzenie(termin.od_zdarzenia)
    if z.data < nadanie.data:
        raise BladSprawy(f"doręczenie {z.data} jest wcześniej niż nadanie {nadanie.data}")
    termin.od_zdarzenia = z.id
    termin.data_konca = koniec_terminu(z.data, termin.dlugosc, kal)
    termin.szacunek = False
    for a in sprawa.zadania:
        if a.termin_id == termin.id and a.zrobione is None:
            if a.regula == REGULA_DORECZENIE:
                a.zrobione = z.data
            elif a.regula == REGULA_ODPOWIEDZ:
                a.aktywne_od = termin.data_konca + _DZIEN
    return [f"termin {termin.id}: do {termin.data_konca.isoformat()} (od doręczenia)"]


def _po_przychodzacym(sprawa: Sprawa, z: Zdarzenie, spec: SpecTerminu | None, kal: Kalendarz) -> list[str]:
    """Pismo doszło do Ciebie (odpowiedź albo wpływ). Data zdarzenia = data doręczenia do
    Ciebie, także zastępczego (awizo). Ze `spec` liczy TWÓJ termin — nie szacunek, bo datę znasz."""
    for regula in (REGULA_ODPOWIEDZ, REGULA_DORECZENIE):
        for a in _otwarte(sprawa, z.watek, regula):
            a.zrobione = z.data
    adresat = sprawa.znajdz_watek(z.watek).adresat if z.watek else "nadawcy"
    co = "odpowiedź" if z.typ == "odpowiedz" else "pismo"
    if spec is None:
        zadanie = _nowe_zadanie(sprawa, f"przeanalizuj {co} od {adresat}", z.data, z.watek, REGULA_ANALIZA)
        return [f"zadanie {zadanie.id}: {zadanie.opis}"]
    termin = Termin(kolejne_id("t", sprawa.terminy), spec.podstawa, z.id, spec.dlugosc,
                    koniec_terminu(z.data, spec.dlugosc, kal), watek=z.watek, czyj="moj")
    sprawa.terminy.append(termin)
    zadanie = _nowe_zadanie(sprawa, f"przeanalizuj {co} od {adresat} i działaj", z.data, z.watek, REGULA_ANALIZA,
                            termin.id, termin.data_konca)
    return [f"Twój termin {termin.id}: do {termin.data_konca.isoformat()} ({spec.podstawa})",
            f"zadanie {zadanie.id}: {zadanie.opis}"]


def przelicz(sprawa: Sprawa, kalendarz: Kalendarz) -> list[str]:
    """Przelicz końce wszystkich terminów (np. po dodaniu dnia wolnego). Zwraca zmiany."""
    zmiany = []
    for t in sprawa.terminy:
        start = sprawa.znajdz_zdarzenie(t.od_zdarzenia).data
        nowy = koniec_terminu(start, t.dlugosc, kalendarz)
        if nowy == t.data_konca:
            continue
        zmiany.append(f"{t.id}: {t.data_konca.isoformat()} → {nowy.isoformat()}")
        t.data_konca = nowy
        for a in sprawa.zadania:
            if a.termin_id != t.id or a.zrobione is not None:
                continue
            if a.regula == REGULA_ODPOWIEDZ:
                a.aktywne_od = nowy + _DZIEN
            elif t.czyj == "moj":
                a.termin = nowy
    return zmiany
