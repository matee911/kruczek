"""Model danych sprawy — źródło prawdy w sprawa.json (spec §4).

Status sprawy i wątku NIE jest tu zapisany: wylicza go widok.py ze zdarzeń, terminów
i zadań, żeby nie rozjeżdżał się z rzeczywistością.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1

# odpowiedz — odpowiedź na Twoje pismo; wplyw — inne pismo, które doszło do Ciebie
# (decyzja, wezwanie, nakaz). Oba to korespondencja przychodząca.
TYPY_ZDARZEN = ("nadanie", "doreczenie", "odpowiedz", "wplyw", "fakt", "telefon", "inne")
# Zdarzenia, które zawsze dotyczą korespondencji z konkretnym podmiotem.
ZDARZENIA_WATKU = ("nadanie", "doreczenie", "odpowiedz", "wplyw")
ZDARZENIA_PRZYCHODZACE = ("odpowiedz", "wplyw")


class BladSprawy(Exception):
    """Błąd z komunikatem dla użytkownika — CLI wypisuje go bez tracebacku."""


@dataclass
class Uczestnik:
    osoba: str
    rola: str  # "opiekun" | "klientka"


@dataclass
class Watek:
    id: str
    adresat: str


@dataclass
class Pismo:
    id: str
    watek: str
    wersja: int
    stan: str  # "szkic" | "recenzja" | "wyslane"
    plik: str | None = None


@dataclass
class Zdarzenie:
    id: str
    data: dt.date
    typ: str
    opis: str = ""
    watek: str | None = None
    dowody: list[str] = field(default_factory=list)


@dataclass
class Termin:
    id: str
    podstawa: str
    od_zdarzenia: str
    dlugosc: str
    data_konca: dt.date
    watek: str | None = None
    szacunek: bool = False
    # "adresata" — do kiedy adresat ma odpowiedzieć na Twoje pismo;
    # "moj" — do kiedy Ty musisz działać (np. odwołanie od decyzji, która do Ciebie doszła)
    czyj: str = "adresata"


@dataclass
class Zadanie:
    id: str
    opis: str
    aktywne_od: dt.date
    termin: dt.date | None = None
    watek: str | None = None
    regula: str | None = None  # reguła, która utworzyła zadanie; None = ręczne
    termin_id: str | None = None
    zrobione: dt.date | None = None


@dataclass
class Dowod:
    sciezka: str
    sha256: str
    dodano: dt.date
    wrazliwy: bool = True  # domyślnie nie opuszcza maszyny opiekuna (spec §3)
    do_udostepnienia: bool = False


@dataclass
class Sprawa:
    id: str
    tytul: str
    wlasciciel: str
    strona_przeciwna: str
    schema_version: int = SCHEMA_VERSION
    rewizja: int = 0
    zamknieta: bool = False
    wynik: str | None = None
    uczestnicy: list[Uczestnik] = field(default_factory=list)
    watki: list[Watek] = field(default_factory=list)
    pisma: list[Pismo] = field(default_factory=list)
    zdarzenia: list[Zdarzenie] = field(default_factory=list)
    terminy: list[Termin] = field(default_factory=list)
    zadania: list[Zadanie] = field(default_factory=list)
    dowody: list[Dowod] = field(default_factory=list)

    def znajdz_watek(self, id: str) -> Watek:
        return _znajdz(self.watki, id, "wątku")

    def znajdz_zadanie(self, id: str) -> Zadanie:
        return _znajdz(self.zadania, id, "zadania")

    def znajdz_zdarzenie(self, id: str) -> Zdarzenie:
        return _znajdz(self.zdarzenia, id, "zdarzenia")


def _znajdz(elementy: list[Any], id: str, co: str) -> Any:
    for e in elementy:
        if e.id == id:
            return e
    znane = ", ".join(e.id for e in elementy) or "brak"
    raise BladSprawy(f"w sprawie nie ma {co} {id!r} (znane: {znane})")


def kolejne_id(prefiks: str, elementy: Iterable[Any]) -> str:
    """Następne id z prefiksem: najwyższy numer + 1.

    >>> kolejne_id("z", [])
    'z1'
    """
    numery = [
        int(e.id[len(prefiks):])
        for e in elementy
        if e.id.startswith(prefiks) and e.id[len(prefiks):].isdigit()
    ]
    return f"{prefiks}{max(numery, default=0) + 1}"


def _na_tekst(o: Any) -> Any:
    if isinstance(o, dt.date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _na_tekst(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_na_tekst(v) for v in o]
    return o


def do_slownika(sprawa: Sprawa) -> dict[str, Any]:
    return _na_tekst(asdict(sprawa))


def _data(tekst: str | None) -> dt.date | None:
    return None if tekst is None else dt.date.fromisoformat(tekst)


def z_slownika(d: dict[str, Any]) -> Sprawa:
    """Odwrotność do_slownika. Nieznany klucz albo zła data → TypeError/ValueError/KeyError
    (repozytorium zamienia je na BladSprawy z nazwą pliku)."""
    return Sprawa(
        id=d["id"],
        tytul=d["tytul"],
        wlasciciel=d["wlasciciel"],
        strona_przeciwna=d["strona_przeciwna"],
        schema_version=d["schema_version"],
        rewizja=d["rewizja"],
        zamknieta=d.get("zamknieta", False),
        wynik=d.get("wynik"),
        uczestnicy=[Uczestnik(**u) for u in d.get("uczestnicy", [])],
        watki=[Watek(**w) for w in d.get("watki", [])],
        pisma=[Pismo(**p) for p in d.get("pisma", [])],
        zdarzenia=[Zdarzenie(**{**z, "data": _data(z["data"])}) for z in d.get("zdarzenia", [])],
        terminy=[Termin(**{**t, "data_konca": _data(t["data_konca"])}) for t in d.get("terminy", [])],
        zadania=[
            Zadanie(
                **{
                    **a,
                    "aktywne_od": _data(a["aktywne_od"]),
                    "termin": _data(a.get("termin")),
                    "zrobione": _data(a.get("zrobione")),
                }
            )
            for a in d.get("zadania", [])
        ],
        dowody=[Dowod(**{**w, "dodano": _data(w["dodano"])}) for w in d.get("dowody", [])],
    )
