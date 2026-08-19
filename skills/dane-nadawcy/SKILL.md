---
name: dane-nadawcy
description: Wypełnia lub aktualizuje _SZABLONY/dane-nadawcy.md z danymi nadawcy (NIP, adres, e-mail). Użyj przy zakładaniu projektu lub gdy dane się zmieniły. Nie dotyka CLAUDE.md.
argument-hint: "[katalog projektu]"
model: sonnet
effort: low
allowed-tools: Read Write Edit
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

## 5. Potwierdź

Pokaż użytkownikowi wypełnione pola. Powiedz które nadal są puste — jeśli są krytyczne
(NIP, adres) — wskaż to wprost.
