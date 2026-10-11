"""Migracja starej teczki (index.md bez sprawa.json) na sprawa.json.

Model czyta stary index.md i pisze propozycję w JSON; kod ją waliduje, odtwarza zdarzenia
w kolejności dat tymi samymi regułami co CLI (w pamięci, bez zapisu) i pokazuje podsumowanie.
Zapis dopiero po akceptacji, z kopią starego index.md. Wolny tekst index.md zostaje — stara
tabela chronologii też (pod nagłówkiem „sprzed migracji”).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.model import WYNIKI_SPRAWY, BladSprawy, Sprawa, kolejne_id
from kruczek_core.operacje import (
    dopisz_watek,
    dopisz_zadanie,
    dopisz_zdarzenie,
    utworz_sprawe,
)
from kruczek_core.reguly import REGULA_DORECZENIE, REGULA_ODPOWIEDZ, SpecTerminu

_POLA = {"tytul", "strona_przeciwna", "wlasciciel", "zamknieta", "wynik", "watki", "zdarzenia", "zadania"}
_POLA_WATKU = {"id", "adresat"}
_POLA_ZDARZENIA = {"klucz", "data", "godzina", "typ", "opis", "watek", "dowody", "pewnosc", "termin", "dotyczy"}
_POLA_TERMINU = {"dlugosc", "podstawa"}
_POLA_ZADANIA = {"opis", "aktywne_od", "termin", "watek"}
_NAGLOWEK_CHRONOLOGII = re.compile(r"^##[ \t]+(?:\d+\.[ \t]*)?Chronologia[ \t]*\r?$", re.MULTILINE | re.IGNORECASE)
_ZNACZNIK_CHRONOLOGII = "<!-- kruczek:chronologia -->"
_NAGLOWEK_ARCHIWALNY = "### Chronologia sprzed migracji (archiwalna — nie dopisuj)"
_NAGLOWEK_SPRAWY = "# sprawa:"
_DOPISEK = " (sprzed migracji)"
_NAGLOWEK_TODO = re.compile(r"^##[ \t]+(?:\d+\.[ \t]*)?TODO[ \t]*$", re.IGNORECASE)
# Wiersz tabeli nagłówka: grupa 1 — treść, grupa 2 — końcowy „|” z otaczającymi spacjami.
_WIERSZ_NAGLOWKA = re.compile(r"^(\|[ \t]*\*\*(?:Status|Najbliższy termin)\*\*[ \t]*\|.*?)([ \t]*\|?[ \t]*)$",
                              re.IGNORECASE)
_ID_ZDARZENIA = re.compile(r"\bz\d+\b")
_STARE_ZADANIA_DNI = 30


@dataclass(frozen=True)
class Podsumowanie:
    sprawa: Sprawa
    komunikaty: list[str]
    ostrzezenia: list[str]


def wczytaj_propozycje(plik: Path) -> dict[str, Any]:
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BladSprawy(f"{plik}: uszkodzony JSON (linia {e.lineno}): {e.msg}") from None
    except (UnicodeDecodeError, OSError) as e:
        raise BladSprawy(f"{plik}: nie można odczytać propozycji: {e}") from None
    if not isinstance(dane, dict):
        raise BladSprawy(f"{plik}: propozycja musi być obiektem JSON")
    return dane


def _obiekt(co: str, v: Any, dozwolone: set[str]) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise BladSprawy(f"{co}: oczekiwano obiektu JSON, jest {v!r}")
    nadmiar = set(v) - dozwolone
    if nadmiar:
        raise BladSprawy(f"{co}: nieznane pola {', '.join(sorted(nadmiar))}")
    return v


def _lista(co: str, v: Any) -> list[Any]:
    if v is None:
        return []
    if not isinstance(v, list):
        raise BladSprawy(f"{co}: oczekiwano listy, jest {v!r}")
    return v


def _napis(co: str, v: Any) -> str | None:
    if v is not None and not isinstance(v, str):
        raise BladSprawy(f"{co}: oczekiwano napisu albo null, jest {v!r}")
    return v


def _data(co: str, tekst: Any) -> dt.date:
    try:
        return dt.date.fromisoformat(tekst)
    except (TypeError, ValueError):
        raise BladSprawy(f"{co}: zła data {tekst!r} — oczekiwano RRRR-MM-DD") from None


@dataclass(frozen=True)
class _Wpis:
    """Zdarzenie z propozycji po sprawdzeniu kształtu, przed odtworzeniem regułami."""
    nr: int
    data: dt.date
    pola: dict[str, Any]
    termin: SpecTerminu | None
    dowody: list[str]


def _wpis(nr: int, surowy: Any) -> _Wpis:
    co = f"zdarzenie {nr}"
    z = _obiekt(co, surowy, _POLA_ZDARZENIA)
    for pole in ("klucz", "godzina", "typ", "opis", "watek", "pewnosc", "dotyczy"):
        _napis(f"{co}: {pole}", z.get(pole))
    dowody = _lista(f"{co}: dowody", z.get("dowody"))
    if not all(isinstance(d, str) for d in dowody):
        raise BladSprawy(f"{co}: dowody — oczekiwano listy ścieżek (napisów)")
    termin = None
    if z.get("termin") is not None:
        t = _obiekt(f"{co}: termin", z["termin"], _POLA_TERMINU)
        termin = SpecTerminu(_napis(f"{co}: termin.dlugosc", t.get("dlugosc")) or "",
                             _napis(f"{co}: termin.podstawa", t.get("podstawa")) or "")
    return _Wpis(nr, _data(co, z.get("data")), z, termin, dowody)


def _kolejnosc_odtwarzania(wpisy: list[_Wpis]) -> list[_Wpis]:
    """Po datach; w obrębie dnia kolejność z propozycji (godzina nie zmienia kolejności), ale
    zdarzenie z `dotyczy` zawsze po zdarzeniu z tego samego dnia, którego dotyczy. `dotyczy`
    wskazujące późniejszą datę albo cykl zostają na swoim miejscu — błąd zgłosi odtwarzanie."""
    wynik: list[_Wpis] = []
    for data in sorted({w.data for w in wpisy}):
        dzien = sorted((w for w in wpisy if w.data == data), key=lambda w: w.nr)
        klucze_dnia = {w.pola.get("klucz") for w in dzien} - {None}
        umieszczone: set[str] = set()
        czekajace: list[_Wpis] = []
        for w in dzien:
            dotyczy = w.pola.get("dotyczy")
            if dotyczy in klucze_dnia and dotyczy not in umieszczone:
                czekajace.append(w)
                continue
            kolejka = [w]
            while kolejka:
                biezacy = kolejka.pop(0)
                wynik.append(biezacy)
                if biezacy.pola.get("klucz") is not None:
                    umieszczone.add(biezacy.pola["klucz"])
                gotowe = [c for c in czekajace if c.pola.get("dotyczy") in umieszczone]
                czekajace = [c for c in czekajace if c not in gotowe]
                kolejka += gotowe
        wynik += czekajace
    return wynik


def _po_kluczach(komunikat: str, nazwy: dict[str, str]) -> str:
    """Id zdarzeń (z1, z2…) w komunikacie reguł → klucze z propozycji, a wskazówka o --dotyczy →
    jak to zapisać w propozycji.

    >>> print(_po_kluczach("czeka: a (z1); b (z2) — --dotyczy <id>", {"z1": "'r'", "z2": "'k'"}))
    czeka: a ('r'); b ('k') — --dotyczy <id> — w propozycji ustaw "dotyczy": "<klucz nadania>"
    """
    wynik = _ID_ZDARZENIA.sub(lambda m: nazwy.get(m.group(0), m.group(0)), komunikat)
    if "--dotyczy" in wynik:
        wynik += ' — w propozycji ustaw "dotyczy": "<klucz nadania>"'
    return wynik


def zbuduj_sprawe(propozycja: dict[str, Any], kalendarz: Kalendarz, dzis: dt.date, wlasciciel: str) -> Podsumowanie:
    """Propozycja → Sprawa w pamięci. Nic nie zapisuje. Błąd wskazuje numer zdarzenia z propozycji."""
    _obiekt("propozycja", propozycja, _POLA)
    zamknieta = propozycja.get("zamknieta")
    if zamknieta is not None and not isinstance(zamknieta, bool):
        raise BladSprawy(f"propozycja: zamknieta {zamknieta!r} — podaj true albo false")
    wynik = propozycja.get("wynik")
    if zamknieta and wynik not in WYNIKI_SPRAWY:
        raise BladSprawy(f"propozycja: wynik {wynik!r} — dozwolone: {', '.join(WYNIKI_SPRAWY)}")
    if not zamknieta and wynik is not None:
        raise BladSprawy(f'propozycja: wynik {wynik!r} podaje się tylko przy "zamknieta": true')
    try:
        s = utworz_sprawe(_napis("tytul", propozycja.get("tytul")) or "",
                          _napis("strona_przeciwna", propozycja.get("strona_przeciwna")) or "",
                          _napis("wlasciciel", propozycja.get("wlasciciel")) or wlasciciel)
    except BladSprawy as e:
        raise BladSprawy(f"propozycja: {e}") from None

    for nr, surowy in enumerate(_lista("wątki", propozycja.get("watki")), start=1):
        w = _obiekt(f"wątek {nr}", surowy, _POLA_WATKU)
        try:
            dopisz_watek(s, _napis(f"wątek {nr}: id", w.get("id")) or "",
                         _napis(f"wątek {nr}: adresat", w.get("adresat")) or "")
        except BladSprawy as e:
            raise BladSprawy(f"wątek {nr}: {e}") from None

    wpisy = [_wpis(nr, z) for nr, z in enumerate(_lista("zdarzenia", propozycja.get("zdarzenia")), start=1)]
    widziane: set[str] = set()
    for w in wpisy:
        klucz = w.pola.get("klucz")
        if klucz is not None and klucz in widziane:
            raise BladSprawy(f"zdarzenie {w.nr}: klucz {klucz!r} użyty dwa razy")
        if klucz is not None:
            widziane.add(klucz)

    klucze: dict[str, str] = {}  # klucz z propozycji → id zdarzenia
    nazwy: dict[str, str] = {}  # id zdarzenia → jak je nazwać w komunikacie
    komunikaty: list[str] = []
    for w in _kolejnosc_odtwarzania(wpisy):
        z = w.pola
        opis = f"zdarzenie {w.nr} ({w.data.isoformat()} {z.get('typ')})"
        dotyczy = z.get("dotyczy")
        if dotyczy is not None and dotyczy not in klucze:
            raise BladSprawy(f"{opis}: dotyczy {dotyczy!r} — nie ma wcześniejszego zdarzenia o tym kluczu")
        klucz = z.get("klucz")
        nazwy[kolejne_id("z", s.zdarzenia)] = repr(klucz) if klucz is not None else f"zdarzenie {w.nr} bez klucza"
        try:
            komunikaty += dopisz_zdarzenie(
                s, z.get("typ") or "", w.data, kalendarz, dzis,
                watek=z.get("watek"), opis=z.get("opis") or "", dowody=w.dowody, termin=w.termin,
                dotyczy=klucze[dotyczy] if dotyczy is not None else None,
                godzina=z.get("godzina"), pewnosc=z.get("pewnosc"),
            )
        except BladSprawy as e:
            raise BladSprawy(f"{opis}: {_po_kluczach(str(e), nazwy)}") from None
        if klucz is not None:
            klucze[klucz] = s.zdarzenia[-1].id

    for nr, surowe in enumerate(_lista("zadania", propozycja.get("zadania")), start=1):
        co = f"zadanie {nr}"
        a = _obiekt(co, surowe, _POLA_ZADANIA)
        aktywne_od = _data(co, a["aktywne_od"]) if a.get("aktywne_od") is not None else dzis
        termin = _data(co, a["termin"]) if a.get("termin") is not None else None
        try:
            dopisz_zadanie(s, _napis(f"{co}: opis", a.get("opis")) or "", aktywne_od,
                           termin=termin, watek=_napis(f"{co}: watek", a.get("watek")))
        except BladSprawy as e:
            raise BladSprawy(f"{co}: {e}") from None

    if zamknieta:
        s.zamknieta, s.wynik = True, wynik
    return Podsumowanie(s, komunikaty, _ostrzezenia(s, dzis))


def _ostrzezenia(s: Sprawa, dzis: dt.date) -> list[str]:
    wyniki = []
    stare = [a for a in s.zadania if a.zrobione is None and (dzis - a.aktywne_od).days > _STARE_ZADANIA_DNI]
    if stare and not s.zamknieta:
        wyniki.append(f"{len(stare)} zadań aktywnych od ponad {_STARE_ZADANIA_DNI} dni "
                      f"({', '.join(a.id for a in stare)}) — po migracji oznacz nieaktualne jako zrobione")
    czekajace_nadania = {a.zdarzenie_id for a in s.zadania
                         if a.zrobione is None and a.regula in (REGULA_DORECZENIE, REGULA_ODPOWIEDZ)}
    for t in s.terminy:
        if t.szacunek and t.data_konca < dzis and t.od_zdarzenia in czekajace_nadania:
            wyniki.append(f"termin {t.id} liczony od nadania i już minął — wpisz doręczenie, jeśli znasz datę")
    return wyniki


def tytul_z_naglowka(tekst: str) -> str | None:
    """Tytuł z pierwszej niepustej linii „# SPRAWA: …” (wielkość liter bez znaczenia).

    >>> tytul_z_naglowka("\\n# Sprawa: Reklamacja\\n")
    'Reklamacja'
    """
    for linia in tekst.lstrip("\ufeff").splitlines():
        if linia.strip():
            linia = linia.strip()
            if linia[:len(_NAGLOWEK_SPRAWY)].casefold() == _NAGLOWEK_SPRAWY:
                return linia[len(_NAGLOWEK_SPRAWY):].strip() or None
            return None
    return None


def wstaw_znaczniki_chronologii(tekst: str) -> tuple[str, bool]:
    """Pod starym nagłówkiem „Chronologia” wstawia znaczniki bloku generowanego, a starą tabelę
    zostawia pod nagłówkiem „sprzed migracji”. Nagłówek zostaje bez zmian (co do znaku). Bez
    nagłówka albo gdy znaczniki już są — bez zmian.

    >>> wstaw_znaczniki_chronologii("## Chronologia\\n| a |\\n")[0].splitlines()[2]
    '<!-- kruczek:chronologia -->'
    """
    if _ZNACZNIK_CHRONOLOGII in tekst:
        return tekst, False
    m = _NAGLOWEK_CHRONOLOGII.search(tekst)
    if m is None:
        return tekst, False
    crlf = m.group(0).endswith("\r")
    nl = "\r\n" if crlf else "\n"
    wstawka = nl.join([m.group(0).removesuffix("\r"), "", _ZNACZNIK_CHRONOLOGII, "<!-- /kruczek:chronologia -->",
                       "", _NAGLOWEK_ARCHIWALNY]) + ("\r" if crlf else "")
    return tekst[:m.start()] + wstawka + tekst[m.end():], True


def oznacz_sprzed_migracji(tekst: str) -> str:
    """Stare `## … TODO` i wiersze nagłówka „Status” / „Najbliższy termin” dostają dopisek
    „(sprzed migracji)” — od migracji aktualne są bloki generowane z sprawa.json. Żadna linia
    nie znika ani nie zmienia się poza dopiskiem; ponowne wywołanie niczego nie dokłada.

    >>> oznacz_sprzed_migracji("| **Status** | w toku |\\n## 5. TODO\\n")
    '| **Status** | w toku (sprzed migracji) |\\n## 5. TODO (sprzed migracji)\\n'
    """
    linie = tekst.splitlines(keepends=True)
    for i, linia in enumerate(linie):
        tresc = linia.rstrip("\r\n")
        if _DOPISEK in tresc:
            continue
        if _NAGLOWEK_TODO.match(tresc):
            nowa = tresc.rstrip() + _DOPISEK + tresc[len(tresc.rstrip()):]
        else:
            m = _WIERSZ_NAGLOWKA.match(tresc)
            if m is None:
                continue
            nowa = m.group(1) + _DOPISEK + m.group(2)
        linie[i] = nowa + linia[len(tresc):]
    return "".join(linie)


def kopia_zapasowa(katalog: Path, dzis: dt.date) -> Path | None:
    """Kopia index.md w ROBOCZE/ (bajt w bajt, sprawdzona; z datą; istniejącej nie nadpisuje)."""
    index = katalog / "index.md"
    if not index.exists():
        return None
    (katalog / "ROBOCZE").mkdir(exist_ok=True)
    cel = katalog / "ROBOCZE" / f"index.przed-migracja-{dzis.isoformat()}.md"
    n = 2
    while cel.exists():
        cel = katalog / "ROBOCZE" / f"index.przed-migracja-{dzis.isoformat()}-{n}.md"
        n += 1
    shutil.copy2(index, cel)
    if cel.read_bytes() != index.read_bytes():
        raise BladSprawy(f"{cel}: kopia index.md różni się od oryginału — nic nie zapisano")
    return cel
