"""Model danych sprawy — źródło prawdy w sprawa.json.

Status sprawy i wątku NIE jest tu zapisany: wylicza go widok.py ze zdarzeń, terminów
i zadań, żeby nie rozjeżdżał się z rzeczywistością.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 2

# odpowiedz — odpowiedź na Twoje pismo; wplyw — inne pismo, które doszło do Ciebie
# (decyzja, wezwanie, nakaz). Oba to korespondencja przychodząca.
TYPY_ZDARZEN = ("nadanie", "doreczenie", "odpowiedz", "wplyw", "fakt", "telefon", "inne")
# Zdarzenia, które zawsze dotyczą korespondencji z konkretnym podmiotem.
ZDARZENIA_WATKU = ("nadanie", "doreczenie", "odpowiedz", "wplyw")
ZDARZENIA_PRZYCHODZACE = ("odpowiedz", "wplyw")
CZYJ_TERMINU = ("adresata", "moj")
ROLE_UCZESTNIKOW = ("opiekun", "klientka")
STANY_PISMA = ("szkic", "recenzja", "wyslane")
WYNIKI_SPRAWY = ("wygrana", "ugoda", "porzucona")
PEWNOSCI = ("dowod", "poszlaka", "wlasne_oswiadczenie")
_GODZINA = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class BladSprawy(Exception):
    """Błąd z komunikatem dla użytkownika — CLI wypisuje go bez tracebacku."""


class ZdarzeniePrzedNadaniem(BladSprawy):
    """Doręczenie albo pismo przychodzące datowane przed nadaniem, którego dotyczy — strona pokazuje to jako błąd pola."""

    def __init__(self, komunikat: str, data_nadania: dt.date) -> None:
        super().__init__(komunikat)
        self.data_nadania = data_nadania


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
    godzina: str | None = None  # "GG:MM" — przy mailach i telefonach rozstrzyga kolejność
    pewnosc: str | None = None  # "dowod" | "poszlaka" | "wlasne_oswiadczenie"; None = nie oceniano
    dotyczy: str | None = None  # id nadania, którego dotyczy doręczenie/odpowiedź/wpływ (ustawiają reguły)


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
    zdarzenie_id: str | None = None  # id zdarzenia, które utworzyło zadanie (reguły); None = ręczne
    zamkniete_przez: str | None = None  # id zdarzenia, które zamknęło zadanie (reguły); None = ręcznie albo otwarte


@dataclass
class Dowod:
    sciezka: str
    sha256: str
    dodano: dt.date
    wrazliwy: bool = True  # domyślnie nie opuszcza maszyny opiekuna
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


def chronologia(s: Sprawa) -> list[Zdarzenie]:
    """Zdarzenia po dacie, godzinie i kolejności wpisu (zdarzenie bez godziny przed tym z godziną)."""
    kolejnosc = {id(z): i for i, z in enumerate(s.zdarzenia)}
    return sorted(s.zdarzenia, key=lambda z: (z.data, z.godzina or "", kolejnosc[id(z)]))


def _znajdz(elementy: list[Any], id: str, co: str) -> Any:
    for e in elementy:
        if e.id == id:
            return e
    znane = ", ".join(e.id for e in elementy) or "brak"
    raise BladSprawy(f"w sprawie nie ma {co} {id!r} (znane: {znane})")


def czy_godzina(tekst: str) -> bool:
    """Godzina w formacie GG:MM.

    >>> czy_godzina("09:05"), czy_godzina("9:5"), czy_godzina("24:00")
    (True, False, False)
    """
    return bool(_GODZINA.match(tekst))


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


def _dozwolona(pole: str, wartosc: str, dozwolone: tuple[str, ...]) -> None:
    if wartosc not in dozwolone:
        raise ValueError(
            f"{pole}: nieznana wartość {wartosc!r} (dozwolone: {', '.join(dozwolone)})"
        )


def _sprawdz_wartosci(sprawa: Sprawa) -> None:
    for z in sprawa.zdarzenia:
        _dozwolona("typ", z.typ, TYPY_ZDARZEN)
        if z.godzina is not None and not czy_godzina(z.godzina):
            raise ValueError(f"godzina: {z.godzina!r} — oczekiwano GG:MM")
        if z.pewnosc is not None:
            _dozwolona("pewnosc", z.pewnosc, PEWNOSCI)
    for t in sprawa.terminy:
        _dozwolona("czyj", t.czyj, CZYJ_TERMINU)
    for u in sprawa.uczestnicy:
        _dozwolona("rola", u.rola, ROLE_UCZESTNIKOW)
    for p in sprawa.pisma:
        _dozwolona("stan", p.stan, STANY_PISMA)
    if sprawa.wynik is not None:
        _dozwolona("wynik", sprawa.wynik, WYNIKI_SPRAWY)


def z_slownika(d: dict[str, Any]) -> Sprawa:
    """Odwrotność do_slownika. Nieznany klucz, zła data albo nieznana wartość enumu →
    TypeError/ValueError/KeyError (repozytorium zamienia je na BladSprawy z nazwą pliku)."""
    sprawa = Sprawa(
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
    _sprawdz_wartosci(sprawa)
    return sprawa
