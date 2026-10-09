#!/usr/bin/env bash
# nowa-sprawa.sh — zakłada katalog sprawy z index.md.
#   nowa-sprawa.sh "<Nazwa podmiotu>" "<przedmiot sprawy>" [KATALOG-PROJEKTU] ["<w imieniu: osoba>"]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# teczka.py startuje przez uv (Python ≥ 3.11); PYTHON nadpisuje interpreter w testach.
TECZKA=("$SCRIPT_DIR/teczka.py")
[ -n "${PYTHON:-}" ] && TECZKA=("$PYTHON" "$SCRIPT_DIR/teczka.py")
NAZWA="${1:?podaj nazwę podmiotu}"; PRZEDMIOT="${2:?podaj przedmiot sprawy}"; ROOT="${3:-.}"; W_IMIENIU="${4:-}"
SLUG=$(printf %s "$NAZWA" | iconv -f UTF-8 -t ASCII//TRANSLIT 2>/dev/null || printf %s "$NAZWA")
# sed -E (ERE): BSD sed na macOS nie rozumie \+ w podstawowym wyrażeniu regularnym —
# bez -E slug zostawał niezmieniony i katalog sprawy dostawał nazwę ze spacjami i kropkami.
SLUG=$(printf %s "$SLUG" | tr 'A-Z' 'a-z' | sed -E 's/[^a-z0-9]+/-/g; s/^-//; s/-$//')
DIR="$ROOT/$SLUG"; DZIS=$(date +%F)
if [ -f "$DIR/index.md" ]; then
  if [ -f "$DIR/sprawa.json" ]; then
    echo "Sprawa już istnieje: $DIR/index.md"
  else
    echo "Sprawa w starym formacie: $DIR — przenieś: /kruczek:migruj"
  fi
  exit 0
fi
mkdir -p "$DIR"
# Najpierw sprawa.json: gdy Python zawiedzie, nie zostaje index.md w starym formacie.
NOWA=(nowa "$DIR" --tytul "$PRZEDMIOT" --strona "$NAZWA" --zadania-startowe)
[ -n "$W_IMIENIU" ] && NOWA+=(--w-imieniu "$W_IMIENIU")
"${TECZKA[@]}" "${NOWA[@]}" >/dev/null
mkdir -p "$DIR"/{ARCHIWUM,ROBOCZE}
cat > "$DIR/index.md" <<EOF
# SPRAWA: $NAZWA

| | |
|---|---|
| **Podmiot** | $NAZWA |
| **Przedmiot** | $PRZEDMIOT |
| **Występuję jako** | _(osoba fizyczna / przedsiębiorca / w imieniu: <kto> — tożsamości w \`_SZABLONY/dane-nadawcy.md\`)_ |
| **Dane rejestrowe** | _(NIP / KRS / adres — uzupełnij: \`podmiot.sh pelny <NIP>\`)_ |
| **Założono** | $DZIS |

## 1. Chronologia

<!-- kruczek:chronologia -->
<!-- /kruczek:chronologia -->

## Terminy

<!-- kruczek:terminy -->
<!-- /kruczek:terminy -->

## Zadania

<!-- kruczek:zadania -->
<!-- /kruczek:zadania -->

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

## 6. Ścieżka eskalacji

_(kolejne kroki po bezskutecznym upływie terminu — od najtańszego do najdroższego)_
EOF
"${TECZKA[@]}" zdarzenie "$DIR" --typ inne --opis "Założenie sprawy" >/dev/null
echo "Założono sprawę: $DIR"
echo "Dopisz ją do rejestru w $ROOT/index.md:"
echo "| | $NAZWA | $PRZEDMIOT | $DZIS |"
echo ""
echo "Dalszą pracę nad tą sprawą prowadź w OSOBNEJ sesji przypiętej do $DIR"
echo "(nie w sesji obejmującej cały $ROOT) — zapobiega myleniu spraw, gdy pracujesz"
echo "równolegle nad kilkoma. W Cowork: przypnij $DIR ORAZ $ROOT/BAZA_WIEDZY jako dwa"
echo "workspace foldery (oba rw — sesja ma dopisywać do bazy wiedzy w trakcie pracy,"
echo "izolacja dotyczy tylko innych spraw, nie bazy wiedzy)."
