---
name: init-projekt
description: Zakłada repozytorium spraw kruczka w bieżącym katalogu — BAZA_WIEDZY, KONWENCJE.md, rejestr spraw, szablony. Użyj raz na projekt, zanim założysz pierwszą sprawę.
argument-hint: "[katalog]"
disable-model-invocation: true
model: sonnet
effort: medium
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/check-deps.sh) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/init-projekt.sh *) Read Write Edit
---

# Założenie repozytorium spraw

Katalog docelowy: `$1` (jeśli pusty — bieżący katalog roboczy).

## 1. Sprawdź, czy nie nadpisujesz

Jeśli w katalogu docelowym jest już `index.md` lub `BAZA_WIEDZY/` — **nie nadpisuj**. Pokaż, co
istnieje, i zapytaj, czy uzupełnić brakujące elementy, czy przerwać.

## 2. Uruchom skrypt

```
${CLAUDE_PLUGIN_ROOT}/scripts/init-projekt.sh <katalog>
```

Skrypt automatycznie uruchamia `check-deps.sh` jako pierwszy krok. Jeśli brakuje wymaganych
narzędzi (`curl`, `jq`, `python3`), skrypt przerwie się i wypisze gotową komendę instalacji
dla wykrytej platformy (macOS/Linux). Użytkownik musi ją uruchomić ręcznie, a potem powtórzyć
`/kruczek:init-projekt`. Brakujące narzędzia opcjonalne (PDF, OCR) są sygnalizowane ostrzeżeniem,
ale nie blokują inicjalizacji.

Tworzy: `index.md` (rejestr spraw), `KONWENCJE.md` (zasady prowadzenia), `BAZA_WIEDZY/`
z podkatalogami `przepisy/ orzecznictwo/ decyzje/ wzory/ metodyka/` oraz `_SZABLONY/`.
Skrypt jest idempotentny — nie nadpisuje istniejących plików.

## 3. Skopiuj szablon pisma

```
cp ${CLAUDE_PLUGIN_ROOT}/templates/pismo.html <katalog>/_SZABLONY/
```

## 4. Dopytaj o kontekst i zapisz go

Zapytaj użytkownika **jednym** wywołaniem AskUserQuestion o rzeczy, które będą wracać w każdym piśmie:

- czy występuje jako **osoba fizyczna / konsument** czy jako **przedsiębiorca** (to zmienia podstawy prawne
  i katalog roszczeń — konsument ma UOKiK, Rzecznika Finansowego i rękojmię, przedsiębiorca ma u.z.n.k.)
- dane do nagłówka pism: imię i nazwisko lub firma, adres korespondencyjny, NIP, e-mail, miejscowość
- czy pisma papierowe wysyła sam, czy przez usługę online (np. Envelo) — od tego zależy, czy załączniki
  mają być wdrukowane w PDF

Zapisz odpowiedzi w `<katalog>/_SZABLONY/dane-nadawcy.md`. Uprzedź, że plik zawiera dane osobowe —
jeśli repozytorium trafi do gita, powinien być w `.gitignore`.

## 5. Podsumuj

Pokaż drzewo katalogów i **jedną** następną komendę: `/kruczek:nowa-sprawa`.
Nie rozpisuj się — użytkownik dopiero zaczyna.
