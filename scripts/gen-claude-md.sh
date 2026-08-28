#!/usr/bin/env bash
# gen-claude-md.sh — generuje CLAUDE.md w repozytorium spraw.
#   gen-claude-md.sh [KATALOG]      (domyślnie bieżący)
#
# Generuje mapę projektu i zasady pracy dla Clauda.
# Nie zawiera danych osobowych — dane nadawcy zostają w _SZABLONY/dane-nadawcy.md.
#
# Bezpieczne do wielokrotnego wywołania — nadpisuje plik.
# Bezpieczne do commitowania — nie ma w nim PII.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-.}"
OUT="$ROOT/CLAUDE.md"
DZIS=$(date +%F)

# Status pól krytycznych dane-nadawcy.md — tylko status (OK/BRAK), nigdy wartości,
# żeby PII nie trafiały do pliku, który bywa commitowany.
STATUS_RAW=$(python3 "$SCRIPT_DIR/dane-nadawcy-status.py" "$ROOT/_SZABLONY/dane-nadawcy.md" 2>/dev/null || true)
STATUS_BLOK=$(printf '%s\n' "$STATUS_RAW" | awk '
  /^OK / { print "- ✓ " substr($0,4); next }
  /^BRAK-PLIK/ { next }
  /^BRAK / { print "- ⚠ BRAK: " substr($0,6); next }
')
if printf '%s\n' "$STATUS_RAW" | grep -q '^BRAK-PLIK$'; then
  STATUS_BLOK="⚠ Plik _SZABLONY/dane-nadawcy.md nie istnieje. Nie zgaduj danych nadawcy —
uruchom /kruczek:dane-nadawcy albo zapytaj użytkownika wprost."
fi

cat > "$OUT" <<EOF
# CLAUDE.md — repozytorium spraw kruczek
<!-- Wygenerowano automatycznie przez gen-claude-md.sh w dniu $DZIS -->
<!-- Aby odświeżyć: bash \${CLAUDE_PLUGIN_ROOT}/scripts/gen-claude-md.sh lub /kruczek:nowy-projekt -->

## Dane nadawcy

Czytaj z: \`_SZABLONY/dane-nadawcy.md\`

Stan pól krytycznych (sprawdzony automatycznie $DZIS przy generowaniu tego pliku):

$STATUS_BLOK

Pola ✓ są wypełnione — nie pytaj o nie użytkownika. Pola ⚠ BRAK **musisz** dopytać,
zanim ich użyjesz w piśmie lub zgłoszeniu — nigdy nie wpisuj do dokumentu, który ma
zostać wysłany, tekstu zastępczego w rodzaju "[NAZWISKO — UZUPEŁNIĆ]"; zamiast tego
albo dopytaj, albo zostaw pole \`class="fill"\` i wypisz je użytkownikowi jako listę
do uzupełnienia.

Ten status jest zapisany w chwili generowania — jeśli \`dane-nadawcy.md\` zmienił się
później, uruchom ponownie \`/kruczek:dane-nadawcy\` (samo odświeży ten plik) albo
\`bash \${CLAUDE_PLUGIN_ROOT}/scripts/gen-claude-md.sh\`.

## Nawigacja po projekcie

\`\`\`
$(cd "$ROOT" && find . -maxdepth 3 \
    -not -path './.git/*' \
    -not -path './BAZA_WIEDZY/przepisy/*' \
    -not -path './BAZA_WIEDZY/orzecznictwo/*' \
    | sort | sed 's|^\./||' | grep -v '^$')
\`\`\`

- **index.md** — rejestr wszystkich spraw (status, terminy)
- **BAZA_WIEDZY/** — przepisy i orzecznictwo wielokrotnego użytku; sprawdź tu zanim zaczniesz research
- **_SZABLONY/dane-nadawcy.md** — dane nadawcy do pism (NIP, adres, e-mail, preferencje)
- **KONWENCJE.md** — zasady prowadzenia archiwum, nazewnictwa, chronologii — przeczytaj przed każdą pracą na plikach

Każda sprawa: \`<PODMIOT>/index.md\` (manifest, chronologia, ustalenia, TODO).

## Zasady pracy

1. **Dane nadawcy** — zawsze z \`_SZABLONY/dane-nadawcy.md\`, nigdy z pamięci ani domysłu.
2. **Dane drugiej strony** — zawsze z rejestrów, nigdy z domysłu. Jak dokładnie (który
   endpoint, kolejność NIP→biała lista→KRS, co zrobić gdy znasz tylko nazwę) — zob.
   skill \`zrodla-rejestry\` i \`podmiot.sh\`. Nie zgaduj szczegółów API na pamięć.
3. **Cytaty prawne** — wyłącznie dosłowne, ze źródeł urzędowych (ELI Sejmu, ISAP, EUR-Lex).
   Zanim zaczniesz research — sprawdź BAZA_WIEDZY/.
4. **ARCHIWUM/** — append-only. Nigdy nie edytuj istniejących plików. Każdy nowy plik dostaje sumę SHA-256.
5. **Hipotezy** — wyraźnie oznaczone \`⚠ HIPOTEZA\`, nigdy w treści pisma.
EOF

echo "CLAUDE.md zaktualizowany: $OUT"
