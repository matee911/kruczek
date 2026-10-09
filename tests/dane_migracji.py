"""Wspólne dane testowe migracji starej teczki (test_migracja, test_teczka_cli)."""

STARY_INDEX = """# SPRAWA: X sp. z o.o.

| | |
|---|---|
| **Podmiot** | X sp. z o.o. |
| **Status** | w toku |

## 1. Chronologia

| Data | Godz. | Zdarzenie | Dowód |
|---|---|---|---|
| 2026-09-01 | | Reklamacja poleconym | ARCHIWUM/2026-09-01_nadanie.pdf |

## 2. Ustalenia

- sprzedawca przyznał wadę telefonicznie
"""


def propozycja(**zmiany):
    p = {
        "tytul": "Reklamacja butów", "strona_przeciwna": "X sp. z o.o.",
        "watki": [{"id": "firma", "adresat": "X sp. z o.o."}],
        "zdarzenia": [
            {"klucz": "r", "data": "2026-09-01", "typ": "nadanie", "watek": "firma",
             "termin": {"dlugosc": "14d", "podstawa": "art. 7a ust. 1 u.p.k."}},
            {"klucz": "o", "data": "2026-09-10", "typ": "odpowiedz", "watek": "firma", "dotyczy": "r"},
            {"klucz": "k", "data": "2026-09-12", "typ": "nadanie", "watek": "firma",
             "termin": {"dlugosc": "14d", "podstawa": "wyznaczony w piśmie"}},
            {"klucz": "e", "data": "2026-09-15", "typ": "doreczenie", "watek": "firma"},
        ],
        "zadania": [{"opis": "Zebrać paragon", "aktywne_od": "2026-10-20"}],
    }
    p.update(zmiany)
    return p
