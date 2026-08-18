#!/usr/bin/env bash
# init-projekt.sh — zakłada strukturę repozytorium spraw kruczka.
#   init-projekt.sh [KATALOG]      (domyślnie bieżący)
set -euo pipefail

# Sprawdź zależności przed czymkolwiek innym
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/check-deps.sh" || exit 1

ROOT="${1:-.}"
mkdir -p "$ROOT"/BAZA_WIEDZY/{przepisy,orzecznictwo,decyzje,wzory,metodyka}
mkdir -p "$ROOT"/_SZABLONY

[ -f "$ROOT/BAZA_WIEDZY/index.md" ] || cat > "$ROOT/BAZA_WIEDZY/index.md" <<'EOF'
# BAZA WIEDZY

Przepisy, orzecznictwo i metodyka wielokrotnego użytku. **Zanim zaczniesz szukać w internecie —
sprawdź, czy odpowiedź już tu jest.**

## Zasady
- Cytaty **dosłowne**, wyłącznie ze źródeł urzędowych (API ELI Sejmu / ISAP, EUR-Lex, portale orzeczeń organów).
- Każdy plik ma na górze: akt, publikator (Dz.U.), URL źródła, datę weryfikacji.
- Pozycje niepotwierdzone oznaczaj `⚠ NIEPOTWIERDZONE` — **nie wolno ich cytować w pismach**.
- Przy każdym przepisie notuj, czy i kiedy został **uchylony lub znowelizowany**.
- Nowa sprawa = najpierw sprawdź bazę, dopiero potem research.

## Spis
| Plik | Zakres |
|---|---|
| _(pusto — dopisuj przy każdym researchu)_ | |
EOF

[ -f "$ROOT/index.md" ] || cat > "$ROOT/index.md" <<'EOF'
# Rejestr spraw

## Struktura
```
.
├── index.md            ← ten plik: rejestr wszystkich spraw
├── BAZA_WIEDZY/        ← przepisy, orzecznictwo, metodyka (wspólne)
├── _SZABLONY/          ← wzory pism i plików
└── <PODMIOT>/          ← jeden katalog na drugą stronę
    ├── index.md        ← manifest, chronologia, ustalenia, TODO, eskalacja
    ├── ARCHIWUM/       ← oryginały dowodów — TYLKO DOPISYWANIE, nigdy edycja
    ├── ROBOCZE/        ← notatki, wersje, materiały pomocnicze
    └── <YYYY_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/
        ├── ROBOCZE/    ← szablon pisma + instrukcja regeneracji
        ├── *.pdf       ← pismo gotowe do druku (z wdrukowanymi załącznikami)
        └── dowody.zip  ← dowody cyfrowe + SHA256SUMS.txt
```

## Sprawy
| # | Podmiot | Przedmiot | Założono | Status | Najbliższy termin |
|---|---|---|---|---|---|
EOF

[ -f "$ROOT/KONWENCJE.md" ] || cat > "$ROOT/KONWENCJE.md" <<'EOF'
# Konwencje prowadzenia spraw

## 1. Archiwum jest niezmienne
`ARCHIWUM/` jest **append-only**. Oryginał dowodu nigdy nie jest edytowany, przycinany ani
konwertowany „w miejscu”. Każda obróbka tworzy **nowy** plik obok oryginału.

Nazewnictwo: `RRRR-MM-DD_<rodzaj>_<krotki-opis>.<ext>`, gdzie data to **data powstania dowodu**
(nadania listu, wysłania maila, wykonania zdjęcia), a nie data dodania do teczki.

## 2. Każdy dowód ma sumę kontrolną
Po dodaniu czegokolwiek do `ARCHIWUM/`:
```
manifest.py sumy   <katalog-sprawy>
manifest.py wstaw  <katalog-sprawy>/index.md <katalog-sprawy>
```
Suma SHA-256 oryginału trafia też do treści pisma — to zabezpiecza przed zarzutem podmiany.

## 3. Dowody nietekstowe dostają wersję tekstową
Skan, zdjęcie, PDF z obrazem, nagranie rozmowy, screenshot — **od razu** przy dodaniu powstaje
plik `.md` obok oryginału, o tej samej nazwie bazowej z sufiksem `_tekst.md`:
- skan / zdjęcie / PDF-obraz → OCR (`ocrmypdf`, `tesseract -l pol`) albo odczyt modelem vision
- nagranie audio/wideo → transkrypcja z **znacznikami czasu** i oznaczeniem mówców
- e-mail `.eml` → `eml-forensics.py` (nagłówki + treść + analiza)

W nagłówku pliku tekstowego zapisz: metodę (OCR/vision/transkrypcja), narzędzie, datę,
oraz **wyraźne ostrzeżenie, że to odczyt pomocniczy, a wiążący jest oryginał**.
Fragmenty nieczytelne oznaczaj `[nieczytelne]`, niepewne `[?]`. Nie zgaduj.

## 4. Chronologia jest ciągła
Tabela chronologii w `index.md` sprawy zawiera każde zdarzenie: wpływ pisma, nadanie, doręczenie,
telefon, upływ terminu. Kolumny: `Data | Godz. | Zdarzenie | Dowód`. Daty względne („za tydzień”)
zawsze zamieniaj na bezwzględne. Bez wpisu w chronologii zdarzenie nie istnieje.

## 5. Wysyłka ma własny katalog
`<YYYY_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/` — data przygotowania. W środku `ROBOCZE/`, plik `.PDF`
z pismem i `dowody.zip`. Jeśli odbiorca wymaga listu papierowego, **załączniki są wdrukowane w PDF**,
żeby wydruk był kompletny bez dokładania czegokolwiek.

## 6. Pisma cytują źródła
Każde twierdzenie prawne ma dosłowny cytat przepisu z publikatorem (Dz.U. rok/pozycja) i — jeśli
istnieje — sygnaturę orzeczenia. Cytaty pochodzą z BAZY WIEDZY albo ze źródła urzędowego,
nigdy z pamięci. Przed wysyłką: cross-check i double check (`/kruczek:weryfikuj`).

## 7. Hipotezy są oznaczone
Ustalenie niepotwierdzone dowodem (np. „to prawdopodobnie ta sama spółka”) trafia do `index.md`
z nagłówkiem `⚠ HIPOTEZA — NIE cytować w pismach` i wprost wskazanym brakującym ogniwem.
EOF
echo "Struktura założona w: $(cd "$ROOT" && pwd)"
find "$ROOT" -maxdepth 2 -not -path '*/.*' | sort
