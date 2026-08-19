---
name: dane-nadawcy
description: Wypełnia lub aktualizuje _SZABLONY/dane-nadawcy.md z danymi nadawcy (NIP, adres, e-mail). Dla przedsiębiorców weryfikuje dane z rejestrem (CEIDG dla JDG, KRS dla spółek). Użyj przy zakładaniu projektu lub gdy dane się zmieniły. Nie dotyka CLAUDE.md.
argument-hint: "[katalog projektu]"
model: sonnet
effort: low
allowed-tools: Read Write Edit Bash(${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh *)
---

# Aktualizacja danych nadawcy

Katalog projektu: `$1` (jeśli pusty — bieżący katalog roboczy).

## 1. Sprawdź czy plik istnieje

Jeśli `_SZABLONY/dane-nadawcy.md` nie istnieje — skopiuj szablon:

```
cp ${CLAUDE_PLUGIN_ROOT}/templates/dane-nadawcy.md <katalog>/_SZABLONY/dane-nadawcy.md
```

## 2. Odczytaj co już jest wypełnione

Read `<katalog>/_SZABLONY/dane-nadawcy.md`. Wypisz użytkownikowi **jedną** tabelę z bieżącymi
wartościami — zaznacz które pola są puste lub mają placeholder (`<...>`).

## 3. Zapytaj o brakujące dane

Zapytaj **jednym** wywołaniem AskUserQuestion o wszystkie puste/placeholder pola naraz.
Nie pytaj o pola już wypełnione — szanuj to co użytkownik już wpisał.

Minimum potrzebne do pisania pism:
- imię i nazwisko (lub firma + forma prawna)
- NIP (jeśli przedsiębiorca lub chce podawać)
- adres do korespondencji
- miejscowość w nagłówku
- e-mail do spraw spornych

## 4. Zapisz odpowiedzi

Edit `<katalog>/_SZABLONY/dane-nadawcy.md` — wpisz podane wartości w odpowiednie wiersze tabeli.
Nie zmieniaj struktury pliku ani innych pól.

## 5. Weryfikacja rejestrowa (tylko dla przedsiębiorców)

Pomiń ten krok jeśli `Występuję jako = osoba fizyczna / konsument`.

Jeśli NIP jest wypełniony, odpytaj rejestr i porównaj z tym co użytkownik podał:

**JDG** (brak KRS lub forma prawna = JDG):
```
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh ceidg <NIP>
```
Sprawdź i zaraportuj rozbieżności w:
- adres do doręczeń w CEIDG vs adres podany przez użytkownika
- e-mail w CEIDG vs e-mail podany przez użytkownika
- status działalności (czy aktywna, czy zawieszona/wykreślona)
- pełne brzmienie firmy (imię i nazwisko + nazwa handlowa)

**Spółka** (jest KRS):
```
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh nip <NIP>
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh krs <KRS> P
```
Sprawdź i zaraportuj rozbieżności w:
- adres siedziby z KRS vs adres podany przez użytkownika
- pełne brzmienie firmy z formą prawną
- reprezentacja (kto może podpisywać pisma w imieniu spółki)
- status (czy aktywna, czy w likwidacji/upadłości)

Raport rozbieżności:
- **zgodne** — jedna linia, nie rozpisuj
- **niezgodne** — wypisz: pole, wartość z rejestru, wartość podana przez użytkownika, zapytaj które użyć
- **brak w rejestrze** (np. e-mail) — informacja, nie błąd

Jeśli CEIDG zwróci błąd braku tokenu — poinformuj użytkownika że weryfikacja adresu zamieszkania
wymaga tokenu CEIDG (`~/.kruczek/ceidg_token`), ale biała lista VAT działa bez niego i podaj z niej
co się dało.

## 6. Potwierdź

Pokaż użytkownikowi wypełnione pola. Powiedz które nadal są puste — jeśli są krytyczne
(NIP, adres) — wskaż to wprost.
