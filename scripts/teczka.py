#!/usr/bin/env python3
"""teczka.py — jedyna droga zapisu danych sprawy (sprawa.json).

Podkomendy:
  nowa <sprawa> --tytul T --strona S [--wlasciciel W]   załóż sprawa.json
  watek <sprawa> <id> --adresat A                      dodaj wątek korespondencji
  zdarzenie <sprawa> --typ T [--data D] [--watek W] [--opis O] [--dowod P ...]
            [--termin 14d --podstawa P] [--dotyczy zN]
            [--godzina GG:MM] [--pewnosc dowod|poszlaka|wlasne_oswiadczenie]  dopisz zdarzenie (reguły tworzą zadania);
                                                       --termin przy nadaniu = termin adresata,
                                                       przy odpowiedz/wplyw = Twój termin
  popraw-zdarzenie <sprawa> <id> [--data D] [--opis O] [--godzina G] [--pewnosc P] [--dowod P ...]
  cofnij-zdarzenie <sprawa> <id>                       cofnij ostatnio wpisane zdarzenie razem ze skutkami
  zadanie <sprawa> <opis> [--aktywne-od D|+Nd] [--termin D|+Nd] [--watek W]
  zrobione <sprawa> <id-zadania>
  zamknij <sprawa> --wynik {wygrana,ugoda,porzucona}   zamknij sprawę (znika z przeglądu)
  otworz <sprawa>                                      otwórz ponownie zamkniętą sprawę
  co-robic [projekt]                                   przegląd wszystkich spraw
  renderuj <sprawa>                                    odśwież bloki w index.md
  dzien-wolny <data> --podstawa P [--projekt K] [--tylko-urzedy]
  przelicz <sprawa>                                    przelicz terminy
  migruj <sprawa> <propozycja.json> [--zapisz] [--wlasciciel W]
                                                       stara teczka (index.md) → sprawa.json;
                                                       bez --zapisz tylko podgląd

Kody wyjścia: 0 OK, 1 błąd sprawy (komunikat na stderr), 2 złe argumenty.
Tylko stdlib.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import re
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from kruczek_core.dni_wolne import PLIK_PROJEKTU, DzienJednorazowy, Kalendarz, kalendarz_sprawy, zapisz_jednorazowy
from kruczek_core.migracja import (
    Podsumowanie,
    kopia_zapasowa,
    tytul_z_naglowka,
    wczytaj_propozycje,
    wstaw_znaczniki_chronologii,
    zbuduj_sprawe,
)
from kruczek_core.model import PEWNOSCI, TYPY_ZDARZEN, WYNIKI_SPRAWY, BladSprawy
from kruczek_core.operacje import (
    cofnij_zdarzenie,
    dodaj_watek,
    dodaj_zadanie,
    dodaj_zdarzenie,
    nowa_sprawa,
    otworz_sprawe,
    oznacz_zrobione,
    popraw_zdarzenie,
    przelicz_sprawe,
    zamknij_sprawe,
)
from kruczek_core.reguly import SpecTerminu
from kruczek_core.render import renderuj
from kruczek_core.repozytorium import (
    PLIK_SPRAWY,
    czy_folder_sprawy,
    czy_rejestr_spraw,
    lista_spraw,
    przetworz_tekst,
    wczytaj,
    zapisz_nowa,
)
from kruczek_core.widok import DNI_BEZ_RUCHU, PozycjaZadania, Przeglad, co_robic

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
    s.add_argument("--wlasciciel")

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
    s.add_argument("--godzina", help="GG:MM, jeśli znana (maile, telefony)")
    s.add_argument("--pewnosc", choices=PEWNOSCI, help="dowod / poszlaka / wlasne_oswiadczenie (fakt bez pliku)")

    s = sub.add_parser("cofnij-zdarzenie", help="cofnij ostatnio wpisane zdarzenie razem z jego skutkami")
    s.add_argument("sprawa", type=Path)
    s.add_argument("id")

    s = sub.add_parser("popraw-zdarzenie", help="popraw błędnie wpisane zdarzenie (data, opis, godzina, pewność, dowody)")
    s.add_argument("sprawa", type=Path)
    s.add_argument("id")
    s.add_argument("--data")
    s.add_argument("--opis")
    s.add_argument("--godzina", help='GG:MM; "" czyści')
    s.add_argument("--pewnosc", help='dowod / poszlaka / wlasne_oswiadczenie; "" czyści')
    s.add_argument("--dowod", action="append", help="zastępuje listę dowodów")

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

    s = sub.add_parser("migruj", help="stara teczka (index.md) → sprawa.json; bez --zapisz tylko podgląd")
    s.add_argument("sprawa", type=Path)
    s.add_argument("propozycja", type=Path, help="JSON z propozycją (pisze go /kruczek:migruj)")
    s.add_argument("--zapisz", action="store_true", help="zapisz po akceptacji podglądu")
    s.add_argument("--wlasciciel")
    return p


def _uzytkownik() -> str:
    try:
        return getpass.getuser()
    except (KeyError, OSError):
        raise BladSprawy("nie da się ustalić użytkownika — podaj --wlasciciel") from None


def _etykieta(sprawa: Path, projekt: Path) -> str:
    """Ścieżka sprawy względem projektu: `sprawa` albo `podprojekt/sprawa`."""
    return sprawa.relative_to(projekt).as_posix()


def _odswiez(katalog: Path, przed: Callable[[str], str] = lambda t: t) -> None:
    """Po udanym zapisie odśwież bloki index.md (jeśli istnieje). Błąd tutaj NIE jest błędem
    zapisu — kod 0, inaczej skill powtórzyłby polecenie i zdublował zdarzenie."""
    if not (katalog / "index.md").exists():
        return
    try:
        kalendarz = kalendarz_sprawy(katalog)
        przetworz_tekst(katalog, "index.md", lambda tekst: renderuj(przed(tekst), wczytaj(katalog), kalendarz))
    except (BladSprawy, OSError) as e:
        print(f"uwaga: zapisano, ale index.md nie odświeżony: {e}", file=sys.stderr)


def _linia_zadania(p: PozycjaZadania, kal: Kalendarz, dzis: dt.date) -> str:
    z = p.zadanie
    watek = f" / {z.watek}" if z.watek else ""
    dopiski = []
    if z.termin is not None:
        dopiski.append(f"termin {z.termin.isoformat()}")
        if z.termin < dzis:
            dopiski.append(f"PO TERMINIE ({(dzis - z.termin).days} dni)")
        dopiski += kal.ostrzezenia(z.termin)
    reszta = f"  {'; '.join(dopiski)}" if dopiski else ""
    return f"[{z.id}] {p.sprawa_id}: {p.sprawa}{watek} — {z.opis}{reszta}"


def _wypisz(przeglad: Przeglad, stary_format: list[str], bez_indexu: list[str], kals: dict[str, Kalendarz],
            dzis: dt.date) -> None:
    """`sprawa_id` w przeglądzie to etykieta folderu (patrz `co-robic`), nie `Sprawa.id`."""
    print("TERAZ")
    for p in przeglad.teraz:
        print(f"  {_linia_zadania(p, kals[p.sprawa_id], dzis)}")
    if not przeglad.teraz:
        print("  —")
    print("CZEKAM")
    for c in przeglad.czekam:
        do = f"do {c.czekam_do.isoformat()}" if c.czekam_do else "bez terminu"
        print(f"  {c.sprawa_id}: {c.sprawa} / {c.watek.id} ({c.watek.adresat}) — {do}{' (szacunek)' if c.szacunek else ''}")
    if not przeglad.czekam:
        print("  —")
    print("WKRÓTCE")
    for p in przeglad.wkrotce:
        print(f"  od {p.zadanie.aktywne_od.isoformat()}  {_linia_zadania(p, kals[p.sprawa_id], dzis)}")
    if not przeglad.wkrotce:
        print("  —")
    if przeglad.bez_ruchu:
        print(f"BEZ RUCHU (ponad {DNI_BEZ_RUCHU} dni)")
        for b in przeglad.bez_ruchu:
            kiedy = b.ostatni_ruch.isoformat() if b.ostatni_ruch else "brak zdarzeń"
            print(f"  {b.sprawa_id}: {b.sprawa} — ostatni ruch {kiedy}")
    if stary_format:
        print("STARY FORMAT (bez sprawa.json — przenieś: /kruczek:migruj)")
        for k in stary_format:
            print(f"  {k}")
    if bez_indexu:
        print("POMINIĘTO (brak index.md)")
        for k in bez_indexu:
            print(f"  {k}")


def _projekt_z_argumentu(projekt: Path) -> Path:
    """Folder sprawy podany zamiast projektu → jego rodzic (z uwagą na stderr)."""
    if not czy_folder_sprawy(projekt):
        return projekt
    rodzic = projekt.resolve().parent
    print(f"uwaga: {projekt.resolve()} to folder sprawy — pokazuję cały projekt {rodzic}", file=sys.stderr)
    return rodzic


def _wypisz_bledy(bledy: list[tuple[str, str]]) -> int:
    print("BŁĘDY")
    for etykieta, komunikat in bledy:
        print(f"  {etykieta}: {komunikat}")
        print(f"błąd: {komunikat}", file=sys.stderr)
    return 1


def _wypisz_podsumowanie(p: Podsumowanie, kal: Kalendarz) -> None:
    s = p.sprawa
    print(f"SPRAWA: {s.tytul} — {s.strona_przeciwna}{' (zamknięta: ' + s.wynik + ')' if s.zamknieta else ''}")
    print(f"wątki: {', '.join(f'{w.id} ({w.adresat})' for w in s.watki) or '—'}; "
          f"zdarzeń: {len(s.zdarzenia)}, terminów: {len(s.terminy)}, "
          f"otwartych zadań: {sum(1 for a in s.zadania if a.zrobione is None)}")
    print(renderuj("", s, kal).strip())
    for o in p.ostrzezenia:
        print(f"uwaga: {o}")


def _migruj(a: argparse.Namespace, dzis: dt.date) -> int:
    """Kolejność zapisu: kopia → sprawa.json → index.md. Wszystko, co może się nie udać, jest
    sprawdzane przed kopią; nieudane odświeżenie index.md to już tylko uwaga (kod 0)."""
    index = a.sprawa / "index.md"
    if (a.sprawa / PLIK_SPRAWY).exists():
        raise BladSprawy(f"{a.sprawa}: już zmigrowana (jest {PLIK_SPRAWY})")
    if not index.is_file():
        raise BladSprawy(f"{a.sprawa}: brak index.md — to nie stara teczka; nową sprawę zakłada teczka.py nowa")
    if czy_rejestr_spraw(a.sprawa):
        raise BladSprawy(f"{a.sprawa}: to podprojekt („# Rejestr spraw”) — migruj osobno każdą sprawę z jego środka")
    try:
        tekst = index.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise BladSprawy(f"{index}: nie jest w UTF-8 — nic nie zapisano") from None
    propozycja = wczytaj_propozycje(a.propozycja)
    tytul = tytul_z_naglowka(tekst)
    if "tytul" not in propozycja and tytul:
        propozycja["tytul"] = tytul
    kalendarz = kalendarz_sprawy(a.sprawa)
    wlasciciel = a.wlasciciel if a.wlasciciel is not None else _uzytkownik()
    pods = zbuduj_sprawe(propozycja, kalendarz, dzis, wlasciciel)
    _wypisz_podsumowanie(pods, kalendarz)
    nowy, wstawiono = wstaw_znaczniki_chronologii(tekst)
    if not wstawiono and "<!-- kruczek:chronologia -->" not in tekst:
        print("uwaga: nie znaleziono nagłówka „Chronologia” — blok trafi na koniec, stara tabela bez zmian")
    try:
        renderuj(nowy, pods.sprawa, kalendarz)
    except BladSprawy as e:
        print(f"uwaga: sprawa.json zostanie zapisana, ale index.md nie odświeżony: {e}")
    if not a.zapisz:
        print(f"\npodgląd — nic nie zapisano. Zapis: teczka.py migruj {a.sprawa} {a.propozycja} --zapisz")
        return 0
    kopia = kopia_zapasowa(a.sprawa, dzis)
    zapisz_nowa(a.sprawa, pods.sprawa)
    print(f"zapisano {a.sprawa / PLIK_SPRAWY}; kopia starego index.md: {kopia}")
    _odswiez(a.sprawa, przed=lambda t: wstaw_znaczniki_chronologii(t)[0])
    return 0


_ZAPISUJACE = {"nowa", "watek", "zdarzenie", "zadanie", "zrobione", "przelicz", "zamknij", "otworz",
               "popraw-zdarzenie", "cofnij-zdarzenie"}


def _wykonaj(a: argparse.Namespace, dzis: dt.date) -> int:
    if a.komenda == "nowa":
        wlasciciel = a.wlasciciel if a.wlasciciel is not None else _uzytkownik()
        a.sprawa.mkdir(parents=True, exist_ok=True)
        s = nowa_sprawa(a.sprawa, a.tytul, a.strona, wlasciciel)
        print(f"założono {a.sprawa / 'sprawa.json'} (id {s.id})")
    elif a.komenda == "watek":
        dodaj_watek(a.sprawa, a.id, a.adresat)
        print(f"wątek {a.id}: {a.adresat}")
    elif a.komenda == "zdarzenie":
        if (a.termin is None) != (a.podstawa is None):
            raise BladSprawy("--termin i --podstawa podaje się razem")
        spec = SpecTerminu(a.termin, a.podstawa) if a.termin else None
        data = parsuj_date(a.data, dzis) if a.data else dzis
        for k in dodaj_zdarzenie(a.sprawa, a.typ, data, kalendarz_sprawy(a.sprawa), dzis,
                                 watek=a.watek, opis=a.opis, dowody=a.dowod, termin=spec,
                                 dotyczy=a.dotyczy, godzina=a.godzina, pewnosc=a.pewnosc):
            print(k)
    elif a.komenda == "popraw-zdarzenie":
        data = parsuj_date(a.data, dzis) if a.data else None
        for k in popraw_zdarzenie(a.sprawa, a.id, kalendarz_sprawy(a.sprawa), dzis, data=data,
                                  opis=a.opis, godzina=a.godzina, pewnosc=a.pewnosc, dowody=a.dowod):
            print(k)
    elif a.komenda == "cofnij-zdarzenie":
        for k in cofnij_zdarzenie(a.sprawa, a.id, kalendarz_sprawy(a.sprawa)):
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
        if not (lista.sprawy or lista.stary_format or lista.bez_indexu):
            print(f"brak spraw w {projekt}")
            return 0
        sprawy, bledy, widziane, kals = [], [], {}, {}
        for k in lista.sprawy:
            etykieta = _etykieta(k, projekt)
            try:
                s = wczytaj(k)
                kals[etykieta] = kalendarz_sprawy(k)
            except BladSprawy as e:
                bledy.append((etykieta, str(e)))
                continue
            if s.id in widziane:
                bledy.append((etykieta, f"to samo id sprawy ({s.id}) co w {widziane[s.id]} — jeden z folderów to kopia"))
            else:
                widziane[s.id] = etykieta
            sprawy.append(replace(s, id=etykieta))  # id = etykieta folderu, by kopie nie myliły linii
        _wypisz(co_robic(sprawy, dzis), [_etykieta(k, projekt) for k in lista.stary_format],
                [_etykieta(k, projekt) for k in lista.bez_indexu], kals, dzis)
        if bledy:
            return _wypisz_bledy(bledy)
    elif a.komenda == "renderuj":
        wczytaj(a.sprawa)  # BladSprawy bez brania blokady, gdy to nie folder sprawy
        kalendarz = kalendarz_sprawy(a.sprawa)
        index = przetworz_tekst(a.sprawa, "index.md", lambda tekst: renderuj(tekst, wczytaj(a.sprawa), kalendarz))
        print(f"odświeżono {index}")
    elif a.komenda == "dzien-wolny":
        projekt = _projekt_z_argumentu(a.projekt)
        data = parsuj_date(a.data, dzis)
        plik = projekt / PLIK_PROJEKTU
        zapisz_jednorazowy(plik, DzienJednorazowy(data, a.podstawa, a.tylko_urzedy))
        print(f"zapisano dzień wolny {data.isoformat()} w {plik}")
        bledy = []
        for k in lista_spraw(projekt).sprawy:
            etykieta = _etykieta(k, projekt)
            try:
                for zmiana in przelicz_sprawe(k, kalendarz_sprawy(k)):
                    print(f"{etykieta}: {zmiana}")
                _odswiez(k)
            except BladSprawy as e:
                bledy.append((etykieta, str(e)))
        if bledy:
            return _wypisz_bledy(bledy)
    elif a.komenda == "migruj":
        return _migruj(a, dzis)
    elif a.komenda == "przelicz":
        for zmiana in przelicz_sprawe(a.sprawa, kalendarz_sprawy(a.sprawa)) or ["bez zmian"]:
            print(zmiana)
    if a.komenda in _ZAPISUJACE:
        _odswiez(a.sprawa)
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
