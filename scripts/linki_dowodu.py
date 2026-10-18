#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""linki_dowodu.py — linki z dowodu z rekomendacją, czy je archiwizować; reguły w kodzie, bez modelu.

Link w wiadomości od drugiej strony (spam, mailing) bywa spersonalizowany: niesie adres odbiorcy wprost,
jego imię i nazwisko albo nazwę jego domeny w slugu, adres w tokenie (base64, hex) albo krótki identyfikator
w ścieżce lub nazwie hosta, albo jest linkiem wypisania. Pobranie takiego linku potwierdza nadawcy, że
skrzynka działa, a snapshot w Wayback Machine publikuje adres. Dlatego `ARCHIWIZUJ` wymaga pozytywnego
kształtu (ścieżka z samych słów, bez parametrów, fragmentu i cyfr w nazwie hosta), a wszystko inne jest co
najmniej `ZAPYTAJ`. Skrypt wypisuje JSON o stałym kształcie:

    {"plik": str, "odbiorcy": [str], "nazwy": [str],
     "linki": [{"url", "domena", "zrodla": [str], "rekomendacja", "powody": [str], "czysty_url": str | null}],
     "domeny": [{"domena", "strona_glowna", "rekomendacja", "powody": [str]}],
     "do_archiwizacji": [str]}

rekomendacja — najostrzejsza wynikająca z powodów:
    ADRES_ODBIORCY, TOKEN_Z_ADRESEM, LINK_WYPISANIA, ZASOB_OSADZONY, HOST_LOKALNY       → NIE_ARCHIWIZUJ
    DANE_ODBIORCY, TOKEN_ZAKODOWANY, IDENTYFIKATOR, PARAMETRY, HOST_NIETYPOWY           → ZAPYTAJ
    SAME_SLOWA                                                                          → ARCHIWIZUJ
DANE_ODBIORCY (imię, nazwisko, nazwa domeny odbiorcy) to dopasowanie przybliżone — zwykłe słowo bywa częścią
nazwiska — więc decyduje użytkownik, a nie reguła. HOST_LOKALNY (localhost, host bez kropki, .local, adres
prywatny) — pobranie trafiłoby do sieci użytkownika; HOST_NIETYPOWY — publiczny adres IP albo jawny port.
Ten sam URL z kilku miejsc pliku (np. stopka i nagłówek List-Unsubscribe) to jeden wpis: źródła i teksty
linku są sumowane, więc decyduje najostrzejsze. Strona główna domeny (`https://<domena>/`) dostaje ocenę
tymi samymi regułami — nazwa hosta też potrafi nieść identyfikator.

czysty_url — adres strony bez identyfikatora odbiorcy, gdy da się go wziąć z samego linku: ten sam adres bez
parametrów i fragmentu (`?utm_source=…`, `?e=<adres>`, token w parametrze), jeśli zostaje link z samych słów,
który nie jest końcówką przekierowania (`/r`, `/ls/click`, `/redirect.php`). Link z pełnym adresem w parametrze
(`?url=https%3A%2F%2F…`) to przekierowanie: czysty adres to wtedy strona docelowa, nigdy ścieżka trackera. `null` przy linku `ARCHIWIZUJ`, linku wypisania, zasobie osadzonym, danych logowania
w adresie i gdy strony bez identyfikatora z linku nie widać. do_archiwizacji — bez powtórzeń: linki
`ARCHIWIZUJ` i wszystkie `czysty_url`; te adresy można zarchiwizować, także w Wayback, bez pytania.

Użycie:
    linki_dowodu.py <plik.eml|.html|.htm|.txt|.md> [--odbiorca ADRES ...] [--nazwa "IMIĘ NAZWISKO" ...]
