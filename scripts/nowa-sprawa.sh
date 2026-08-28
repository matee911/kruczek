#!/usr/bin/env bash
# nowa-sprawa.sh — zakłada katalog sprawy z index.md.
#   nowa-sprawa.sh "<Nazwa podmiotu>" "<przedmiot sprawy>" [KATALOG-PROJEKTU]
set -euo pipefail
NAZWA="${1:?podaj nazwę podmiotu}"; PRZEDMIOT="${2:?podaj przedmiot sprawy}"; ROOT="${3:-.}"
SLUG=$(printf %s "$NAZWA" | iconv -f UTF-8 -t ASCII//TRANSLIT 2>/dev/null || printf %s "$NAZWA")
# sed -E (ERE): BSD sed na macOS nie rozumie \+ w podstawowym wyrażeniu regularnym —
# bez -E slug zostawał niezmieniony i katalog sprawy dostawał nazwę ze spacjami i kropkami.
SLUG=$(printf %s "$SLUG" | tr 'A-Z' 'a-z' | sed -E 's/[^a-z0-9]+/-/g; s/^-//; s/-$//')
DIR="$ROOT/$SLUG"; DZIS=$(date +%F)
mkdir -p "$DIR"/{ARCHIWUM,ROBOCZE}
[ -f "$DIR/index.md" ] && { echo "Sprawa już istnieje: $DIR/index.md"; exit 0; }
cat > "$DIR/index.md" <<EOF
# SPRAWA: $NAZWA

| | |
|---|---|
| **Podmiot** | $NAZWA |
| **Przedmiot** | $PRZEDMIOT |
| **Występuję jako** | _(osoba fizyczna / przedsiębiorca / w imieniu: <kto> — tożsamości w \`_SZABLONY/dane-nadawcy.md\`)_ |
| **Dane rejestrowe** | _(NIP / KRS / adres — uzupełnij: \`podmiot.sh pelny <NIP>\`)_ |
| **Status** | nowa |
| **Założono** | $DZIS |
| **Najbliższy termin** | — |

## 1. Chronologia

| Data | Godz. | Zdarzenie | Dowód |
|---|---|---|---|
| $DZIS | | Założenie sprawy | — |

## 2. Ustalenia

_(fakty potwierdzone dowodem — po jednym punkcie)_

### ⚠ HIPOTEZY — NIE cytować w pismach
_(ustalenia bez pełnego dowodu + wskazanie brakującego ogniwa)_

## 3. Podstawa prawna

_(przepisy z dosłownym cytatem — źródła w ../BAZA_WIEDZY/)_

## 4. Manifest plików

Tabela poniżej jest generowana automatycznie: \`manifest.py wstaw $DIR/index.md $DIR\`.
Opisy plików prowadź w tej sekcji nad manifestem.

| Plik | Co to jest |
|---|---|
| | |

<!-- KRUCZEK:MANIFEST:START -->
<!-- KRUCZEK:MANIFEST:END -->

## 5. TODO

- [ ] Ustalić pełne dane rejestrowe drugiej strony
- [ ] Zebrać i zarchiwizować dowody (+ wersje tekstowe dla plików nietekstowych)
- [ ] Sprawdzić BAZĘ WIEDZY, uzupełnić brakujące przepisy
- [ ] Przygotować pismo
- [ ] Cross-check cytatów przed wysyłką
- [ ] Nadać i zarchiwizować potwierdzenie nadania
- [ ] Wpisać termin kontrolny do chronologii

## 6. Ścieżka eskalacji

_(kolejne kroki po bezskutecznym upływie terminu — od najtańszego do najdroższego)_
EOF
echo "Założono sprawę: $DIR"
echo "Dopisz ją do rejestru w $ROOT/index.md:"
echo "| | $NAZWA | $PRZEDMIOT | $DZIS | nowa | — |"
echo ""
echo "Dalszą pracę nad tą sprawą prowadź w OSOBNEJ sesji przypiętej do $DIR"
echo "(nie w sesji obejmującej cały $ROOT) — zapobiega myleniu spraw, gdy pracujesz"
echo "równolegle nad kilkoma. W Cowork: przypnij $DIR ORAZ $ROOT/BAZA_WIEDZY jako dwa"
echo "workspace foldery (oba rw — sesja ma dopisywać do bazy wiedzy w trakcie pracy,"
echo "izolacja dotyczy tylko innych spraw, nie bazy wiedzy)."
