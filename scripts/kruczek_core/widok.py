"""Przegląd „co robić” — wyliczany, nie zapisywany.

Actionable = zadania z aktywne_od ≤ dziś i niezrobione. Piłka w wątku wynika z OTWARTYCH
zadań reguł, nie z ostatniego zdarzenia: jeśli w wątku jest otwarte zadanie sprawdzenia
odpowiedzi albo doręczenia, piłka jest u adresata; w przeciwnym razie u mnie. „Czekam do”
to najwcześniejszy termin adresata, którego zadanie odpowiedzi jest jeszcze otwarte.
„Czekam” bierze tylko terminy adresata; Twoje terminy są datą zadania w „Teraz”.
„Po terminie” liczy jedna funkcja dla CLI i strony: zadanie z własnym terminem po jego dacie,
a sprawdzenie odpowiedzi — po końcu terminu adresata (wtedy właśnie staje się aktywne).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from kruczek_core.model import Sprawa, Termin, Watek, Zadanie
from kruczek_core.reguly import (
    REGULA_DORECZENIE,
    REGULA_ODPOWIEDZ,
    REGULA_START,
    REGULA_START_NADANIE,
)

DNI_BEZ_RUCHU = 30


@dataclass(frozen=True)
class StanWatku:
    sprawa: str
    watek: Watek
    pilka: str  # "moja" | "adresata"
    czekam_do: dt.date | None
    szacunek: bool
    sprawa_id: str = ""
    klucz: str = ""


@dataclass(frozen=True)
class PozycjaZadania:
    sprawa: str
    zadanie: Zadanie
    sprawa_id: str = ""
    klucz: str = ""
    termin_sprawy: Termin | None = None  # termin, z którego wynika zadanie (Zadanie.termin_id)
    termin_konca: dt.date | None = None  # do kiedy — patrz termin_zadania
    po_terminie: int = 0  # ile dni po terminie_konca; 0 = nie po terminie


@dataclass(frozen=True)
class BezRuchu:
    sprawa: str
    sprawa_id: str
    ostatni_ruch: dt.date | None
    klucz: str = ""


@dataclass(frozen=True)
class Przeglad:
    teraz: list[PozycjaZadania]
    czekam: list[StanWatku]
    wkrotce: list[PozycjaZadania]
    bez_ruchu: list[BezRuchu] = field(default_factory=list)


def termin_zadania(sprawa: Sprawa, zadanie: Zadanie) -> dt.date | None:
    """Do kiedy zadanie trzeba zrobić: jego własny termin, a dla sprawdzenia odpowiedzi —
    koniec terminu adresata (zadanie staje się aktywne dzień po nim)."""
    if zadanie.termin is not None:
        return zadanie.termin
    if zadanie.regula == REGULA_ODPOWIEDZ and zadanie.termin_id is not None:
        termin = _termin(sprawa, zadanie.termin_id)
        return termin.data_konca if termin is not None else None
    return None


def dni_po_terminie(termin: dt.date | None, dzis: dt.date) -> int:
    """Ile dni minęło od terminu; 0, gdy termin jest dziś, w przyszłości albo go nie ma.

    >>> d = dt.date
    >>> dni_po_terminie(d(2026, 10, 13), d(2026, 10, 14)), dni_po_terminie(d(2026, 10, 14), d(2026, 10, 14))
    (1, 0)
    >>> dni_po_terminie(None, d(2026, 10, 14))
    0
    """
    if termin is None or termin >= dzis:
        return 0
    return (dzis - termin).days


def _termin(sprawa: Sprawa, termin_id: str | None) -> Termin | None:
    return next((t for t in sprawa.terminy if t.id == termin_id), None) if termin_id else None


def _pozycja(s: Sprawa, a: Zadanie, klucz: str, dzis: dt.date) -> PozycjaZadania:
    koniec = termin_zadania(s, a)
    return PozycjaZadania(s.tytul, a, s.id, klucz, _termin(s, a.termin_id), koniec, dni_po_terminie(koniec, dzis))


def stan_watku(sprawa: Sprawa, watek_id: str, klucz: str = "") -> StanWatku:
    watek = sprawa.znajdz_watek(watek_id)
    otwarte = [a for a in sprawa.zadania if a.watek == watek_id and a.zrobione is None]
    if not any(a.regula in (REGULA_ODPOWIEDZ, REGULA_DORECZENIE) for a in otwarte):
        return StanWatku(sprawa.tytul, watek, "moja", None, False, sprawa.id, klucz)
    czekajace = [
        t for t in sprawa.terminy
        if t.watek == watek_id and t.czyj == "adresata"
        and any(a.termin_id == t.id and a.regula == REGULA_ODPOWIEDZ for a in otwarte)
    ]
    if not czekajace:
        return StanWatku(sprawa.tytul, watek, "adresata", None, False, sprawa.id, klucz)
    najblizszy = min(czekajace, key=lambda t: t.data_konca)
    return StanWatku(sprawa.tytul, watek, "adresata", najblizszy.data_konca, najblizszy.szacunek, sprawa.id, klucz)


def co_robic(sprawy: Sequence[tuple[str, Sprawa]], dzis: dt.date, horyzont_dni: int = 14,
             bez_ruchu_dni: int = DNI_BEZ_RUCHU) -> Przeglad:
    granica = dzis + dt.timedelta(days=horyzont_dni)
    teraz, wkrotce, czekam, bez_ruchu = [], [], [], []
    for klucz, s in sprawy:
        if s.zamknieta:
            continue
        for a in s.zadania:
            if a.zrobione is not None:
                continue
            if a.aktywne_od <= dzis:
                teraz.append(_pozycja(s, a, klucz, dzis))
            elif a.aktywne_od <= granica:
                wkrotce.append(_pozycja(s, a, klucz, dzis))
        czeka = [st for w in s.watki if (st := stan_watku(s, w.id, klucz)).pilka == "adresata"]
        czekam += czeka
        if not czeka and all(a.zrobione is not None for a in s.zadania):
            ostatni = max((z.data for z in s.zdarzenia), default=None)
            if ostatni is None or (dzis - ostatni).days > bez_ruchu_dni:
                bez_ruchu.append(BezRuchu(s.tytul, s.id, ostatni, klucz))
    teraz.sort(key=lambda p: (p.zadanie.termin or dt.date.max, p.zadanie.aktywne_od, p.sprawa, p.klucz))
    wkrotce.sort(key=lambda p: (p.zadanie.aktywne_od, p.sprawa, p.klucz))
    czekam.sort(key=lambda st: (st.czekam_do or dt.date.max, st.sprawa, st.klucz))
    bez_ruchu.sort(key=lambda b: (b.ostatni_ruch is not None, b.ostatni_ruch or dt.date.min, b.sprawa, b.klucz))
    return Przeglad(teraz, czekam, wkrotce, bez_ruchu)


KROKI_STARTOWE = (REGULA_START, REGULA_START_NADANIE)


@dataclass(frozen=True)
class KrokiStartowe:
    """Sześć kroków startowych jednej sprawy jako jedna pozycja (zrobione i otwarte, w kolejności dodania)."""
    sprawa: str
    klucz: str
    kroki: list[Zadanie]

    @property
    def zrobione(self) -> int:
        return sum(1 for a in self.kroki if a.zrobione is not None)


@dataclass(frozen=True)
class Sekcje:
    """Przegląd w kolejności ekranu: PO TERMINIE, TERAZ, CZEKAM, WKRÓTCE, BEZ RUCHU."""
    po_terminie: list[PozycjaZadania]
    teraz: list[PozycjaZadania | KrokiStartowe]
    czekam: list[StanWatku]
    wkrotce: list[PozycjaZadania | KrokiStartowe]
    bez_ruchu: list[BezRuchu]


def _zwin_kroki(pozycje: list[PozycjaZadania], sprawy: Mapping[str, Sprawa]) -> list[PozycjaZadania | KrokiStartowe]:
    wynik: list[PozycjaZadania | KrokiStartowe] = []
    zwiniete: set[str] = set()
    for p in pozycje:
        if p.zadanie.regula not in KROKI_STARTOWE:
            wynik.append(p)
        elif p.klucz not in zwiniete:
            zwiniete.add(p.klucz)
            kroki = [a for a in sprawy[p.klucz].zadania if a.regula in KROKI_STARTOWE]
            wynik.append(KrokiStartowe(p.sprawa, p.klucz, kroki))
    return wynik


def sekcje(przeglad: Przeglad, sprawy: Mapping[str, Sprawa], dzis: dt.date) -> Sekcje:
    """Zadanie po terminie (także sprawdzenie odpowiedzi po terminie adresata) idzie do PO TERMINIE,
    a wątek, którego termin minął, znika z CZEKAM — piłka wróciła do nas. Kroki startowe sprawy
    zwijają się w jedną pozycję w miejscu pierwszego otwartego kroku."""
    return Sekcje(
        [p for p in przeglad.teraz if p.po_terminie],
        _zwin_kroki([p for p in przeglad.teraz if not p.po_terminie], sprawy),
        [c for c in przeglad.czekam if not dni_po_terminie(c.czekam_do, dzis)],
        _zwin_kroki(przeglad.wkrotce, sprawy),
        list(przeglad.bez_ruchu),
    )