Dla .eml odbiorcy i ich nazwy z To, Cc, Delivered-To i X-Original-To; linki z części HTML (z rodzajem zasobu
i tekstem linku), części tekstowej i nagłówka List-Unsubscribe; `domeny` obejmują po domenach linków także domeny
adresów From, Reply-To, Return-Path i Sender (Received pomijamy). Dla .html/.htm — zasoby jak w części HTML
maila; dla .txt/.md — linki z tekstu. Kod wyjścia: 0 = ocenione, 2 = brak pliku albo nieobsługiwany typ.
"""

import argparse
import ipaddress
import json
import re
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from email.utils import getaddresses
from enum import StrEnum
from pathlib import Path
from urllib.parse import SplitResult, parse_qsl, unquote, urlsplit, urlunsplit

from eml_forensics_logika import (
    decode_tokens,
    extract_bodies,
    extract_html_resources,
    load_message,
)


class Rekomendacja(StrEnum):
    ARCHIWIZUJ = "ARCHIWIZUJ"
    ZAPYTAJ = "ZAPYTAJ"
    NIE_ARCHIWIZUJ = "NIE_ARCHIWIZUJ"


class Powod(StrEnum):
    ADRES_ODBIORCY = "ADRES_ODBIORCY"
    DANE_ODBIORCY = "DANE_ODBIORCY"
    TOKEN_Z_ADRESEM = "TOKEN_Z_ADRESEM"
    LINK_WYPISANIA = "LINK_WYPISANIA"
    ZASOB_OSADZONY = "ZASOB_OSADZONY"
    TOKEN_ZAKODOWANY = "TOKEN_ZAKODOWANY"
    IDENTYFIKATOR = "IDENTYFIKATOR"
    PARAMETRY = "PARAMETRY"
    HOST_LOKALNY = "HOST_LOKALNY"
    HOST_NIETYPOWY = "HOST_NIETYPOWY"
    SAME_SLOWA = "SAME_SLOWA"


SKUTEK = {
    Powod.ADRES_ODBIORCY: Rekomendacja.NIE_ARCHIWIZUJ,
    Powod.DANE_ODBIORCY: Rekomendacja.ZAPYTAJ,
    Powod.TOKEN_Z_ADRESEM: Rekomendacja.NIE_ARCHIWIZUJ,
    Powod.LINK_WYPISANIA: Rekomendacja.NIE_ARCHIWIZUJ,
    Powod.ZASOB_OSADZONY: Rekomendacja.NIE_ARCHIWIZUJ,
    Powod.TOKEN_ZAKODOWANY: Rekomendacja.ZAPYTAJ,
    Powod.IDENTYFIKATOR: Rekomendacja.ZAPYTAJ,
    Powod.PARAMETRY: Rekomendacja.ZAPYTAJ,
    Powod.HOST_LOKALNY: Rekomendacja.NIE_ARCHIWIZUJ,
    Powod.HOST_NIETYPOWY: Rekomendacja.ZAPYTAJ,
    Powod.SAME_SLOWA: Rekomendacja.ARCHIWIZUJ,
}
OD_NAJOSTRZEJSZEJ = (Rekomendacja.NIE_ARCHIWIZUJ, Rekomendacja.ZAPYTAJ, Rekomendacja.ARCHIWIZUJ)
URL = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.IGNORECASE)
ADRES = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Segment ścieżki, który jest słowem albo slugiem bez cyfr (małe litery, myślnik, podkreślnik), z opcjonalnym
# rozszerzeniem strony. Wszystko inne (cyfry, wielkie litery, krótkie kody) może być identyfikatorem odbiorcy.
SLOWO = re.compile(r"[a-z]+(?:[-_][a-z]+)*(?:\.(?:html?|php|pdf))?")
# Link wypisania albo ustawień subskrypcji — w ścieżce, parametrach albo tekście linku; kliknięcie potwierdza adres.
WYPISANIE = re.compile(r"unsub|wypis|rezygn|opt-?out|preferenc|subskrypc|subscription", re.IGNORECASE)
# Źródła, z których link otwiera dopiero człowiek; reszta (img, script, css…) pobiera się sama przy otwarciu.
KLIKANE = frozenset({"a", "tekst", "List-Unsubscribe"})
HTML = frozenset({".html", ".htm"})
TEKST = frozenset({".txt", ".md"})
NAGLOWKI_ODBIORCOW = ("To", "Cc", "Delivered-To", "X-Original-To")
# Nagłówki nadawcy — ich domeny też trafiają do `domeny` (Received pomijamy: to ślad serwerów pośredniczących).
NAGLOWKI_NADAWCY = ("From", "Reply-To", "Return-Path", "Sender")
MIN_CZESC_LOKALNA = 4
# Część imienia lub nazwiska i etykieta domeny odbiorcy liczą się od 5 liter — krótsze dają za dużo trafień.
MIN_CZESC_NAZWY = 5
# Domeny poczty darmowej — ich nazwa nie mówi nic o odbiorcy.
POCZTA_DARMOWA = frozenset({"gmail", "googlemail", "outlook", "hotmail", "live", "yahoo", "icloud", "proton",
                            "protonmail", "gmx", "onet", "interia", "poczta", "tlen", "op", "wp", "o2"})
# Bez czystego adresu: sama ścieżka linku wypisania bywa poleceniem wypisania, a zasób osadzony to piksel.
BEZ_CZYSTEGO = frozenset({Powod.LINK_WYPISANIA, Powod.ZASOB_OSADZONY})
# Końcówki przekierowań — bez tokenu nie pokażą strony docelowej (krótsze niż 3 znaki też: /r, /c, /ls).
PRZEKIEROWANIE = frozenset({"click", "clicks", "track", "tracking", "redirect", "redir", "link", "links", "out", "go"})
# Nazwy sieci lokalnej — link do nich z wrogiego pliku to zapytanie z Maca użytkownika do jego routera czy usług.
LOKALNE_SUFIKSY = (".local", ".localhost", ".lan", ".internal", ".home.arpa")
# Host z samych liczb (dziesiętnych albo szesnastkowych) — curl rozwiąże `127.1` czy `0x7f.1` na 127.0.0.1.
HOST_LICZBOWY = re.compile(r"(?:0x[0-9a-f]+|\d+)(?:\.(?:0x[0-9a-f]+|\d+)){0,3}")


@dataclass(frozen=True)
class Ocena:
    url: str
    domena: str
    zrodla: tuple[str, ...]
    rekomendacja: Rekomendacja
    powody: tuple[Powod, ...]


def _rozkoduj(tekst: str) -> str:
    """Kodowanie procentowe zdjęte do skutku — adres bywa kodowany dwa razy.

    >>> _rozkoduj("e=osoba.testowa%2540odbiorca.example")
    'e=osoba.testowa@odbiorca.example'
    """
    for _ in range(5):
        nowy = unquote(tekst)
        if nowy == tekst:
            break
        tekst = nowy
    return tekst


def _splaszcz(tekst: str) -> str:
    return re.sub(r"[.\-_+]", "", tekst.lower())


def _bez_znakow(tekst: str) -> str:
    """Polskie i inne znaki diakrytyczne zamienione na łacińskie, jak w slugach adresów.

    >>> _bez_znakow("Zażółcia Gęślowska")
    'Zazolcia Geslowska'
    """
    tekst = tekst.replace("ł", "l").replace("Ł", "L")
    return "".join(z for z in unicodedata.normalize("NFKD", tekst) if not unicodedata.combining(z))


def _niesie_adres(tekst: str, odbiorcy: Sequence[str]) -> bool:
    """Adres odbiorcy wprost albo jego część lokalna (≥ 4 znaki), także zapisana z innymi separatorami.

    >>> _niesie_adres("https://firma-x.example/dla/osoba-testowa", ["osoba.testowa@odbiorca.example"])
    True
    >>> _niesie_adres("https://firma-x.example/regulamin", ["osoba.testowa@odbiorca.example"])
    False
    """
    rozkodowany = _rozkoduj(tekst).lower()
    plaski = _splaszcz(rozkodowany)
    for adres in odbiorcy:
        lokalna = _splaszcz(adres.split("@", 1)[0])
        if adres.lower() in rozkodowany or (len(lokalna) >= MIN_CZESC_LOKALNA and lokalna in plaski):
            return True
    return False


def _slady(nazwy: Sequence[str], odbiorcy: Sequence[str]) -> list[str]:
    """Spłaszczone ślady odbiorcy poza adresem: imię i nazwisko razem w obu kolejnościach, każda ich część
    od 5 liter (z polskimi znakami i bez nich) i etykieta domeny odbiorcy spoza poczty darmowej.

    >>> _slady(["Jan Testowy"], ["jan@studio-testowe.example", "jan@outlook.example"])
    ['jantestowy', 'testowyjan', 'testowy', 'studiotestowe']
    """
    slady: list[str] = []
    for nazwa in nazwy:
        for wariant in dict.fromkeys((nazwa.lower(), _bez_znakow(nazwa).lower())):
            czesci = [c for c in re.split(r"[\s.\-_+,]+", wariant) if c]
            if len(czesci) >= 2:
                slady += ["".join(czesci), "".join(reversed(czesci))]
            slady += [c for c in czesci if len(c) >= MIN_CZESC_NAZWY]
    for adres in odbiorcy:
        etykiety = adres.rsplit("@", 1)[-1].lower().split(".")[:-1]
        slady += [_splaszcz(e) for e in etykiety if e not in POCZTA_DARMOWA and len(_splaszcz(e)) >= MIN_CZESC_NAZWY]
    return list(dict.fromkeys(slady))


def _niesie_dane(tekst: str, slady: Sequence[str]) -> bool:
    """Któryś ślad odbiorcy w tekście spłaszczonym tak samo — także bez polskich znaków.

    >>> _niesie_dane("https://firma-x.example/dla/jan-testowy", ["jantestowy"])
    True
    """
    rozkodowany = _rozkoduj(tekst).lower()
    plaskie = {_splaszcz(rozkodowany), _splaszcz(_bez_znakow(rozkodowany))}
    return any(s in p for s in slady for p in plaskie)


def _ma_identyfikator(czesci: SplitResult) -> bool:
    """Cyfra w nazwie hosta albo segment ścieżki, który nie jest słowem.

    >>> _ma_identyfikator(urlsplit("https://firma-x.example/o-firmie/regulamin.html"))
    False
    >>> [_ma_identyfikator(urlsplit(u)) for u in ("https://firma-x.example/c/Ab3xK9q",
    ...     "https://firma-x.example/l/user-8812734", "https://x7k2p9q4.sledzenie.example/")]
    [True, True, True]
    """
    etykiety = (czesci.hostname or "").split(".")[:-1]
    segmenty = [s for s in czesci.path.split("/") if s]
    return any(c.isdigit() for e in etykiety for c in e) or not all(SLOWO.fullmatch(s) for s in segmenty)


def _host(czesci: SplitResult) -> Powod | None:
    """HOST_LOKALNY dla sieci lokalnej, HOST_NIETYPOWY dla publicznego adresu IP albo jawnego portu.

    >>> [_host(urlsplit(u)).value for u in ("http://localhost:8080/shutdown", "http://[::1]:8080/admin",
    ...     "http://router.local/reboot", "http://intranet/panel", "http://192.168.1.1/")]
    ['HOST_LOKALNY', 'HOST_LOKALNY', 'HOST_LOKALNY', 'HOST_LOKALNY', 'HOST_LOKALNY']
    >>> [_host(urlsplit(u)) for u in ("https://8.8.8.8/", "https://firma-x.example:8443/", "https://firma-x.example/")]
    [<Powod.HOST_NIETYPOWY: 'HOST_NIETYPOWY'>, <Powod.HOST_NIETYPOWY: 'HOST_NIETYPOWY'>, None]
    """
    host = (czesci.hostname or "").rstrip(".").lower()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        return Powod.HOST_NIETYPOWY if ip.is_global else Powod.HOST_LOKALNY
    if "." not in host or host.endswith(LOKALNE_SUFIKSY) or HOST_LICZBOWY.fullmatch(host):
        return Powod.HOST_LOKALNY
    try:
        port = czesci.port
    except ValueError:
        return Powod.HOST_NIETYPOWY
    return Powod.HOST_NIETYPOWY if port is not None else None


def ocen_link(url: str, odbiorcy: Sequence[str], zrodla: Sequence[str] = ("a",),
              teksty: Sequence[str] = (), nazwy: Sequence[str] = ()) -> Ocena:
    """Rekomendacja dla jednego linku. `zrodla`: „a”, „tekst”, „List-Unsubscribe” albo rodzaj zasobu osadzonego
    w HTML („img”, „script”…); `teksty` — widoczny tekst linku („Wypisz się”); `nazwy` — imię i nazwisko odbiorcy.

    >>> ocen_link("https://firma-x.example/regulamin", []).rekomendacja.value
    'ARCHIWIZUJ'
    >>> o = ocen_link("https://firma-x.example/wypisz?e=osoba.testowa%40odbiorca.example",
    ...               ["osoba.testowa@odbiorca.example"])
    >>> o.rekomendacja.value, [p.value for p in o.powody]
    ('NIE_ARCHIWIZUJ', ['ADRES_ODBIORCY', 'LINK_WYPISANIA', 'PARAMETRY'])
    >>> [p.value for p in ocen_link("https://firma-x.example/dla/jan-testowy", [], nazwy=["Jan Testowy"]).powody]
    ['DANE_ODBIORCY']
    >>> [p.value for p in ocen_link("https://firma-x.example/r/8f3a9c2e4b1d7f60a5e2", []).powody]
    ['TOKEN_ZAKODOWANY']
    >>> [p.value for p in ocen_link("https://firma-x.example/u/1", [], teksty=["Wypisz się"]).powody]
    ['LINK_WYPISANIA', 'IDENTYFIKATOR']
    """
    czesci = urlsplit(url)
    tokeny = decode_tokens(url, "url")
    slady = _slady(nazwy, odbiorcy)
    powody: list[Powod] = []
    if _niesie_adres(url, odbiorcy):
        powody.append(Powod.ADRES_ODBIORCY)
    elif _niesie_dane(url, slady):
        powody.append(Powod.DANE_ODBIORCY)
    if any(t.decoded_text and (ADRES.search(t.decoded_text) or _niesie_adres(t.decoded_text, odbiorcy)
                               or _niesie_dane(t.decoded_text, slady)) for t in tokeny):
        powody.append(Powod.TOKEN_Z_ADRESEM)
    if ("List-Unsubscribe" in zrodla or WYPISANIE.search(f"{czesci.path}?{czesci.query}#{czesci.fragment}")
            or any(WYPISANIE.search(t) for t in teksty)):
        powody.append(Powod.LINK_WYPISANIA)
    if any(z not in KLIKANE for z in zrodla):
        powody.append(Powod.ZASOB_OSADZONY)
    if host := _host(czesci):
        powody.append(host)
    if tokeny and Powod.TOKEN_Z_ADRESEM not in powody:
        powody.append(Powod.TOKEN_ZAKODOWANY)
    if not tokeny and _ma_identyfikator(czesci):
        powody.append(Powod.IDENTYFIKATOR)
    if czesci.query or czesci.fragment:
        powody.append(Powod.PARAMETRY)
    if not powody:
        powody.append(Powod.SAME_SLOWA)
    rekomendacja = next(r for r in OD_NAJOSTRZEJSZEJ if any(SKUTEK[p] is r for p in powody))
    return Ocena(url, (czesci.hostname or "").lower(), tuple(zrodla), rekomendacja, tuple(powody))


def czysty_url(ocena: Ocena, odbiorcy: Sequence[str], nazwy: Sequence[str] = ()) -> str | None:
    """Adres strony bez identyfikatora odbiorcy, wzięty z samego linku — inaczej None (opis w docstringu modułu).

    >>> o = ocen_link("https://firma-x.example/oferta?utm_source=news&e=osoba.testowa%40odbiorca.example",
    ...               ["osoba.testowa@odbiorca.example"])
    >>> o.rekomendacja.value, czysty_url(o, ["osoba.testowa@odbiorca.example"])
    ('NIE_ARCHIWIZUJ', 'https://firma-x.example/oferta')
    >>> czysty_url(ocen_link("https://click.mailer.example/ls/click?upn=Xk2&url=https%3A%2F%2Ffirma-x.example"
    ...                      "%2Foferta%3Futm_source%3Dnews", []), [])
    'https://firma-x.example/oferta'
    >>> czysty_url(ocen_link("https://tracker.example/redirect.php?url=https%3A%2F%2Ffirma-x.example%2Foferta", []), [])
    'https://firma-x.example/oferta'
    >>> czysty_url(ocen_link("https://firma-x.example/c/Ab3xK9q?utm_source=news", []), []) is None
    True
    """
    czesci = urlsplit(ocena.url)
    if (ocena.rekomendacja is Rekomendacja.ARCHIWIZUJ or BEZ_CZYSTEGO & set(ocena.powody)
            or Powod.HOST_LOKALNY in ocena.powody or not (czesci.query or czesci.fragment)
            or czesci.username or czesci.password):
        return None
    cele = [wartosc for _, wartosc in parse_qsl(czesci.query) if URL.fullmatch(wartosc)]
    if cele:
        for cel in cele:
            docelowa = ocen_link(cel, odbiorcy, nazwy=nazwy)
            if docelowa.rekomendacja is Rekomendacja.ARCHIWIZUJ:
                return docelowa.url
            if czysty := czysty_url(docelowa, odbiorcy, nazwy):
                return czysty
        return None
    segmenty = [s for s in czesci.path.split("/") if s]
    koncowka = segmenty[-1].split(".")[0].lower() if segmenty else ""
    if segmenty and (len(koncowka) <= 2 or koncowka in PRZEKIEROWANIE):
        return None
    czysty = urlunsplit((czesci.scheme, czesci.netloc, czesci.path or "/", "", ""))
    return czysty if ocen_link(czysty, odbiorcy, nazwy=nazwy).rekomendacja is Rekomendacja.ARCHIWIZUJ else None


def _z_tekstu(tekst: str) -> list[str]:
    """Linki http(s) z tekstu, bez interpunkcji domykającej zdanie.

    >>> _z_tekstu("Zob. https://firma-x.example/a, potem (https://firma-x.example/b).")
    ['https://firma-x.example/a', 'https://firma-x.example/b']
    """
    return [u.rstrip(".,;:!?") for u in URL.findall(tekst)]


def _z_html(src: str) -> list[tuple[str, str, str | None]]:
    """(link, źródło, tekst linku) dla każdego zasobu http(s) z HTML, także zapisów tego samego URL-a
    w innym miejscu (`also_as`)."""
    return [(r.url, kind, r.text) for r in extract_html_resources(src) if r.scheme in ("http", "https")
            for kind in (r.kind, *r.also_as)]


def _z_eml(sciezka: Path) -> tuple[list[tuple[str, str, str | None]], list[str], list[str], list[str]]:
    """Linki z części HTML, tekstowej i List-Unsubscribe, adresy i nazwy odbiorców oraz domeny nadawcy z nagłówków."""
    msg = load_message(sciezka)
    pary = getaddresses([str(v) for nazwa in NAGLOWKI_ODBIORCOW for v in (msg.get_all(nazwa) or [])])
    odbiorcy = [a for _, a in pary if ADRES.fullmatch(a)]
    nazwy = [n for n, _ in pary if n]
    nadawcy = getaddresses([str(v) for nazwa in NAGLOWKI_NADAWCY for v in (msg.get_all(nazwa) or [])])
    domeny = list(dict.fromkeys(a.rsplit("@", 1)[-1].lower() for _, a in nadawcy if ADRES.fullmatch(a)))
    html, tekst = extract_bodies(msg)
    linki = _z_html(html or "")
    linki += [(u, "tekst", None) for u in _z_tekstu(tekst or "")]
    linki += [(u, "List-Unsubscribe", None) for v in (msg.get_all("List-Unsubscribe") or [])
              for u in _z_tekstu(str(v))]
    return linki, odbiorcy, nazwy, domeny


def ocen_plik(sciezka: Path, odbiorcy: Sequence[str] = (), nazwy: Sequence[str] = ()) -> dict:
    """Ocena wszystkich linków z pliku — słownik o kształcie z docstringu modułu (gotowy do JSON)."""
    rozszerzenie = sciezka.suffix.lower()
    z_pliku: list[str] = []
    nazwy_z_pliku: list[str] = []
    domeny_nadawcy: list[str] = []
    if rozszerzenie == ".eml":
        linki, z_pliku, nazwy_z_pliku, domeny_nadawcy = _z_eml(sciezka)
    elif rozszerzenie in HTML:
        linki = _z_html(sciezka.read_text(encoding="utf-8", errors="replace"))
    elif rozszerzenie in TEKST:
        linki = [(u, "tekst", None) for u in _z_tekstu(sciezka.read_text(encoding="utf-8", errors="replace"))]
    else:
        raise ValueError(f"nieobsługiwany typ pliku {rozszerzenie or '(bez rozszerzenia)'} — podaj .eml, .html "
                         "albo wersję tekstową dokumentu (_tekst.md)")
    wszyscy = list(dict.fromkeys(a.lower() for a in [*z_pliku, *odbiorcy] if a))
    wszystkie_nazwy = list(dict.fromkeys(n for n in [*nazwy_z_pliku, *nazwy] if n.strip()))
    zebrane: dict[str, tuple[list[str], list[str]]] = {}
    for url, zrodlo, tekst in linki:
        zrodla, teksty = zebrane.setdefault(url, ([], []))
        if zrodlo not in zrodla:
            zrodla.append(zrodlo)
        if tekst:
            teksty.append(tekst)
    oceny = [ocen_link(url, wszyscy, zrodla, teksty, wszystkie_nazwy) for url, (zrodla, teksty) in zebrane.items()]
    czyste = [czysty_url(o, wszyscy, wszystkie_nazwy) for o in oceny]
    domeny = [ocen_link(f"https://[{d}]/" if ":" in d else f"https://{d}/", wszyscy, nazwy=wszystkie_nazwy)
              for d in dict.fromkeys([*(o.domena for o in oceny if o.domena), *domeny_nadawcy])]
    do_archiwizacji = [o.url for o in oceny if o.rekomendacja is Rekomendacja.ARCHIWIZUJ] + [c for c in czyste if c]
    return {
        "plik": str(sciezka),
        "odbiorcy": wszyscy,
        "nazwy": wszystkie_nazwy,
        "linki": [{"url": o.url, "domena": o.domena, "zrodla": list(o.zrodla), "rekomendacja": o.rekomendacja.value,
                   "powody": [p.value for p in o.powody], "czysty_url": c} for o, c in zip(oceny, czyste, strict=True)],
        "domeny": [{"domena": o.domena, "strona_glowna": o.url, "rekomendacja": o.rekomendacja.value,
                    "powody": [p.value for p in o.powody]} for o in domeny],
        "do_archiwizacji": list(dict.fromkeys(do_archiwizacji)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("plik")
    ap.add_argument("--odbiorca", action="append", default=[],
                    help="Twój adres e-mail (można kilka razy) — link z nim nie zostanie otwarty")
    ap.add_argument("--nazwa", action="append", default=[],
                    help="Twoje imię i nazwisko (można kilka razy) — link z nimi nie zostanie otwarty")
    a = ap.parse_args(argv)
    sciezka = Path(a.plik)
    if not sciezka.is_file():
        print(f"BŁĄD: brak pliku {sciezka}", file=sys.stderr)
        return 2
    try:
        wynik = ocen_plik(sciezka, a.odbiorca, a.nazwa)
    except ValueError as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 2
    print(json.dumps(wynik, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
