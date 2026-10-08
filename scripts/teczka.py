#!/usr/bin/env python3
"""teczka.py — jedyna droga zapisu danych sprawy (sprawa.json).

Podkomendy:
  nowa <sprawa> --tytul T --strona S [--wlasciciel W]   załóż sprawa.json
  watek <sprawa> <id> --adresat A                      dodaj wątek korespondencji
  zdarzenie <sprawa> --typ T [--data D] [--watek W] [--opis O] [--dowod P ...]
            [--termin 14d --podstawa P] [--dotyczy zN]  dopisz zdarzenie (reguły tworzą zadania);
                                                       --termin przy nadaniu = termin adresata,
                                                       przy odpowiedz/wplyw = Twój termin
  zadanie <sprawa> <opis> [--aktywne-od D|+Nd] [--termin D|+Nd] [--watek W]
  zrobione <sprawa> <id-zadania>
  zamknij <sprawa> --wynik {wygrana,ugoda,porzucona}   zamknij sprawę (znika z przeglądu)
  otworz <sprawa>                                      otwórz ponownie zamkniętą sprawę
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
from kruczek_core.model import TYPY_ZDARZEN, WYNIKI_SPRAWY, BladSprawy
from kruczek_core.operacje import (
    dodaj_watek,
    dodaj_zadanie,
    dodaj_zdarzenie,
    nowa_sprawa,
    otworz_sprawe,
    oznacz_zrobione,
    przelicz_sprawe,
    zamknij_sprawe,
)
from kruczek_core.reguly import SpecTerminu
from kruczek_core.render import renderuj
from kruczek_core.repozytorium import czy_folder_sprawy, lista_spraw, przetworz_tekst, wczytaj
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


_TYPY_POMOC = """typy zdarzeń (kierunek):
  nadanie     Ty wysyłasz pismo
  doreczenie  Twoje pismo doszło do adresata
  odpowiedz   adresat odpisał Tobie
  wplyw       przyszło do Ciebie pismo/decyzja (Twój termin liczony od tej daty)
  fakt, telefon, inne   notatka
