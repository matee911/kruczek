"""Dane ekranów strony: co pokazać na karcie, w wierszu i na osi czasu.

Terminy, „po terminie”, piłkę, sekcje i dni zamknięcia urzędów liczy kruczek_core (przeglad_projektu,
sekcje, zamkniecia_urzedow). Tu tylko dobór słów i znaczników według design systemu: daty dd.mm.rrrr,
kto ma termin, jaki znacznik i jaka akcja na karcie. Tylko stdlib i kruczek_core.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from urllib.parse import quote

from kruczek_core.dni_wolne import DzienJednorazowy, Kalendarz
from kruczek_core.model import (
    ZDARZENIA_PRZYCHODZACE,
    Sprawa,
    Termin,
    Zadanie,
    Zdarzenie,
    chronologia,
)
from kruczek_core.projekt import PrzegladProjektu
from kruczek_core.reguly import REGULA_ANALIZA, REGULA_DORECZENIE, REGULA_ODPOWIEDZ
from kruczek_core.widok import (
    BezRuchu,
    KrokiStartowe,
    PozycjaZadania,
    Sekcje,
    StanWatku,
    co_robic,
    sekcje,
    zamkniecia_urzedow,
)

from kruczek_strona.format import (
    dalej_ze_sprawa,
    data_pl,
    dlugosc_slownie,
    polecenie,
    temu,
    za,
    zostalo,
)

TYPY_ZDARZEN = {"nadanie": "Nadanie pisma", "doreczenie": "Doręczenie pisma", "odpowiedz": "Odpowiedź",
                "wplyw": "Pismo przychodzące", "fakt": "Fakt", "telefon": "Telefon", "inne": "Zdarzenie"}
BLEDY_HTTP = {404: "Nie ma takiej strony", 405: "Tego adresu nie otwiera się w ten sposób"}
BLAD_DOMYSLNY = "Nie da się tego zrobić"
BLAD_SERWERA_TYTUL = "Coś poszło nie tak"
BLAD_SERWERA_TRESC = "Spróbuj odświeżyć. Jeśli się powtarza, uruchom stronę ponownie i zgłoś to w rozmowie z Claude."
WROC_DO_LISTY_SPRAW = "Wróć do listy spraw."
STARY_FORMAT_TYTUL = "Ta sprawa ma stary format"
STARY_FORMAT_TRESC = "Kruczek pokaże ją tutaj po przeniesieniu do sprawa.json."
NIE_MA_SPRAWY_TYTUL = "Nie ma takiej sprawy"
NIE_MA_SPRAWY_TRESC = "Sprawdź adres albo wróć do listy."
SPRAWA_USZKODZONA_TYTUL = "Nie da się odczytać tej sprawy"
SPRAWA_USZKODZONA_TRESC = "Plik sprawa.json jest uszkodzony albo niepełny. Napraw go w rozmowie z Claude."
PEWNOSC = {"dowod": "proof", "poszlaka": "clue", "wlasne_oswiadczenie": "own"}  # → CertaintyChip


def url_sprawy(klucz: str) -> str:
    """
    >>> url_sprawy("podprojekt/sprawa b ą")
    '/sprawa/podprojekt/sprawa%20b%20%C4%85'
    """
    return "/sprawa/" + quote(klucz)


def strona_sprawy(s: Sprawa) -> str | None:
    """Osoba, której sprawa dotyczy, gdy działasz w czyimś imieniu; None = nie wiadomo, bez podmiotu."""
    return next((u.osoba for u in s.uczestnicy if u.rola == "klientka"), None)


def _kto_ma_termin(s: Sprawa, t: Termin) -> str | None:
    if t.czyj == "moj":
        return strona_sprawy(s)
    return s.znajdz_watek(t.watek).adresat if t.watek else s.strona_przeciwna


def uwaga_zamkniecia(j: DzienJednorazowy, *, twoj_termin: bool) -> str:
    """Dzień zamknięcia urzędów w dniu terminu. „Wyślij wcześniej” tylko przy Twoim terminie —
    przy terminie adresata to on musi zdążyć.

    >>> j = DzienJednorazowy(dt.date(2026, 10, 23), "test", True)
    >>> uwaga_zamkniecia(j, twoj_termin=True), uwaga_zamkniecia(j, twoj_termin=False)
    ('urzędy zamknięte 23.10.2026 (test) — wyślij wcześniej', 'urzędy zamknięte 23.10.2026 (test)')
    """
    return f"urzędy zamknięte {data_pl(j.data)} ({j.podstawa})" + (" — wyślij wcześniej" if twoj_termin else "")


def opis_terminu(s: Sprawa, t: Termin) -> str:
    """„Kto: długość — podstawa”, np. „Firma X sp. z o.o.: 14 dni — art. 7 u.r.”."""
    kto = _kto_ma_termin(s, t)
    return f"{kto + ': ' if kto else ''}{dlugosc_slownie(t.dlugosc)} — {t.podstawa}"


@dataclass(frozen=True)
class KartaZadania:
    """TaskCard. akcja: "zrobione", "doreczenie" (formularz daty), "polecenie" (do Claude) albo "" (Wkrótce)."""
    klucz: str
    zadanie: Zadanie
    status: str
    kiedy: str
    dlaczego: str
    uwagi: list[str]
    akcja: str
    polecenie: str = ""

    @property
    def url(self) -> str:
        return url_sprawy(self.klucz)

    @property
    def dom_id(self) -> str:
        """Id elementu unikalne na całej stronie (ten sam numer zadania bywa w kilku sprawach)."""
        return f"z-{hashlib.sha1(self.klucz.encode()).hexdigest()[:8]}-{self.zadanie.id}"


@dataclass(frozen=True)
class KartaKrokow:
    """StartSteps: kroki startowe jednej sprawy w jednej karcie."""
    klucz: str
    kroki: list[Zadanie]
    zrobione: int
    polecenie: str

    @property
    def url(self) -> str:
        return url_sprawy(self.klucz)

    @property
    def dom_id(self) -> str:
        return f"k-{hashlib.sha1(self.klucz.encode()).hexdigest()[:8]}"

    @property
    def kiedy(self) -> str:
        return f"bez terminu · {self.zrobione} z {len(self.kroki)} kroków"


@dataclass(frozen=True)
class Wiersz:
    """WaitRow: Czekam (klepsydra) albo Bez ruchu (folder)."""
    klucz: str
    ikona: str
    kto: str
    watek: str | None
    data: str
    pod_data: str

    @property
    def url(self) -> str:
        return url_sprawy(self.klucz)


@dataclass(frozen=True)
class Wpis:
    """Wiersz osi czasu (Timeline): zdarzenie albo termin."""
    data: str
    rodzaj: str  # "" | "in" | "due"
    co: str
    status: str = ""  # StatusChip albo CertaintyChip
    meta: list[str] = field(default_factory=list)
    dowody: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Komunikat:
    """Alert nad treścią po akcji (PageAlert); `polecenie` — gdy dalej trzeba działać w Claude."""
    tytul: str
    tresc: str
    wariant: str = "warning"
    polecenie: str = ""


@dataclass(frozen=True)
class Powiadomienie:
    """Toast po zapisie; `akcja` = adres „Cofnij” (POST z polami `pola`), pusty = bez „Cofnij”."""
    tekst: str
    akcja: str = ""
    pola: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EkranSekcji:
    po_terminie: list[KartaZadania]
    teraz: list[KartaZadania | KartaKrokow]
    czekam: list[Wiersz]
    wkrotce: list[KartaZadania | KartaKrokow]
    bez_ruchu: list[Wiersz]
    najblizszy: dt.date | None


@dataclass(frozen=True)
class EkranCoRobic:
    dzis: dt.date
    sekcje: EkranSekcji
    liczba_spraw: int
    stary_format: list[str]
    bez_indexu: list[str]
    bledy: list[tuple[str, str]]


@dataclass(frozen=True)
class EkranSprawy:
    dzis: dt.date
    klucz: str
    sprawa: Sprawa
    strona: str | None
    sekcje: EkranSekcji
    terminy: list[Wpis]
    chronologia: list[Wpis]


def karta_zadania(p: PozycjaZadania, s: Sprawa, kal: Kalendarz, dzis: dt.date, *, wkrotce: bool = False) -> KartaZadania:
    a, t = p.zadanie, p.termin_sprawy
    status, kiedy = "", "bez terminu"
    if p.po_terminie:
        status, kiedy = "overdue", f"minął {data_pl(p.termin_konca)} · {temu(p.po_terminie)}"
    elif wkrotce:
        status, kiedy = "soon", f"od {data_pl(a.aktywne_od)} · {za((a.aktywne_od - dzis).days)}"
    elif a.termin is not None:
        status, kiedy = "ours", f"do {data_pl(a.termin)} · {zostalo((a.termin - dzis).days)}"
    elif a.regula == REGULA_DORECZENIE and t is not None:
        status = "estimate" if t.szacunek else ""
        kto = _kto_ma_termin(s, t)
        kiedy = f"{kto + ': ' if kto else ''}{'ok. ' if t.szacunek else 'do '}{data_pl(t.data_konca)}"
    dlaczego = ""
    if t is not None:
        dlaczego = opis_terminu(s, t) + (" · termin szacunkowy — wpisz datę doręczenia" if t.szacunek else "")
    uwagi = [uwaga_zamkniecia(j, twoj_termin=True) for j in zamkniecia_urzedow(p, kal)]
    if wkrotce:
        return KartaZadania(p.klucz, a, status, kiedy, dlaczego, uwagi, "")
    if a.regula == REGULA_DORECZENIE:
        return KartaZadania(p.klucz, a, status, kiedy, dlaczego, uwagi, "doreczenie")
    if a.regula in (REGULA_ODPOWIEDZ, REGULA_ANALIZA):
        return KartaZadania(p.klucz, a, status, kiedy, dlaczego, uwagi, "polecenie", polecenie("eskalacja", p.klucz))
    return KartaZadania(p.klucz, a, status, kiedy, dlaczego, uwagi, "zrobione")


def karta_krokow(k: KrokiStartowe) -> KartaKrokow:
    return KartaKrokow(k.klucz, k.kroki, k.zrobione, dalej_ze_sprawa(k.klucz))


def wiersz_czekam(st: StanWatku, dzis: dt.date) -> Wiersz:
    data, pod = "bez terminu", ""
    if st.czekam_do is not None:
        data = f"{'ok. ' if st.szacunek else 'do '}{data_pl(st.czekam_do)}"
        pod = f"{'szacunek · ' if st.szacunek else ''}{zostalo((st.czekam_do - dzis).days)}"
    return Wiersz(st.klucz, "hourglass", f"Czekam na odpowiedź: {st.watek.adresat}", st.watek.id, data, pod)


def wiersz_bez_ruchu(b: BezRuchu, dzis: dt.date) -> Wiersz:
    if b.ostatni_ruch is None:
        return Wiersz(b.klucz, "folder", b.sprawa, None, "brak zdarzeń", "")
    return Wiersz(b.klucz, "folder", b.sprawa, None, data_pl(b.ostatni_ruch), temu((dzis - b.ostatni_ruch).days))


def _karty(pozycje: list, sprawy: Mapping[str, Sprawa], kalendarze: Mapping[str, Kalendarz], dzis: dt.date,
           *, wkrotce: bool = False) -> list:
    return [karta_krokow(p) if isinstance(p, KrokiStartowe)
            else karta_zadania(p, sprawy[p.klucz], kalendarze[p.klucz], dzis, wkrotce=wkrotce) for p in pozycje]


def sekcje_ekranu(sek: Sekcje, sprawy: Mapping[str, Sprawa], kalendarze: Mapping[str, Kalendarz],
                  dzis: dt.date) -> EkranSekcji:
    daty = [c.czekam_do for c in sek.czekam if c.czekam_do] + [
        p.termin_konca for p in sek.wkrotce if isinstance(p, PozycjaZadania) and p.termin_konca]
    return EkranSekcji(
        _karty(sek.po_terminie, sprawy, kalendarze, dzis),
        _karty(sek.teraz, sprawy, kalendarze, dzis),
        [wiersz_czekam(c, dzis) for c in sek.czekam],
        _karty(sek.wkrotce, sprawy, kalendarze, dzis, wkrotce=True),
        [wiersz_bez_ruchu(b, dzis) for b in sek.bez_ruchu],
        min(daty, default=None),
    )


def ekran_co_robic(pp: PrzegladProjektu, dzis: dt.date) -> EkranCoRobic:
    sek = sekcje(pp.przeglad, pp.sprawy, dzis)
    return EkranCoRobic(dzis, sekcje_ekranu(sek, pp.sprawy, pp.kalendarze, dzis), len(pp.sprawy),
                        pp.stary_format, pp.bez_indexu, pp.bledy)


def _wpis_terminu(s: Sprawa, t: Termin, kal: Kalendarz) -> Wpis:
    status = "estimate" if t.szacunek else ("ours" if t.czyj == "moj" else "waiting")
    zamkniecia = [uwaga_zamkniecia(j, twoj_termin=t.czyj == "moj") for j in kal.zamkniete_urzedy(t.data_konca)]
    meta = [t.podstawa, *(["szacunek"] if t.szacunek else []), *zamkniecia] + ([f"wątek: {t.watek}"] if t.watek else [])
    kto = _kto_ma_termin(s, t)
    co = f"{kto + ': ' if kto else ''}{dlugosc_slownie(t.dlugosc)}"
    return Wpis(f"{'ok. ' if t.szacunek else ''}{data_pl(t.data_konca)}", "due", co, status, meta)


def _wpis_zdarzenia(z: Zdarzenie) -> Wpis:
    co = f"{TYPY_ZDARZEN[z.typ]}: {z.opis}" if z.opis else TYPY_ZDARZEN[z.typ]
    data = data_pl(z.data) + (f" {z.godzina}" if z.godzina else "")
    meta = [f"wątek: {z.watek}"] if z.watek else []
    return Wpis(data, "in" if z.typ in ZDARZENIA_PRZYCHODZACE else "", co, PEWNOSC.get(z.pewnosc or "", ""), meta,
                list(z.dowody))


def ekran_sprawy(klucz: str, s: Sprawa, kal: Kalendarz, dzis: dt.date) -> EkranSprawy:
    """Jedna sprawa: te same sekcje co „Co robić” (kod co_robic + sekcje), terminy i chronologia."""
    sek = sekcje(co_robic([(klucz, s)], dzis), {klucz: s}, dzis)
    return EkranSprawy(dzis, klucz, s, strona_sprawy(s), sekcje_ekranu(sek, {klucz: s}, {klucz: kal}, dzis),
                       [_wpis_terminu(s, t, kal) for t in sorted(s.terminy, key=lambda t: t.data_konca)],
                       [_wpis_zdarzenia(z) for z in chronologia(s)])


# --- zapis ze strony: alerty, toasty i błędy formularza ------------------------------------------

NIE_ZAPISANO = "Nie zapisano"
FORMULARZ_ZA_DUZY = f"{NIE_ZAPISANO}: formularz jest za duży."
KONFLIKT = Komunikat("Sprawa zmieniła się w międzyczasie",
                     "Ktoś zapisał ją w innym miejscu (np. w rozmowie z Claude). Pokazuję aktualny stan — "
                     "sprawdź i kliknij jeszcze raz, jeśli trzeba.")
ODRZUCONE_TRESC = ("Formularz pochodzi ze starej karty (kruczek był uruchomiony ponownie) albo z innej strony. "
                   "Odśwież stronę i spróbuj jeszcze raz.")
POLA_FORMULARZA = {"widok": "widok", "opis": "opis zadania", "data": "data", "typ": "rodzaj wpisu"}


def alert_bez_zapisu(powod: object) -> Komunikat:
    """Zapis odrzucony przez rdzeń (np. zadanie już zrobione)."""
    return Komunikat(NIE_ZAPISANO, f"{powod}.", "destructive")


def alert_index_nieaktualny(uwaga: str) -> Komunikat:
    """Zapis się udał, ale odświeżenie index.md nie."""
    return Komunikat("Zapisano, ale index.md nie jest aktualny", f"{uwaga}.")


def powiadomienie_zrobione(klucz: str, zadanie_id: str, opis: str) -> Powiadomienie:
    cofnij = f"{url_sprawy(klucz)}/zadania/{zadanie_id}/cofnij-zrobione"
    return Powiadomienie(f"Oznaczono jako zrobione: „{opis}”.", cofnij, {"opis": opis})


def powiadomienie_otwarte(opis: str) -> Powiadomienie:
    return Powiadomienie(f"Zadanie znów otwarte: „{opis}”.")


NIE_OSTATNIE_TYTUL = "Tego wpisu nie cofniesz już tutaj"
POWIADOMIENIE_COFNIETO = "Cofnięto wpis doręczenia."


def blad_doreczenia_przed_nadaniem(data_nadania: dt.date) -> str:
    return (f"Pismo nadano {data_pl(data_nadania)} — doręczenie nie mogło być wcześniej. "
            "Sprawdź datę w potwierdzeniu odbioru.")


def powiadomienie_doreczenia(klucz: str, zdarzenie: Zdarzenie) -> Powiadomienie:
    cofnij = f"{url_sprawy(klucz)}/zdarzenia/{zdarzenie.id}/cofnij"
    return Powiadomienie(f"Zapisano doręczenie {data_pl(zdarzenie.data)}. Termin liczy się teraz od tej daty.",
                         cofnij, {"typ": zdarzenie.typ, "data": zdarzenie.data.isoformat()})


def alert_nie_ostatnie(klucz: str) -> Komunikat:
    """„Cofnij” doręczenia, po którym jest już nowsze zdarzenie — poprawia się je w rozmowie z Claude."""
    return Komunikat(NIE_OSTATNIE_TYTUL,
                     "Po nim w sprawie jest nowsze zdarzenie. Popraw albo cofnij je w rozmowie z Claude:",
                     polecenie=polecenie("chronologia", klucz))


def komunikat_formularza(bledy: Iterable[Mapping[str, object]]) -> Komunikat:
    """Błędy kształtu formularza (lista z pydantic) po polsku: które pola i co zrobić. Tekstów pydantic
    nie pokazujemy — taki formularz nie pochodzi z aktualnej strony, poprawia go odświeżenie.

    >>> komunikat_formularza([{"loc": ("body", "opis"), "type": "missing", "msg": "Field required"},
    ...                       {"loc": ("body", "widok"), "type": "literal_error", "msg": "Input should be"}]).tresc
    'Niepełne albo nieznane pola: opis zadania, widok. Formularz pochodzi ze starszej wersji strony — odśwież ją i spróbuj jeszcze raz.'
    """
    pola = dict.fromkeys(POLA_FORMULARZA.get(str((b.get("loc") or ("",))[-1]), "inne pole") for b in bledy)
    return Komunikat(NIE_ZAPISANO, f"Niepełne albo nieznane pola: {', '.join(pola)}. Formularz pochodzi "
                     "ze starszej wersji strony — odśwież ją i spróbuj jeszcze raz.", "destructive")
