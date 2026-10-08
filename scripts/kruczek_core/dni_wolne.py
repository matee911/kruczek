"""Dni wolne od pracy w Polsce — reguły z art. 1 ustawy o dniach wolnych od pracy.

Źródło: t.j. Dz.U. 2025 poz. 296 (ELI DU/2025/296), stan sprawdzony 2026-10-08.
Wigilia jest dniem wolnym od 1.02.2025 (ustawa z 6.12.2024, Dz.U. 2024 poz. 1965).

Obok listy z ustawy są dni wolne JEDNORAZOWE, ustanawiane osobnymi aktami: plik
dni_wolne_jednorazowe.json w pluginie plus .kruczek/dni-wolne.json w projekcie
użytkownika. Dzień „tylko dla urzędów” (rozporządzenie PRM) nie jest dniem „uznanym
ustawowo za wolny od pracy” w rozumieniu art. 115 k.c. — nie przesuwa terminu, daje
tylko ostrzeżenie. To ocena, nie pewnik (spec §5.2).

Lata przed 2000 nie są obsługiwane.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
from dataclasses import dataclass
from pathlib import Path

from kruczek_core.model import BladSprawy

PIERWSZY_ROK = 2000
JEDNORAZOWE_PLUGIN = Path(__file__).with_name("dni_wolne_jednorazowe.json")
PLIK_PROJEKTU = Path(".kruczek") / "dni-wolne.json"

# (miesiąc, dzień, nazwa, obowiązuje od) — art. 1 pkt 1 ustawy
_STALE = (
    (1, 1, "Nowy Rok", None),
    (1, 6, "Święto Trzech Króli", dt.date(2011, 1, 1)),
    (5, 1, "Święto Państwowe", None),
    (5, 3, "Święto Narodowe Trzeciego Maja", None),
    (8, 15, "Wniebowzięcie Najświętszej Maryi Panny", None),
    (11, 1, "Wszystkich Świętych", None),
    (11, 11, "Narodowe Święto Niepodległości", None),
    (12, 24, "Wigilia Bożego Narodzenia", dt.date(2025, 2, 1)),
    (12, 25, "pierwszy dzień Bożego Narodzenia", None),
    (12, 26, "drugi dzień Bożego Narodzenia", None),
)


def wielkanoc(rok: int) -> dt.date:
    """Niedziela Wielkanocna w kalendarzu gregoriańskim (algorytm Meeusa/Jonesa/Butchera).

    >>> wielkanoc(2025)
    datetime.date(2025, 4, 20)
    """
    a = rok % 19
    b, c = divmod(rok, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 — nazwa z algorytmu
    m = (a + 11 * h + 22 * l) // 451
    miesiac, dzien = divmod(h + l - 7 * m + 114, 31)
    return dt.date(rok, miesiac, dzien + 1)


@functools.cache
def dni_ustawowo_wolne(rok: int) -> dict[dt.date, str]:
    """Dni z art. 1 pkt 1 ustawy w danym roku — bez zwykłych niedziel (art. 1 pkt 2).

    Wynik jest współdzielony przez cache — nie modyfikuj go.

    >>> dt.date(2024, 12, 24) in dni_ustawowo_wolne(2024)
    False
    >>> dni_ustawowo_wolne(2025)[dt.date(2025, 12, 24)]
    'Wigilia Bożego Narodzenia'
    """
    if rok < PIERWSZY_ROK:
        raise ValueError(f"lata przed {PIERWSZY_ROK} nie są obsługiwane: {rok}")
    out: dict[dt.date, str] = {}
    for miesiac, dzien, nazwa, od in _STALE:
        data = dt.date(rok, miesiac, dzien)
        if od is None or data >= od:
            out[data] = nazwa
    w = wielkanoc(rok)
    out[w] = "pierwszy dzień Wielkiej Nocy"
    out[w + dt.timedelta(days=1)] = "drugi dzień Wielkiej Nocy"
    out[w + dt.timedelta(days=49)] = "pierwszy dzień Zielonych Świątek"
    out[w + dt.timedelta(days=60)] = "dzień Bożego Ciała"
    return out


@dataclass(frozen=True)
class DzienJednorazowy:
    data: dt.date
    podstawa: str
    tylko_urzedy: bool = False


def wczytaj_jednorazowe(sciezka: Path) -> list[DzienJednorazowy]:
    if not sciezka.exists():
        return []
    try:
        dane = json.loads(sciezka.read_text(encoding="utf-8"))
        return [
            DzienJednorazowy(dt.date.fromisoformat(w["data"]), w["podstawa"], w.get("tylko_urzedy", False))
            for w in dane
        ]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError) as e:
        raise BladSprawy(f"{sciezka}: uszkodzony plik dni wolnych — {e}") from e


def zapisz_jednorazowy(sciezka: Path, dzien: DzienJednorazowy) -> None:
    """Dopisz dzień do pliku (bez duplikatów po dacie), posortowany po dacie."""
    dni = {d.data: d for d in wczytaj_jednorazowe(sciezka)}
    dni[dzien.data] = dzien
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    wiersze = [
        {"data": d.data.isoformat(), "podstawa": d.podstawa, "tylko_urzedy": d.tylko_urzedy}
        for d in sorted(dni.values(), key=lambda d: d.data)
    ]
    sciezka.write_text(json.dumps(wiersze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class Kalendarz:
    jednorazowe: tuple[DzienJednorazowy, ...] = ()

    def czy_wolny(self, d: dt.date) -> bool:
        """Niedziela, dzień z art. 1 ustawy albo jednorazowy dzień wolny ustanowiony ustawą."""
        if d.weekday() == 6 or d in dni_ustawowo_wolne(d.year):
            return True
        return any(j.data == d and not j.tylko_urzedy for j in self.jednorazowe)

    def czy_przesuwa(self, d: dt.date) -> bool:
        """Czy koniec terminu w tym dniu się przesuwa: sobota albo dzień wolny
        (art. 115 k.c., art. 57 § 4 k.p.a.)."""
        return d.weekday() == 5 or self.czy_wolny(d)

    def ostrzezenia(self, d: dt.date) -> list[str]:
        return [
            f"urzędy zamknięte {d.isoformat()} ({j.podstawa}) — wyślij wcześniej"
            for j in self.jednorazowe
            if j.data == d and j.tylko_urzedy
        ]


def wczytaj_kalendarz(katalog_projektu: Path | None) -> Kalendarz:
    dni = wczytaj_jednorazowe(JEDNORAZOWE_PLUGIN)
    if katalog_projektu is not None:
        dni += wczytaj_jednorazowe(katalog_projektu / PLIK_PROJEKTU)
    return Kalendarz(tuple(dni))