"""


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

    s = sub.add_parser("zdarzenie", help="dopisz zdarzenie", epilog=_TYPY_POMOC,
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument("sprawa", type=Path)
    s.add_argument("--typ", required=True, choices=TYPY_ZDARZEN, help="rodzaj zdarzenia (kierunek: patrz niżej)")
    s.add_argument("--data", help="RRRR-MM-DD, domyślnie dziś")
    s.add_argument("--watek")
    s.add_argument("--opis", default="")
    s.add_argument("--dowod", action="append", default=[])
    s.add_argument("--termin", help="14d, 2t, 1m, 1r — przy nadaniu: termin adresata; przy odpowiedz/wplyw: "
                                    "TWÓJ termin liczony od --data (dzień doręczenia do Ciebie, także po awizo)")
    s.add_argument("--podstawa", help="podstawa terminu, np. „art. 7 ust. 1 u.r.”")
    s.add_argument("--dotyczy", help="id Twojego nadania, którego dotyczy doręczenie/odpowiedź — potrzebne "
                                     "tylko, gdy w wątku czeka naraz kilka pism")

    s = sub.add_parser("zadanie", help="dodaj zadanie")
    s.add_argument("sprawa", type=Path)
    s.add_argument("opis")
    s.add_argument("--aktywne-od", default="+0d")
    s.add_argument("--termin")
    s.add_argument("--watek")

    s = sub.add_parser("zrobione", help="oznacz zadanie jako zrobione")
    s.add_argument("sprawa", type=Path)
    s.add_argument("id")

    s = sub.add_parser("zamknij", help="zamknij sprawę (znika z przeglądu)")
    s.add_argument("sprawa", type=Path)
    s.add_argument("--wynik", required=True, choices=WYNIKI_SPRAWY)

    s = sub.add_parser("otworz", help="otwórz ponownie zamkniętą sprawę")
    s.add_argument("sprawa", type=Path)

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
        print("STARY FORMAT (bez sprawa.json — migracja w kolejnej wersji; nowa sprawa: teczka.py nowa)")
        for k in stary_format:
            print(f"  {k.name}")


def _projekt_z_argumentu(projekt: Path) -> Path:
    """Folder sprawy podany zamiast projektu → jego rodzic (z uwagą na stderr)."""
    if not czy_folder_sprawy(projekt):
        return projekt
    rodzic = projekt.resolve().parent
    print(f"uwaga: {projekt.resolve()} to folder sprawy — pokazuję cały projekt {rodzic}", file=sys.stderr)
    return rodzic


def _wypisz_bledy(bledy: list[tuple[Path, str]]) -> int:
    print("BŁĘDY")
    for k, komunikat in bledy:
        print(f"  {k.name}: {komunikat}")
        print(f"błąd: {komunikat}", file=sys.stderr)
    return 1


def _wykonaj(a: argparse.Namespace, dzis: dt.date) -> int:
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
                                 watek=a.watek, opis=a.opis, dowody=a.dowod, termin=spec,
                                 dotyczy=a.dotyczy):
            print(k)
    elif a.komenda == "zadanie":
        termin = parsuj_date(a.termin, dzis) if a.termin else None
        z = dodaj_zadanie(a.sprawa, a.opis, parsuj_date(a.aktywne_od, dzis), termin=termin, watek=a.watek)
        print(f"zadanie {z.id}: {z.opis} (aktywne od {z.aktywne_od.isoformat()})")
    elif a.komenda == "zrobione":
        z = oznacz_zrobione(a.sprawa, a.id, dzis)
        print(f"zrobione {z.id}: {z.opis}")
    elif a.komenda == "zamknij":
        zamknij_sprawe(a.sprawa, a.wynik)
        print(f"zamknięto sprawę {a.sprawa.name} ({a.wynik})")
    elif a.komenda == "otworz":
        otworz_sprawe(a.sprawa)
        print(f"otwarto sprawę {a.sprawa.name}")
    elif a.komenda == "co-robic":
        projekt = _projekt_z_argumentu(a.projekt)
        lista = lista_spraw(projekt)
        if not lista.sprawy and not lista.stary_format:
            print(f"brak spraw w {projekt}")
            return 0
        sprawy, bledy = [], []
        for k in lista.sprawy:
            try:
                sprawy.append(wczytaj(k))
            except BladSprawy as e:
                bledy.append((k, str(e)))
        _wypisz(co_robic(sprawy, dzis), lista.stary_format)
        if bledy:
            return _wypisz_bledy(bledy)
    elif a.komenda == "renderuj":
        kalendarz = wczytaj_kalendarz(_projekt(a.sprawa))
        index = przetworz_tekst(a.sprawa, "index.md", lambda tekst: renderuj(tekst, wczytaj(a.sprawa), kalendarz))
        print(f"odświeżono {index}")
    elif a.komenda == "dzien-wolny":
        projekt = _projekt_z_argumentu(a.projekt)
        data = parsuj_date(a.data, dzis)
        plik = projekt / PLIK_PROJEKTU
        zapisz_jednorazowy(plik, DzienJednorazowy(data, a.podstawa, a.tylko_urzedy))
        print(f"zapisano dzień wolny {data.isoformat()} w {plik}")
        kalendarz = wczytaj_kalendarz(projekt)
        bledy = []
        for k in lista_spraw(projekt).sprawy:
            try:
                for zmiana in przelicz_sprawe(k, kalendarz):
                    print(f"{k.name}: {zmiana}")
            except BladSprawy as e:
                bledy.append((k, str(e)))
        if bledy:
            return _wypisz_bledy(bledy)
    elif a.komenda == "przelicz":
        for zmiana in przelicz_sprawe(a.sprawa, wczytaj_kalendarz(_projekt(a.sprawa))) or ["bez zmian"]:
            print(zmiana)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        parser.print_help()
        raise SystemExit(2)
    a = parser.parse_args(argv)
    try:
        dzis = parsuj_date(a.dzis, dt.date.today()) if a.dzis else dt.date.today()
        return _wykonaj(a, dzis)
    except (BladSprawy, OSError) as e:
        print(f"błąd: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
