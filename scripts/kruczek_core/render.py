"""Bloki index.md generowane z sprawa.json.

Treść między znacznikami <!-- kruczek:<blok> --> … <!-- /kruczek:<blok> --> jest
nadpisywana przy każdym renderowaniu. Wszystko poza znacznikami (stan faktyczny,
strategia, notatki) zostaje nietknięte.
"""

from __future__ import annotations

from kruczek_core.dni_wolne import Kalendarz
from kruczek_core.model import BladSprawy, Sprawa, Termin, chronologia

BLOKI = ("chronologia", "terminy", "zadania")
_NAGLOWKI = {"chronologia": "Chronologia", "terminy": "Terminy", "zadania": "Zadania"}


def _jednolinia(s: str) -> str:
    return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _komorka(s: str) -> str:
    return _jednolinia(s).replace("|", "\\|")


_PEWNOSC = {"dowod": "dowód", "poszlaka": "poszlaka", "wlasne_oswiadczenie": "własne oświadczenie — brak pliku"}


def _chronologia(s: Sprawa) -> str:
    wiersze = ["| Data | Godz. | Zdarzenie | Wątek | Opis | Dowody |", "|---|---|---|---|---|---|"]
    for z in chronologia(s):
        watek = _komorka(z.watek or "—")
        opis = _komorka(z.opis)
        dowody = ", ".join(z.dowody) or "—"
        if z.pewnosc:
            dowody = f"{dowody} ({_PEWNOSC[z.pewnosc]})"
        wiersze.append(f"| {z.data.isoformat()} | {z.godzina or '—'} | {z.typ} | {watek} | {opis} | {_komorka(dowody)} |")
    return "\n".join(wiersze)


def uwagi_terminu(t: Termin, kal: Kalendarz) -> list[str]:
    """Uwagi do terminu wspólne dla index.md i strony: szacunek (liczony od nadania) i dni wolne tylko dla urzędów."""
    return (["szacunek"] if t.szacunek else []) + kal.ostrzezenia(t.data_konca)


def _terminy(s: Sprawa, kal: Kalendarz) -> str:
    wiersze = ["| Termin | Czyj | Wątek | Podstawa | Długość | Koniec | Uwagi |", "|---|---|---|---|---|---|---|"]
    for t in sorted(s.terminy, key=lambda t: t.data_konca):
        uwagi = uwagi_terminu(t, kal)
        czyj = "mój" if t.czyj == "moj" else "adresata"
        watek = _komorka(t.watek or "—")
        podstawa = _komorka(t.podstawa)
        uwagi_txt = _komorka("; ".join(uwagi) or "—")
        wiersze.append(f"| {t.id} | {czyj} | {watek} | {podstawa} | {t.dlugosc} | {t.data_konca.isoformat()} | {uwagi_txt} |")
    return "\n".join(wiersze)


def _zadania(s: Sprawa) -> str:
    otwarte = sorted((a for a in s.zadania if a.zrobione is None), key=lambda a: a.aktywne_od)
    if not otwarte:
        return "_(brak otwartych zadań)_"
    linie = []
    for a in otwarte:
        termin = f", termin {a.termin.isoformat()}" if a.termin else ""
        opis = _jednolinia(a.opis)
        linie.append(f"- [ ] {a.id} — {opis} (aktywne od {a.aktywne_od.isoformat()}{termin})")
    return "\n".join(linie)


def _wstaw(tekst: str, blok: str, nowy: str) -> str:
    start, koniec = f"<!-- kruczek:{blok} -->", f"<!-- /kruczek:{blok} -->"
    ile_start, ile_koniec = tekst.count(start), tekst.count(koniec)
    if ile_start == 0 and ile_koniec == 0:
        return tekst.rstrip("\n") + f"\n\n## {_NAGLOWKI[blok]} (generowane — nie edytuj ręcznie)\n\n{nowy}\n"
    if ile_start == 1 and ile_koniec == 1 and tekst.index(start) < tekst.index(koniec):
        przed, reszta = tekst.split(start, 1)
        _, po = reszta.split(koniec, 1)
        return przed + nowy + po
    raise BladSprawy(f"index.md: uszkodzone znaczniki bloku {blok} — popraw ręcznie")


def renderuj(tekst: str, sprawa: Sprawa, kalendarz: Kalendarz) -> str:
    tresci = {"chronologia": _chronologia(sprawa), "terminy": _terminy(sprawa, kalendarz), "zadania": _zadania(sprawa)}
    for blok in BLOKI:
        nowy = f"<!-- kruczek:{blok} -->\n{tresci[blok]}\n<!-- /kruczek:{blok} -->"
        tekst = _wstaw(tekst, blok, nowy)
    return tekst
