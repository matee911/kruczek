#!/usr/bin/env python3
"""teczka.py — jedyna droga zapisu danych sprawy (sprawa.json). Spec §6.

Podkomendy:
  nowa <sprawa> --tytul T --strona S [--wlasciciel W]   załóż sprawa.json
  watek <sprawa> <id> --adresat A                      dodaj wątek korespondencji
  zdarzenie <sprawa> --typ T [--data D] [--watek W] [--opis O] [--dowod P ...]
            [--termin 14d --podstawa P]                dopisz zdarzenie (reguły tworzą zadania);
                                                       --termin przy nadaniu = termin adresata,
                                                       przy odpowiedz/wplyw = Twój termin
  zadanie <sprawa> <opis> [--aktywne-od D|+Nd] [--termin D|+Nd] [--watek W]
  zrobione <sprawa> <id-zadania>
  co-robic [projekt]                                   przegląd wszystkich spraw
  renderuj <sprawa>                                    odśwież bloki w index.md
  dzien-wolny <data> --podstawa P [--projekt K] [--tylko-urzedy]
  przelicz <sprawa>                                    przelicz terminy

Kody wyjścia: 0 OK, 1 błąd sprawy (komunikat na stderr), 2 złe argumenty.
Tylko stdlib.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import re
import sys
from pathlib import Path

from kruczek_core.dni_wolne import PLIK_PROJEKTU, DzienJednorazowy, wczytaj_kalendarz, zapisz_jednorazowy
from kruczek_core.model import TYPY_ZDARZEN, BladSprawy
from kruczek_core.operacje import (
    dodaj_watek,
    dodaj_zadanie,
    dodaj_zdarzenie,
    nowa_sprawa,
    oznacz_zrobione,
    przelicz_sprawe,
)
from kruczek_core.reguly import SpecTerminu
from kruczek_core.render import renderuj
from kruczek_core.repozytorium import lista_spraw, wczytaj
from kruczek_core.widok import Przeglad, co_robic

_WZGLEDNA = re.compile(r"^\+(\d+)([dt])$")


def parsuj_date(tekst: str, dzis: dt.date) -> dt.date:
    """RRRR-MM-DD albo przesunięcie od dziś: +14d (dni), +2t (tygodnie).

    >>> parsuj_date("+1d", dt.date(2026, 10, 20))
    datetime.date(2026, 10, 21)
    """
    m = _WZGLEDNA.match(tekst)
    if m:
        n = int(m.group(1))
        return dzis + dt.timedelta(days=n if m.group(2) == "d" else 7 * n)
    try:
        return dt.date.fromisoformat(tekst)
    except ValueError:
        raise BladSprawy(f"nieznana data {tekst!r} — podaj RRRR-MM-DD albo +14d / +2t") from None


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="teczka.py", description="Dane sprawy: zdarzenia, terminy, zadania.")
    p.add_argument("--dzis", help="data „dziś” (RRRR-MM-DD) — do testów")
    sub = p.add_subparsers(dest="komenda", required=True)

    s = sub.add_parser("nowa", help="załóż sprawa.json")
    s.add_argument("sprawa", type=Path)
    s.add_argument("--tytul", required=True)
    s.add_argument("--strona", required=True, help="strona przeciwna")
    s.add_argument("--wlasciciel", default=getpass.getuser())

    s = sub.add_parser("watek", help="dodaj wątek korespondencji")
    s.add_argument("sprawa", type=Path)
    s.add_argument("id")
    s.add_argument("--adresat", required=True)

    s = sub.add_parser("zdarzenie", help="dopisz zdarzenie")
    s.add_argument("sprawa", type=Path)
    s.add_argument("--typ", required=True, choices=TYPY_ZDARZEN)
    s.add_argument("--data", help="RRRR-MM-DD, domyślnie dziś")
    s.add_argument("--watek")
    s.add_argument("--opis", default="")
    s.add_argument("--dowod", action="append", default=[])
    s.add_argument("--termin", help="14d, 2t, 1m, 1r — przy nadaniu: termin adresata; przy odpowiedz/wplyw: "
                                    "TWÓJ termin liczony od --data (dzień doręczenia do Ciebie, także po awizo)")
    s.add_argument("--podstawa", help="podstawa terminu, np. „art. 7 ust. 1 u.r.”")

    s = sub.add_parser("zadanie", help="dodaj zadanie")
    s.add_argument("sprawa", type=Path)
    s.add_argument("opis")
    s.add_argument("--aktywne-od", default="+0d")
    s.add_argument("--termin")
    s.add_argument("--watek")

    s = sub.add_parser("zrobione", help="oznacz zadanie jako zrobione")
    s.add_argument("sprawa", type=Path)
    s.add_argument("id")

    s = sub.add_parser("co-robic", help="przegląd wszystkich spraw")
    s.add_argument("projekt", type=Path, nargs="?", default=Path("."))

    s = sub.add_parser("renderuj", help="odśwież bloki w index.md")
    s.add_argument("sprawa", type=Path)

    s = sub.add_parser("dzien-wolny", help="dodaj jednorazowy dzień wolny i przelicz terminy")
    s.add_argument("data")
    s.add_argument("--podstawa", required=True)
    s.add_argument("--projekt", type=Path, default=Path("."))
    s.add_argument("--tylko-urzedy", action="store_true")

    s = sub.add_parser("przelicz", help="przelicz terminy sprawy")
    s.add_argument("sprawa", type=Path)
    return p


def _projekt(sprawa: Path) -> Path:
    return sprawa.resolve().parent


def _wypisz(przeglad: Przeglad, stary_format: list[Path]) -> None:
    print("TERAZ")
    for p in przeglad.teraz or []:
        termin = f"  termin {p.zadanie.termin.isoformat()}" if p.zadanie.termin else ""
        watek = f" / {p.zadanie.watek}" if p.zadanie.watek else ""
        print(f"  [{p.zadanie.id}] {p.sprawa}{watek} — {p.zadanie.opis}{termin}")
    if not przeglad.teraz:
        print("  —")
    print("CZEKAM")
    for c in przeglad.czekam:
        do = f"do {c.czekam_do.isoformat()}" if c.czekam_do else "bez terminu"
        print(f"  {c.sprawa} / {c.watek.id} ({c.watek.adresat}) — {do}{' (szacunek)' if c.szacunek else ''}")
    if not przeglad.czekam:
        print("  —")
    print("WKRÓTCE")
    for p in przeglad.wkrotce:
        print(f"  od {p.zadanie.aktywne_od.isoformat()}  [{p.zadanie.id}] {p.sprawa} — {p.zadanie.opis}")
    if not przeglad.wkrotce:
        print("  —")
    if stary_format:
        print("STARY FORMAT (bez sprawa.json — uruchom migrację)")
        for k in stary_format:
            print(f"  {k.name}")


def _wykonaj(a: argparse.Namespace, dzis: dt.date) -> None:
    if a.komenda == "nowa":
        a.sprawa.mkdir(parents=True, exist_ok=True)
        s = nowa_sprawa(a.sprawa, a.tytul, a.strona, a.wlasciciel)
        print(f"założono {a.sprawa / 'sprawa.json'} (id {s.id})")
    elif a.komenda == "watek":
        dodaj_watek(a.sprawa, a.id, a.adresat)
        print(f"wątek {a.id}: {a.adresat}")
    elif a.komenda == "zdarzenie":
        if (a.termin is None) != (a.podstawa is None):
            raise BladSprawy("--termin i --podstawa podaje się razem")
        spec = SpecTerminu(a.termin, a.podstawa) if a.termin else None
        data = parsuj_date(a.data, dzis) if a.data else dzis
        for k in dodaj_zdarzenie(a.sprawa, a.typ, data, wczytaj_kalendarz(_projekt(a.sprawa)), dzis,
                                 watek=a.watek, opis=a.opis, dowody=a.dowod, termin=spec):
            print(k)
    elif a.komenda == "zadanie":
        termin = parsuj_date(a.termin, dzis) if a.termin else None
        z = dodaj_zadanie(a.sprawa, a.opis, parsuj_date(a.aktywne_od, dzis), termin=termin, watek=a.watek)
        print(f"zadanie {z.id}: {z.opis} (aktywne od {z.aktywne_od.isoformat()})")
    elif a.komenda == "zrobione":
        z = oznacz_zrobione(a.sprawa, a.id, dzis)
        print(f"zrobione {z.id}: {z.opis}")
    elif a.komenda == "co-robic":
        lista = lista_spraw(a.projekt)
        _wypisz(co_robic([wczytaj(k) for k in lista.sprawy], dzis), lista.stary_format)
    elif a.komenda == "renderuj":
        index = a.sprawa / "index.md"
        tekst = index.read_text(encoding="utf-8") if index.exists() else ""
        index.write_text(renderuj(tekst, wczytaj(a.sprawa), wczytaj_kalendarz(_projekt(a.sprawa))), encoding="utf-8")
        print(f"odświeżono {index}")
    elif a.komenda == "dzien-wolny":
        zapisz_jednorazowy(a.projekt / PLIK_PROJEKTU,
                           DzienJednorazowy(parsuj_date(a.data, dzis), a.podstawa, a.tylko_urzedy))
        kalendarz = wczytaj_kalendarz(a.projekt)
        for k in lista_spraw(a.projekt).sprawy:
            for zmiana in przelicz_sprawe(k, kalendarz):
                print(f"{k.name}: {zmiana}")
    elif a.komenda == "przelicz":
        for zmiana in przelicz_sprawe(a.sprawa, wczytaj_kalendarz(_projekt(a.sprawa))) or ["bez zmian"]:
            print(zmiana)


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        dzis = parsuj_date(a.dzis, dt.date.today()) if a.dzis else dt.date.today()
        _wykonaj(a, dzis)
    except (BladSprawy, OSError) as e:
        print(f"błąd: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
