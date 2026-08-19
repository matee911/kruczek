#!/usr/bin/env bash
# gen-claude-md.sh — generuje CLAUDE.md w repozytorium spraw.
#   gen-claude-md.sh [KATALOG]      (domyślnie bieżący)
#
# Wczytuje _SZABLONY/dane-nadawcy.md i buduje CLAUDE.md z:
#   - danymi nadawcy (kto pisze, NIP, adres, e-mail)
#   - nawigacją po strukturze projektu
#   - instrukcją dla Clauda: skąd brać dane zamiast pytać
#
# Bezpieczne do wielokrotnego wywołania — nadpisuje plik.
set -euo pipefail

ROOT="${1:-.}"
DANE="$ROOT/_SZABLONY/dane-nadawcy.md"
OUT="$ROOT/CLAUDE.md"

if [ ! -f "$DANE" ]; then
  echo "BŁĄD: nie znalazłem $DANE — najpierw wypełnij dane nadawcy." >&2
  echo "Wzorzec: $(dirname "$(dirname "$0")")/templates/dane-nadawcy.md" >&2
  exit 1
fi

# Wyciągnij wartość z wiersza tabeli Markdown: "| Etykieta | wartość |" lub "| Etykieta | wartość | opcjonalna kolumna |"
# Zwraca trzecią kolumnę (indeks 3 przy split na |).
_pole() {
  local label="$1"
  grep -m1 "| ${label} |" "$DANE" \
    | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3); print $3}'
}

ROLA=$(_pole "Występuję jako")
IMIE=$(_pole "Imię i nazwisko")
FIRMA=$(_pole "Firma (pełne brzmienie, jeśli przedsiębiorca)")
FORMA=$(_pole "Forma prawna")
NIP=$(_pole "NIP")
REGON=$(_pole "REGON")
KRS=$(_pole "KRS")
ADR_KORESP=$(grep -m1 "Do korespondencji" "$DANE" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3); print $3}')
ADR_SIEDZ=$(_pole "Zamieszkania / siedziby")
EMAIL=$(grep -m1 "E-mail główny" "$DANE" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3); print $3}')
EMAIL_SPORY=$(grep -m1 "E-mail w sprawach spornych" "$DANE" | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3); print $3}')
MIEJSCOWOSC=$(_pole "Miejscowość w nagłówku pism")
TON=$(grep -m1 "Ton pism:" "$DANE" | sed 's/.*Ton pism: //' | sed 's/<//;s/>//' | awk '{print $1}')
TERMIN=$(grep -m1 "Domyślny termin" "$DANE" | sed 's/.*Domyślny termin w wezwaniach: //' | sed 's/<//;s/>//' | awk '{print $1}')

DZIS=$(date +%F)

cat > "$OUT" <<EOF
# CLAUDE.md — repozytorium spraw kruczek
<!-- Wygenerowano automatycznie przez gen-claude-md.sh w dniu $DZIS -->
<!-- Aby zaktualizować: /kruczek:dane-nadawcy  lub  scripts/gen-claude-md.sh -->

## Dane nadawcy

> Używaj tych danych w każdym piśmie. Nie pytaj użytkownika o NIP, adres ani imię —
> są tu. Jeśli coś jest puste, poinformuj że brakuje wartości w _SZABLONY/dane-nadawcy.md.

| Pole | Wartość |
|---|---|
| Rola | $ROLA |
| Imię i nazwisko | $IMIE |
| Firma | $FIRMA |
| Forma prawna | $FORMA |
| NIP | $NIP |
| REGON | $REGON |
| KRS | $KRS |
| Adres siedziby / zamieszkania | $ADR_SIEDZ |
| **Adres do korespondencji** | $ADR_KORESP |
| Miejscowość w nagłówku | $MIEJSCOWOSC |
| E-mail główny | $EMAIL |
| E-mail w sprawach spornych | $EMAIL_SPORY |
| Ton pism | $TON |
| Domyślny termin wezwań | $TERMIN |

Pełny plik źródłowy: \`_SZABLONY/dane-nadawcy.md\`

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
- **_SZABLONY/** — wzory pism, dane nadawcy
- **KONWENCJE.md** — zasady prowadzenia archiwum, nazewnictwa, chronologii — przeczytaj przed każdą pracą na plikach

Każda sprawa: \`<PODMIOT>/index.md\` (manifest, chronologia, ustalenia, TODO).

## Zasady pracy

1. **Dane nadawcy** — zawsze z tej sekcji powyżej, nigdy z pamięci ani domysłu.
2. **Dane drugiej strony** — zawsze z rejestrów (\`podmiot.sh pelny <NIP>\`), nigdy z domysłu.
   Biała lista VAT nie ma endpointu /search/name — nie szukaj po nazwie, szukaj po NIP lub REGON.
   Jeśli masz tylko nazwę: WebFetch stopki/regulaminu firmy → rejestr.io → jeśli nic — zapytaj użytkownika.
3. **Cytaty prawne** — wyłącznie dosłowne, ze źródeł urzędowych (ELI Sejmu, ISAP, EUR-Lex).
   Zanim zaczniesz research — sprawdź BAZA_WIEDZY/.
4. **ARCHIWUM/** — append-only. Nigdy nie edytuj istniejących plików. Każdy nowy plik dostaje sumę SHA-256.
5. **Hipotezy** — wyraźnie oznaczone \`⚠ HIPOTEZA\`, nigdy w treści pisma.
EOF

echo "CLAUDE.md zaktualizowany: $OUT"
