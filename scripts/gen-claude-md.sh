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

ROOT="${1:-.}"
OUT="$ROOT/CLAUDE.md"
DZIS=$(date +%F)

cat > "$OUT" <<EOF
# CLAUDE.md — repozytorium spraw kruczek
<!-- Wygenerowano automatycznie przez gen-claude-md.sh w dniu $DZIS -->
<!-- Aby odświeżyć: bash \${CLAUDE_PLUGIN_ROOT}/scripts/gen-claude-md.sh lub /kruczek:nowy-projekt -->

## Dane nadawcy

Czytaj z: \`_SZABLONY/dane-nadawcy.md\`

Nie pytaj użytkownika o NIP, imię, adres ani e-mail — są w tym pliku. Jeśli plik nie istnieje
lub pole jest puste, poinformuj o tym wprost zamiast zgadywać.

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
2. **Dane drugiej strony** — zawsze z rejestrów (\`podmiot.sh pelny <NIP>\`), nigdy z domysłu.
   Biała lista VAT nie ma endpointu /search/name — nie szukaj po nazwie, szukaj po NIP lub REGON.
   Jeśli masz tylko nazwę: WebFetch stopki/regulaminu firmy → rejestr.io → jeśli nic — zapytaj użytkownika.
3. **Cytaty prawne** — wyłącznie dosłowne, ze źródeł urzędowych (ELI Sejmu, ISAP, EUR-Lex).
   Zanim zaczniesz research — sprawdź BAZA_WIEDZY/.
4. **ARCHIWUM/** — append-only. Nigdy nie edytuj istniejących plików. Każdy nowy plik dostaje sumę SHA-256.
5. **Hipotezy** — wyraźnie oznaczone \`⚠ HIPOTEZA\`, nigdy w treści pisma.
EOF

echo "CLAUDE.md zaktualizowany: $OUT"
