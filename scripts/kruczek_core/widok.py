"""Przegląd „co robić” — wyliczany, nie zapisywany.

Actionable = zadania z aktywne_od ≤ dziś i niezrobione. Piłka w wątku wynika z OTWARTYCH
zadań reguł, nie z ostatniego zdarzenia: jeśli w wątku jest otwarte zadanie sprawdzenia
odpowiedzi albo doręczenia, piłka jest u adresata; w przeciwnym razie u mnie. „Czekam do”
to najwcześniejszy termin adresata, którego zadanie odpowiedzi jest jeszcze otwarte.
„Czekam” bierze tylko terminy adresata; Twoje terminy są datą zadania w „Teraz”.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from kruczek_core.model import Sprawa, Watek, Zadanie
from kruczek_core.reguly import REGULA_DORECZENIE, REGULA_ODPOWIEDZ

DNI_BEZ_RUCHU = 30


@dataclass(frozen=True)
class StanWatku:
    sprawa: str
    watek: Watek
    pilka: str  # "moja" | "adresata"
    czekam_do: dt.date | None
    szacunek: bool
    sprawa_id: str = ""


@dataclass(frozen=True)
class PozycjaZadania:
    sprawa: str
    zadanie: Zadanie
    sprawa_id: str = ""


@dataclass(frozen=True)
class BezRuchu:
    sprawa: str
    sprawa_id: str
    ostatni_ruch: dt.date | None


@dataclass(frozen=True)
class Przeglad:
    teraz: list[PozycjaZadania]
    czekam: list[StanWatku]
    wkrotce: list[PozycjaZadania]
    bez_ruchu: list[BezRuchu] = field(default_factory=list)


def stan_watku(sprawa: Sprawa, watek_id: str) -> StanWatku:
    watek = sprawa.znajdz_watek(watek_id)
    otwarte = [a for a in sprawa.zadania if a.watek == watek_id and a.zrobione is None]
    if not any(a.regula in (REGULA_ODPOWIEDZ, REGULA_DORECZENIE) for a in otwarte):
        return StanWatku(sprawa.tytul, watek, "moja", None, False, sprawa.id)
    czekajace = [
        t for t in sprawa.terminy
        if t.watek == watek_id and t.czyj == "adresata"
        and any(a.termin_id == t.id and a.regula == REGULA_ODPOWIEDZ for a in otwarte)
    ]
    if not czekajace:
        return StanWatku(sprawa.tytul, watek, "adresata", None, False, sprawa.id)
    najblizszy = min(czekajace, key=lambda t: t.data_konca)
    return StanWatku(sprawa.tytul, watek, "adresata", najblizszy.data_konca, najblizszy.szacunek, sprawa.id)


def co_robic(sprawy: list[Sprawa], dzis: dt.date, horyzont_dni: int = 14,
             bez_ruchu_dni: int = DNI_BEZ_RUCHU) -> Przeglad:
    granica = dzis + dt.timedelta(days=horyzont_dni)
    teraz, wkrotce, czekam, bez_ruchu = [], [], [], []
    for s in sprawy:
        if s.zamknieta:
            continue
        for a in s.zadania:
            if a.zrobione is not None:
                continue
            if a.aktywne_od <= dzis:
                teraz.append(PozycjaZadania(s.tytul, a, s.id))
            elif a.aktywne_od <= granica:
                wkrotce.append(PozycjaZadania(s.tytul, a, s.id))
        czeka = [st for w in s.watki if (st := stan_watku(s, w.id)).pilka == "adresata"]
        czekam += czeka
        if not czeka and all(a.zrobione is not None for a in s.zadania):
            ostatni = max((z.data for z in s.zdarzenia), default=None)
            if ostatni is None or (dzis - ostatni).days > bez_ruchu_dni:
                bez_ruchu.append(BezRuchu(s.tytul, s.id, ostatni))
    teraz.sort(key=lambda p: (p.zadanie.termin or dt.date.max, p.zadanie.aktywne_od, p.sprawa))
    wkrotce.sort(key=lambda p: (p.zadanie.aktywne_od, p.sprawa))
    czekam.sort(key=lambda st: (st.czekam_do or dt.date.max, st.sprawa))
    bez_ruchu.sort(key=lambda b: (b.ostatni_ruch is not None, b.ostatni_ruch or dt.date.min, b.sprawa))
    return Przeglad(teraz, czekam, wkrotce, bez_ruchu)
