#!/usr/bin/env bash
# archiwa.sh — komendy Wayback Machine, CDX API, TimeTravel
# Użycie: archiwa.sh <tryb> [argumenty]
#   save    <url>                        — Save Page Now
#   pobierz <url> <timestamp> <outdir>  — surowa kopia bez pasków Wayback
#   historia <url>                       — CDX: lista snapshotów z digestami (realne zmiany)
#   timemap  <url>                       — TimeTravel: wszystkie archiwa
#   cdx-url  <url-wzorzec>              — CDX: wszystkie URL-e w domenie (skasowane itd.)
set -euo pipefail

MODE="${1:?Podaj tryb: save | pobierz | historia | timemap | cdx-url}"
URL="${2:?Podaj URL}"

case "$MODE" in
  save)
    echo "Archiwizuję: $URL"
    RESP=$(curl -sI "https://web.archive.org/save/${URL}" 2>&1)
    LOCATION=$(echo "$RESP" | grep -i '^location:' | tr -d '\r' | awk '{print $2}')
    if [ -n "$LOCATION" ]; then
      TS=$(echo "$LOCATION" | grep -oE '[0-9]{14}' | head -1)
      echo "OK: https://web.archive.org/web/${TS}/${URL}"
      echo "Timestamp: ${TS}"
    else
      echo "OSTRZEŻENIE: Save Page Now nie zwrócił lokalizacji." >&2
      echo "Odpowiedź serwera:" >&2
      echo "$RESP" | head -20 >&2
      echo "Spróbuj ręcznie: https://web.archive.org/save/${URL}"
      exit 1
    fi
    ;;

  pobierz)
    TIMESTAMP="${3:?Podaj timestamp (14 cyfr, np. 20260818120000)}"
    OUTDIR="${4:?Podaj katalog wyjściowy}"
    mkdir -p "$OUTDIR"
    DOMAIN=$(echo "$URL" | sed 's|https\?://||; s|/.*||')
    OUTFILE="${OUTDIR}/wayback-${TIMESTAMP}-${DOMAIN}.html"
    echo "Pobieram: https://web.archive.org/web/${TIMESTAMP}id_/${URL}"
    curl -sL "https://web.archive.org/web/${TIMESTAMP}id_/${URL}" -o "$OUTFILE"
    HASH=$(shasum -a 256 "$OUTFILE" | awk '{print $1}')
    echo "Zapisano: $OUTFILE"
    echo "SHA-256:  $HASH"
    ;;

  historia)
    echo "Historia snapshotów (tylko realne zmiany treści): $URL"
    curl -s "http://web.archive.org/cdx/search/cdx?url=${URL}&output=json&fl=timestamp,digest,statuscode,length&collapse=digest" \
      | python3 -c "
import json, sys
data = json.load(sys.stdin)
if not data or len(data) <= 1:
    print('Brak snapshotów w Wayback Machine.')
    sys.exit(0)
header = data[0]
rows = data[1:]
print(f'Znaleziono {len(rows)} unikalnych wersji:')
for r in rows:
    d = dict(zip(header, r))
    ts = d.get('timestamp','?')
    date = f'{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}' if len(ts)>=12 else ts
    print(f'  {date}  status={d.get(\"statuscode\",\"?\")}  digest={d.get(\"digest\",\"?\")[:12]}...')
"
    ;;

  timemap)
    echo "TimeTravel — wszystkie archiwa dla: $URL"
    curl -s "http://timetravel.mementoweb.org/timemap/link/${URL}" | head -40
    ;;

  cdx-url)
    echo "CDX — wszystkie URL-e w domenie (łącznie z usuniętymi): $URL"
    curl -s "http://web.archive.org/cdx/search/cdx?url=${URL}*&output=json&fl=timestamp,original,statuscode&collapse=urlkey&limit=200" \
      | python3 -c "
import json, sys
data = json.load(sys.stdin)
if not data or len(data) <= 1:
    print('Brak wyników.')
    sys.exit(0)
header = data[0]
for r in data[1:]:
    d = dict(zip(header, r))
    print(f'{d.get(\"timestamp\",\"?\")[:8]}  {d.get(\"statuscode\",\"?\")}  {d.get(\"original\",\"?\")}')
"
    ;;

  *)
    echo "Nieznany tryb: $MODE" >&2
    echo "Dostępne: save | pobierz | historia | timemap | cdx-url" >&2
    exit 1
    ;;
esac
