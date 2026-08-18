#!/usr/bin/env bash
# eli.sh — dostęp do API Sejmu ELI (Dziennik Ustaw / Monitor Polski).
# Bez klucza API. Zwraca JSON albo pobiera PDF tekstu ujednoliconego.
#
# UWAGA: /text.pdf i /text.html zwracają tekst OGŁOSZONY (pierwotny), nie aktualny!
# Tekst ujednolicony to wyłącznie wpis texts[] o type == "U".
#
# Użycie:
#   eli.sh szukaj "Kodeks cywilny" [rok]      — wyszukaj akt (title = AND po podciągach, bez stemmingu)
#   eli.sh meta DU 2024 1221                  — metadane aktu (status, inForce, texts[], references)
#   eli.sh teksty DU 1964 93                  — lista dostępnych plików z opisem typów
#   eli.sh ujednolicony DU 1964 93 [plik.pdf] — POBIERZ aktualny tekst ujednolicony (typ U)
#   eli.sh referencje DU 2004 1800            — akty zmieniające/uchylające z datami
#   eli.sh obowiazuje DU 2004 1800            — czy akt obowiązuje + czym uchylony
#   eli.sh zmiany 2026-08-01                  — akty zmienione od daty (monitoring)
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
API="https://api.sejm.gov.pl/eli"
_get() { curl -sSfL --max-time 60 "$1"; }

case "${1:-}" in
  szukaj)
    q="${2:?podaj frazę}"; rok="${3:-}"
    url="$API/acts/search?title=$(urlencode "$q")&publisher=DU&limit=20"
    [ -n "$rok" ] && url="$url&year=$rok"
    _get "$url" | jq '{totalCount, items: [.items[] | {address, title, status, inForce, entryIntoForce}]}'
    ;;
  meta)
    _get "$API/acts/${2}/${3}/${4}" | jq '{address,title,status,inForce,entryIntoForce,changeDate,texts,comments}'
    ;;
  teksty)
    _get "$API/acts/${2}/${3}/${4}" | jq -r '
      "TYP | PLIK | ZNACZENIE",
      "----|------|---------",
      (.texts[] | "\(.type) | \(.fileName) | " + (
        if   .type=="U" then "TEKST UJEDNOLICONY (aktualny) <-- TEN"
        elif .type=="T" then "tekst ogłoszony, skład Kancelarii Sejmu"
        elif .type=="O" then "oryginał z Dziennika Ustaw (skan)"
        elif .type=="I" then "kopia oryginału"
        elif .type=="H" then "HTML tekstu OGŁOSZONEGO (nie aktualny!)"
        else "?" end))'
    ;;
  ujednolicony)
    pub="${2}"; rok="${3}"; poz="${4}"; out="${5:-}"
    plik=$(_get "$API/acts/$pub/$rok/$poz" | jq -r '[.texts[]|select(.type=="U")][0].fileName // empty')
    if [ -z "$plik" ]; then
      echo "BRAK tekstu ujednoliconego (typ U) dla $pub/$rok/$poz." >&2
      echo "Sprawdź references['Inf. o tekście jednolitym'] przez: eli.sh referencje $pub $rok $poz" >&2
      exit 2
    fi
    [ -z "$out" ] && out="${pub}_${rok}_${poz}_ujednolicony.pdf"
    curl -sSfL --max-time 300 -o "$out" "$API/acts/$pub/$rok/$poz/text/U/$plik"
    echo "Zapisano: $out"
    echo "SHA-256: $(sha256sum "$out" | cut -d' ' -f1)"
    echo "Nagłówek 'Opracowano na podstawie' mówi, do której nowelizacji tekst jest aktualny — sprawdź go."
    ;;
  referencje)
    _get "$API/acts/${2}/${3}/${4}" | jq '.references | {
      "Akty zmieniające": (."Akty zmieniające" // []),
      "Akty uchylające": (."Akty uchylające" // []),
      "Inf. o tekście jednolitym": (."Inf. o tekście jednolitym" // []),
      "Nowelizacje po tekście jednolitym": (."Nowelizacje po tekście jednolitym" // [])}'
    ;;
  obowiazuje)
    _get "$API/acts/${2}/${3}/${4}" | jq -r '
      "Tytuł:        \(.title)",
      "Status:       \(.status)",
      "inForce:      \(.inForce)",
      "W życie od:   \(.entryIntoForce)",
      "Ost. zmiana:  \(.changeDate)",
      (if (.references."Akty uchylające" // []) | length > 0
       then "UCHYLONY przez: " + ((.references."Akty uchylające"[]) | "\(.id) z dniem \(.date // "?")")
       else "Brak aktów uchylających." end),
      (if .comments != null and .comments != "" then "\nUWAGI (vacatio legis poszczególnych przepisów):\n\(.comments)" else "" end)'
    ;;
  zmiany)
    _get "$API/changes/acts?since=${2}T00:00:00&limit=50" | jq '[.items[]? | {address,title,changeDate}]'
    ;;
  *)
    sed -n '2,20p' "$0"; exit 1;;
esac
