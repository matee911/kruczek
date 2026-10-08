"""Przegląd „co robić” — wyliczany, nie zapisywany (spec §4.2).

Actionable = zadania z aktywne_od ≤ dziś i niezrobione. Piłka w wątku wynika
z ostatniego zdarzenia korespondencji: nadanie/doręczenie → u adresata, odpowiedź/wpływ → moja.
„Czekam” bierze tylko terminy adresata; Twoje terminy są datą zadania w „Teraz”.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from kruczek_core.model import ZDARZENIA_PRZYCHODZACE, ZDARZENIA_WATKU, Sprawa, Watek, Zadanie


@dataclass(frozen=True)
class StanWatku:
    sprawa: str
    watek: Watek
    pilka: str  # "moja" | "adresata"
    czekam_do: dt.date | None
    szacunek: bool


@dataclass(frozen=True)
class PozycjaZadania:
    sprawa: str
    zadanie: Zadanie


@dataclass(frozen=True)
class Przeglad:
    teraz: list[PozycjaZadania]
    czekam: list[StanWatku]
    wkrotce: list[PozycjaZadania]


def stan_watku(sprawa: Sprawa, watek_id: str) -> StanWatku:
    watek = sprawa.znajdz_watek(watek_id)
    korespondencja = sorted(
        (z for z in sprawa.zdarzenia if z.watek == watek_id and z.typ in ZDARZENIA_WATKU),
        key=lambda z: z.data,
    )
    ostatnie = korespondencja[-1] if korespondencja else None
    if ostatnie is None or ostatnie.typ in ZDARZENIA_PRZYCHODZACE:
        return StanWatku(sprawa.tytul, watek, "moja", None, False)
    terminy = [t for t in sprawa.terminy if t.watek == watek_id and t.czyj == "adresata"]
    if not terminy:
        return StanWatku(sprawa.tytul, watek, "adresata", None, False)
    return StanWatku(sprawa.tytul, watek, "adresata", terminy[-1].data_konca, terminy[-1].szacunek)


def co_robic(sprawy: list[Sprawa], dzis: dt.date, horyzont_dni: int = 14) -> Przeglad:
    granica = dzis + dt.timedelta(days=horyzont_dni)
    teraz, wkrotce, czekam = [], [], []
    for s in sprawy:
        if s.zamknieta:
            continue
        for a in s.zadania:
            if a.zrobione is not None:
                continue
            if a.aktywne_od <= dzis:
                teraz.append(PozycjaZadania(s.tytul, a))
            elif a.aktywne_od <= granica:
                wkrotce.append(PozycjaZadania(s.tytul, a))
        czekam += [st for w in s.watki if (st := stan_watku(s, w.id)).pilka == "adresata"]
    teraz.sort(key=lambda p: (p.zadanie.termin or dt.date.max, p.zadanie.aktywne_od, p.sprawa))
    wkrotce.sort(key=lambda p: (p.zadanie.aktywne_od, p.sprawa))
    czekam.sort(key=lambda st: (st.czekam_do or dt.date.max, st.sprawa))
    return Przeglad(teraz, czekam, wkrotce)
