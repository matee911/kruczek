#!/usr/bin/env bash
# eurlex.sh — pobieranie dokumentów z EUR-Lex po numerze CELEX (akty UE, wyroki TSUE, ...).
# Bez klucza API. Zapisuje plik i podaje SHA-256 — do BAZA_WIEDZY/ albo ARCHIWUM/.
#
# Użycie:
#   eurlex.sh html <CELEX> [język] [plik]   — tekst HTML (domyślnie PL)
#   eurlex.sh pdf  <CELEX> [język] [plik]   — PDF
#
# CELEX: 62010CJ0618 (wyrok C-618/10), 32016R0679 (RODO, akt bazowy),
#        02016R0679-20160504 (RODO, wersja skonsolidowana na dzień).
# Język: kod dwuliterowy wersji językowej UE (PL, EN, DE, FR, ...).
#
# EUR-Lex stoi za AWS WAF: przy zbyt częstych zapytaniach odpowiada 202 z nagłówkiem
# x-amzn-waf-action: challenge (wyzwanie JavaScript). Nie obchodzimy go — skrypt kończy
# się kodem 2 i odsyła do WebFetch / skillu fallback-przegladarka.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

BASE="${EURLEX_BASE:-https://eur-lex.europa.eu}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=$(python3 -c "import json; print(json.load(open('${SCRIPT_DIR}/../.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo "0")
UA="kruczek/${VERSION} (+https://github.com/matee911/kruczek)"
JEZYKI=" BG ES CS DA DE ET EL EN FR GA HR IT LV LT HU MT NL PL PT RO SK SL FI SV "

# robots.txt EUR-Lex: Crawl-delay 10. Znacznik czasu ostatniego zapytania trzymamy
# w TMPDIR, żeby odstęp działał między kolejnymi wywołaniami skryptu.
ODSTEP=10
ZNACZNIK="${TMPDIR:-/tmp}/kruczek-eurlex.ostatnie"
odczekaj() {
  local teraz ostatnie
  teraz=$(date +%s)
  ostatnie=$(cat "$ZNACZNIK" 2>/dev/null || echo 0)
  if [ $((teraz - ostatnie)) -lt "$ODSTEP" ]; then
    sleep $((ODSTEP - (teraz - ostatnie)))
  fi
  date +%s >"$ZNACZNIK"
}

pobierz() {
  local format="$1" celex jezyk ext oczekiwany url out kod ctype
  celex=$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')
  jezyk=$(printf '%s' "${3:-PL}" | tr '[:lower:]' '[:upper:]')
  if ! [[ "$celex" =~ ^[0-9CE][0-9]{4}[A-Z]{1,2}[0-9A-Z()_]+(-[0-9]{8})?$ ]]; then
    echo "BŁĄD: '$celex' nie wygląda na numer CELEX (np. 62010CJ0618, 32016R0679)." >&2
    exit 1
  fi
  case "$JEZYKI" in
    *" $jezyk "*) ;;
    *) echo "BŁĄD: nieznany język '$jezyk'. Dostępne:$JEZYKI" >&2; exit 1 ;;
  esac
  case "$format" in
    HTML) ext=html; oczekiwany="text/html" ;;
    PDF)  ext=pdf;  oczekiwany="application/pdf" ;;
  esac
  url="$BASE/legal-content/$jezyk/TXT/$format/?uri=CELEX:$celex"
  out="${4:-CELEX_${celex}_${jezyk}.${ext}}"
  # globalne, nie local: trap EXIT odpala się już poza funkcją (set -u)
  tmp=$(mktemp); naglowki=$(mktemp)
  trap 'rm -f "$tmp" "$naglowki"' EXIT

  odczekaj
  kod=$(curl -sSL --max-time 300 -A "$UA" -H "Accept-Language: $(printf '%s' "$jezyk" | tr '[:upper:]' '[:lower:]')" \
    -D "$naglowki" -o "$tmp" -w '%{http_code}' "$url")
  ctype=$(grep -i '^content-type:' "$naglowki" | tail -1 | tr -d '\r' || true)

  if grep -qi '^x-amzn-waf-action: *challenge' "$naglowki" || [ "$kod" = 202 ]; then
    echo "EUR-Lex odpowiedział wyzwaniem anty-botowym (AWS WAF, HTTP $kod) — nie obchodzimy go." >&2
    echo "Blokada jest czasowa (po serii zapytań) — odczekaj kilka minut i ponów." >&2
    echo "WebFetch trafia na tę samą blokadę, ale bywa, że przechodzi: $url" >&2
    echo "Gdy i to zawiedzie: skill kruczek:fallback-przegladarka." >&2
    exit 2
  fi
  if [ "$kod" != 200 ] || [ ! -s "$tmp" ] || [[ "$ctype" != *"$oczekiwany"* ]]; then
    echo "BŁĄD: EUR-Lex zwrócił HTTP $kod, ${ctype:-brak Content-Type} (oczekiwano $oczekiwany)." >&2
    echo "Dokument może nie istnieć w wersji $jezyk albo w formacie $format: $url" >&2
    exit 2
  fi

  mv "$tmp" "$out"
  echo "Zapisano: $out"
  echo "SHA-256: $(sha256 "$out")"
  echo "Źródło:  $url"
  echo "Pobrano: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

case "${1:-}" in
  html) pobierz HTML "${2:?podaj CELEX}" "${3:-}" "${4:-}" ;;
  pdf)  pobierz PDF  "${2:?podaj CELEX}" "${3:-}" "${4:-}" ;;
  *) sed -n '2,15p' "$0"; exit 1 ;;
esac
