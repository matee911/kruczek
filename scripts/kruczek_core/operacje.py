"""Operacje na teczce — jedyna droga zapisu dla CLI, strony i MCP.

Walidacja wejścia jest tutaj, nie w CLI: strona i MCP dostaną te same komunikaty.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from collections.abc import Sequence
from pathlib import Path

from kruczek_core.dni_wolne import PIERWSZY_ROK, Kalendarz
from kruczek_core.model import (
    PEWNOSCI,
    TYPY_ZDARZEN,
    WYNIKI_SPRAWY,
    ZDARZENIA_PRZYCHODZACE,
    ZDARZENIA_WATKU,
    BladSprawy,
    Sprawa,
    Uczestnik,
    Watek,
    Zadanie,
    Zdarzenie,
    czy_godzina,
    kolejne_id,
)
from kruczek_core.reguly import (
    REGULA_DORECZENIE,
    REGULA_START,
    REGULA_START_NADANIE,
    SpecTerminu,
    cofnij,
    przelicz,
    zastosuj,
    zmien_date,
)
from kruczek_core.repozytorium import PLIK_SPRAWY, KonfliktRewizji, zapisz_nowa, zmien
from kruczek_core.terminy import koniec_terminu, parsuj_dlugosc


def _niepusty(nazwa: str, wartosc: str) -> str:
    czysta = wartosc.strip()
    if not czysta:
        raise BladSprawy(f"{nazwa} nie może być pusty")
    return czysta


def _sprawdz_godzine(godzina: str) -> str:
    czysta = godzina.strip()
    if not czy_godzina(czysta):
        raise BladSprawy(f"godzina {godzina!r} — podaj GG:MM, np. 09:05")
    return czysta


def _sprawdz_pewnosc(pewnosc: str) -> str:
    if pewnosc not in PEWNOSCI:
        raise BladSprawy(f"nieznana pewność {pewnosc!r}; dozwolone: {', '.join(PEWNOSCI)}")
    return pewnosc


def _sprawdz_termin(termin: SpecTerminu, data: dt.date, kalendarz: Kalendarz) -> SpecTerminu:
    """Długość i podstawa muszą być poprawne, a koniec terminu w obsługiwanym zakresie dat."""
    podstawa = _niepusty("podstawa terminu", termin.podstawa)
    dlugosc = termin.dlugosc.strip()
    try:
        parsuj_dlugosc(dlugosc)
    except ValueError:
        raise BladSprawy(f"nieznana długość terminu {termin.dlugosc!r} — podaj np. 14d, 2t, 1m, 1r") from None
    try:
        koniec_terminu(data, dlugosc, kalendarz) + dt.timedelta(days=1)
    except (ValueError, OverflowError):
        raise BladSprawy(f"termin poza obsługiwanym zakresem dat (obsługiwane lata od {PIERWSZY_ROK}): "
                         f"{dlugosc} od {data}") from None
    return dataclasses.replace(termin, dlugosc=dlugosc, podstawa=podstawa)


ZADANIA_STARTOWE = (
    "Ustalić pełne dane rejestrowe drugiej strony",
    "Zebrać i zarchiwizować dowody (+ wersje tekstowe dla plików nietekstowych)",
    "Sprawdzić BAZĘ WIEDZY, uzupełnić brakujące przepisy",
    "Przygotować pismo",
    "Cross-check cytatów przed wysyłką",
    "Nadać i zarchiwizować potwierdzenie nadania",
)


def utworz_sprawe(tytul: str, strona_przeciwna: str, wlasciciel: str, w_imieniu: str | None = None) -> Sprawa:
    """Nowa sprawa w pamięci (bez zapisu): walidacja, stałe id, właściciel jako opiekun, a osoba,
    w której imieniu działa — jako klientka (strona sprawy)."""
    tytul = _niepusty("tytuł", tytul)
    strona_przeciwna = _niepusty("strona przeciwna", strona_przeciwna)
    wlasciciel = _niepusty("właściciel", wlasciciel)
    uczestnicy = [Uczestnik(wlasciciel, "opiekun")]
    if w_imieniu is not None:
        uczestnicy.append(Uczestnik(_niepusty("osoba, w której imieniu działasz", w_imieniu), "klientka"))
    return Sprawa(id=uuid.uuid4().hex, tytul=tytul, wlasciciel=wlasciciel, strona_przeciwna=strona_przeciwna,
                  uczestnicy=uczestnicy)


def _dopisz_zadania_startowe(s: Sprawa, od: dt.date) -> None:
    for opis in ZADANIA_STARTOWE:
        regula = REGULA_START_NADANIE if opis == ZADANIA_STARTOWE[-1] else REGULA_START
        s.zadania.append(Zadanie(kolejne_id("a", s.zadania), opis, od, regula=regula))


def nowa_sprawa(katalog: Path, tytul: str, strona_przeciwna: str, wlasciciel: str, *,
                w_imieniu: str | None = None, zadania_startowe: dt.date | None = None) -> Sprawa:
    """Odmawia w folderze starej teczki (index.md bez sprawa.json): nowa sprawa.json przykryłaby
    jej chronologię i terminy — taką teczkę przenosi migracja. `zadania_startowe` = data, od której
    są aktywne sześć kroków startowych (None = bez nich)."""
    if (katalog / "index.md").is_file() and not (katalog / PLIK_SPRAWY).exists():
        raise BladSprawy(f"{katalog}: jest index.md bez {PLIK_SPRAWY} — stary format — przenieś: /kruczek:migruj")
    sprawa = utworz_sprawe(tytul, strona_przeciwna, wlasciciel, w_imieniu)
    if zadania_startowe is not None:
        _dopisz_zadania_startowe(sprawa, zadania_startowe)
    zapisz_nowa(katalog, sprawa)
    return sprawa


def dopisz_watek(s: Sprawa, id: str, adresat: str) -> Watek:
    id = _niepusty("id wątku", id)
    adresat = _niepusty("adresat", adresat)
    if any(w.id == id for w in s.watki):
        raise BladSprawy(f"wątek {id!r} już istnieje")
    watek = Watek(id, adresat)
    s.watki.append(watek)
    return watek


def dodaj_watek(katalog: Path, id: str, adresat: str) -> None:
    zmien(katalog, lambda s: dopisz_watek(s, id, adresat))


def dopisz_zdarzenie(s: Sprawa, typ: str, data: dt.date, kalendarz: Kalendarz, dzis: dt.date, *,
                     watek: str | None = None, opis: str = "", dowody: Sequence[str] = (),
                     termin: SpecTerminu | None = None, dotyczy: str | None = None,
                     godzina: str | None = None, pewnosc: str | None = None) -> list[str]:
    """Dopisuje zdarzenie do sprawy w pamięci i stosuje reguły. Błąd = sprawa bez zmian
    (walidacja przed pierwszą mutacją; reguły walidują przed swoją)."""
    if typ not in TYPY_ZDARZEN:
        raise BladSprawy(f"nieznany typ zdarzenia {typ!r}; dozwolone: {', '.join(TYPY_ZDARZEN)}")
    if data > dzis:
        raise BladSprawy(f"data zdarzenia {data} jest w przyszłości — przyszłe rzeczy zapisz jako zadanie")
    if typ in ZDARZENIA_WATKU and watek is None:
        raise BladSprawy(f"zdarzenie {typ!r} wymaga wątku")
    if termin is not None and typ not in ("nadanie", *ZDARZENIA_PRZYCHODZACE):
        raise BladSprawy("termin podaje się przy nadaniu (termin adresata) albo przy odpowiedzi/wpływie (Twój termin)")
    if termin is not None:
        termin = _sprawdz_termin(termin, data, kalendarz)
    if dotyczy is not None:
        dotyczy = _niepusty("dotyczy", dotyczy)
    if godzina is not None:
        godzina = _sprawdz_godzine(godzina)
    if pewnosc is not None:
        pewnosc = _sprawdz_pewnosc(pewnosc)
    if watek is not None:
        s.znajdz_watek(watek)
    z = Zdarzenie(kolejne_id("z", s.zdarzenia), data, typ, opis, watek, list(dowody), godzina=godzina,
                  pewnosc=pewnosc)
    s.zdarzenia.append(z)
    try:
        return [f"zdarzenie {z.id}: {typ} {data.isoformat()}", *zastosuj(s, z, termin, kalendarz, dotyczy=dotyczy)]
    except BladSprawy:
        s.zdarzenia.remove(z)
        raise


def dodaj_zdarzenie(katalog: Path, typ: str, data: dt.date, kalendarz: Kalendarz, dzis: dt.date, *,
                    watek: str | None = None, opis: str = "", dowody: Sequence[str] = (),
                    termin: SpecTerminu | None = None, dotyczy: str | None = None,
                    godzina: str | None = None, pewnosc: str | None = None) -> list[str]:
    return zmien(katalog, lambda s: dopisz_zdarzenie(s, typ, data, kalendarz, dzis, watek=watek, opis=opis,
                                                     dowody=dowody, termin=termin, dotyczy=dotyczy,
                                                     godzina=godzina, pewnosc=pewnosc))


def dopisz_zadanie(s: Sprawa, opis: str, aktywne_od: dt.date, *, termin: dt.date | None = None,
                   watek: str | None = None) -> Zadanie:
    opis = _niepusty("opis", opis)
    if termin is not None and termin < aktywne_od:
        raise BladSprawy(f"termin zadania {termin} jest wcześniej niż aktywne od {aktywne_od}")
    if watek is not None:
        s.znajdz_watek(watek)
    zadanie = Zadanie(kolejne_id("a", s.zadania), opis, aktywne_od, termin=termin, watek=watek)
    s.zadania.append(zadanie)
    return zadanie


def dodaj_zadanie(katalog: Path, opis: str, aktywne_od: dt.date, *, termin: dt.date | None = None,
                  watek: str | None = None) -> Zadanie:
    return zmien(katalog, lambda s: dopisz_zadanie(s, opis, aktywne_od, termin=termin, watek=watek))


def zamknij_sprawe(katalog: Path, wynik: str) -> list[Zadanie]:
    """Zamyka sprawę i zwraca jej otwarte zadania z Twoim terminem — zamknięcie chowa je
    z przeglądu, więc wywołujący ma je pokazać użytkownikowi."""
    if wynik not in WYNIKI_SPRAWY:
        raise BladSprawy(f"nieznany wynik {wynik!r}; dozwolone: {', '.join(WYNIKI_SPRAWY)}")

    def zmiana(s: Sprawa) -> list[Zadanie]:
        if s.zamknieta:
            raise BladSprawy(f"sprawa już zamknięta ({s.wynik})")
        s.zamknieta, s.wynik = True, wynik
        return [a for a in s.zadania if a.zrobione is None and a.termin is not None]

    return zmien(katalog, zmiana)


def otworz_sprawe(katalog: Path) -> None:
    def zmiana(s: Sprawa) -> None:
        s.zamknieta, s.wynik = False, None

    zmien(katalog, zmiana)


class NieOstatnieZdarzenie(BladSprawy):
    """Cofnąć można tylko ostatnie zdarzenie — starsze poprawia się w rozmowie (popraw-zdarzenie)."""


class ZadanieJuzZrobione(BladSprawy):
    """Zadanie zamknięto wcześniej (np. w drugiej karcie strony albo w rozmowie z Claude)."""


class ZadanieNieZrobione(BladSprawy):
    """„Cofnij” zadania, które jest już otwarte."""


def _zadanie_o_opisie(s: Sprawa, zadanie_id: str, opis: str) -> Zadanie:
    """Zadanie, które widziała strona: to samo id i ten sam opis. Inaczej ktoś je w międzyczasie
    cofnął, a numer trafił do innego zadania."""
    zadanie = next((a for a in s.zadania if a.id == zadanie_id), None)
    if zadanie is None or zadanie.opis != opis:
        raise KonfliktRewizji(f"sprawa zmieniła się w międzyczasie: zadanie {zadanie_id} to już nie „{opis}”")
    return zadanie


def zaznacz_zrobione(s: Sprawa, zadanie_id: str, dzis: dt.date, *, oczekiwany_opis: str | None = None) -> Zadanie:
    """Oznacz zadanie jako zrobione w pamięci. `oczekiwany_opis` (strona): patrz _zadanie_o_opisie."""
    if oczekiwany_opis is not None:
        _zadanie_o_opisie(s, zadanie_id, oczekiwany_opis)
    zadanie = s.znajdz_zadanie(zadanie_id)
    if zadanie.zrobione is not None:
        raise ZadanieJuzZrobione(f"zadanie {zadanie_id} już zrobione ({zadanie.zrobione})")
    zadanie.zrobione = dzis
    return zadanie


def odznacz_zrobione(s: Sprawa, zadanie_id: str, *, oczekiwany_opis: str) -> Zadanie:
    """„Cofnij” po „Zrobione”: zadanie znów otwarte. Tylko zamknięte ręcznie — zamknięte
    zdarzeniem (np. doręczeniem) otwiera się, cofając to zdarzenie."""
    zadanie = _zadanie_o_opisie(s, zadanie_id, oczekiwany_opis)
    if zadanie.zrobione is None:
        raise ZadanieNieZrobione(f"zadanie {zadanie_id} nie jest zrobione")
    if zadanie.zamkniete_przez is not None:
        raise BladSprawy(f"zadanie {zadanie_id} zamknęło zdarzenie {zadanie.zamkniete_przez} — cofnij to zdarzenie")
    zadanie.zrobione = None
    return zadanie


def zapisz_doreczenie(s: Sprawa, zadanie_id: str, data: dt.date, kalendarz: Kalendarz, dzis: dt.date, *,
                      oczekiwany_opis: str) -> tuple[Zdarzenie, list[str]]:
    """Doręczenie wpisane przy zadaniu „sprawdź datę doręczenia”: wątek i nadanie bierze z zadania,
    więc nie trzeba wskazywać, którego pisma dotyczy. Zwraca nowe zdarzenie i komunikaty reguł."""
    zadanie = _zadanie_o_opisie(s, zadanie_id, oczekiwany_opis)
    if zadanie.regula != REGULA_DORECZENIE or zadanie.zdarzenie_id is None:
        raise BladSprawy(f"zadanie {zadanie_id} nie jest sprawdzeniem doręczenia")
    if zadanie.zrobione is not None:
        raise ZadanieJuzZrobione(f"zadanie {zadanie_id} już zrobione ({zadanie.zrobione})")
    nadanie = s.znajdz_zdarzenie(zadanie.zdarzenie_id)
    adresat = s.znajdz_watek(zadanie.watek).adresat if zadanie.watek else "adresat"
    komunikaty = dopisz_zdarzenie(s, "doreczenie", data, kalendarz, dzis, watek=zadanie.watek,
                                  opis=f"{adresat}: pismo nadane {nadanie.data:%d.%m.%Y}",
                                  dotyczy=zadanie.zdarzenie_id)
    return s.zdarzenia[-1], komunikaty


def oznacz_zrobione(katalog: Path, zadanie_id: str, dzis: dt.date) -> Zadanie:
    return zmien(katalog, lambda s: zaznacz_zrobione(s, zadanie_id, dzis))


def przelicz_sprawe(katalog: Path, kalendarz: Kalendarz) -> list[str]:
    return zmien(katalog, lambda s: przelicz(s, kalendarz))


def popraw_zdarzenie(katalog: Path, zdarzenie_id: str, kalendarz: Kalendarz, dzis: dt.date, *,
                     data: dt.date | None = None, opis: str | None = None, godzina: str | None = None,
                     pewnosc: str | None = None, dowody: Sequence[str] | None = None) -> list[str]:
    """Poprawia błędnie wpisane zdarzenie. Pusty napis w godzinie/pewności czyści pole.
    Typu i wątku nie zmienia — to cofnij-zdarzenie i wpis od nowa."""
    if all(v is None for v in (data, opis, godzina, pewnosc, dowody)):
        raise BladSprawy("nic do poprawienia — podaj --data, --opis, --godzina, --pewnosc albo --dowod")
    if data is not None and data > dzis:
        raise BladSprawy(f"data zdarzenia {data} jest w przyszłości")
    if godzina:
        godzina = _sprawdz_godzine(godzina)
    if pewnosc:
        pewnosc = _sprawdz_pewnosc(pewnosc)

    def zmiana(s: Sprawa) -> list[str]:
        z = s.znajdz_zdarzenie(zdarzenie_id)
        try:
            komunikaty = zmien_date(s, z, data, kalendarz) if data is not None and data != z.data else []
        except (ValueError, OverflowError):
            raise BladSprawy(f"termin poza obsługiwanym zakresem dat (obsługiwane lata od {PIERWSZY_ROK}): "
                             f"{zdarzenie_id} z datą {data}") from None
        if opis is not None:
            z.opis = opis
        if godzina is not None:
            z.godzina = godzina or None
        if pewnosc is not None:
            z.pewnosc = pewnosc or None
        if dowody is not None:
            z.dowody = list(dowody)
        return komunikaty or [f"{z.id}: poprawiono"]

    return zmien(katalog, zmiana)


def wycofaj_zdarzenie(s: Sprawa, zdarzenie_id: str, kalendarz: Kalendarz, *,
                      oczekiwane: tuple[str, dt.date] | None = None) -> list[str]:
    """Cofnięcie ostatniego zdarzenia w pamięci. `oczekiwane` (strona) = (typ, data) zdarzenia,
    które pokazał toast — inaczej numer mógł trafić do innego zdarzenia po cofnięciu w CLI."""
    if oczekiwane is not None:
        z = next((x for x in s.zdarzenia if x.id == zdarzenie_id), None)
        if z is None or (z.typ, z.data) != oczekiwane:
            raise KonfliktRewizji(f"sprawa zmieniła się w międzyczasie: zdarzenie {zdarzenie_id} to już nie "
                                  f"{oczekiwane[0]} z {oczekiwane[1].isoformat()}")
    z = s.znajdz_zdarzenie(zdarzenie_id)
    if z is not s.zdarzenia[-1]:
        raise NieOstatnieZdarzenie(f"cofnąć można tylko ostatnie wpisane zdarzenie ({s.zdarzenia[-1].id}); "
                                   f"starsze popraw przez popraw-zdarzenie")
    return cofnij(s, z, kalendarz)


def cofnij_zdarzenie(katalog: Path, zdarzenie_id: str, kalendarz: Kalendarz) -> list[str]:
    return zmien(katalog, lambda s: wycofaj_zdarzenie(s, zdarzenie_id, kalendarz))
