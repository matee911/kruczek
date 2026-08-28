#!/usr/bin/env bash
# archiwa.sh — komendy Wayback Machine, CDX API
# Użycie: archiwa.sh <tryb> [argumenty] --kontakt <e-mail>
#   lokalnie <url> <outdir>             — WŁASNA kopia: treść + nagłówki + SHA-256 + metryczka
#   save    <url>                        — Save Page Now (niezależne poświadczenie IA)
#   pobierz <url> <timestamp> <outdir>  — surowa kopia bez pasków Wayback
#   historia <url>                       — CDX: snapshoty, po jednym na każdą zmianę digestu
#   cdx-url  <url-wzorzec>              — CDX: wszystkie URL-e w domenie (skasowane itd.)
#
# --kontakt <e-mail|URL>  — kontakt do operatora bota, wymagany przez politykę botów
#   Internet Archive. Bierz go z `_SZABLONY/dane-nadawcy.md` (e-mail w sprawach spornych),
#   nie każ użytkownikowi konfigurować środowiska. Alternatywnie zmienna KRUCZEK_CONTACT.
#
# Tryb "timemap" (TimeTravel przez timetravel.mementoweb.org) usunięty 2026-08-28 —
# host nie rozwiązuje się w DNS, usługa jest martwa/przeniesiona.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

# Internet Archive wymaga opisowego User-Agent z kontaktem (archive.org/developers/bots.html).
# Kontakt pochodzi z danych nadawcy sprawy (--kontakt), nie z konfiguracji systemu użytkownika.
# KRUCZEK_MODEL — nazwa modelu, którym faktycznie pracuje bieżąca sesja.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_JSON="${SCRIPT_DIR}/../.claude-plugin/plugin.json"
VERSION=$(python3 -c "import json; print(json.load(open('${PLUGIN_JSON}'))['version'])" 2>/dev/null || echo "0")

# --kontakt wyjmujemy z argumentów, zanim zaczniemy je czytać pozycyjnie (może stać
# w dowolnym miejscu wywołania). Reszta trafia z powrotem do $@ w oryginalnej kolejności.
CONTACT="${KRUCZEK_CONTACT:-}"
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --kontakt) CONTACT="${2:?--kontakt wymaga wartości (e-mail lub URL)}"; shift 2 ;;
    --kontakt=*) CONTACT="${1#--kontakt=}"; shift ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
# bash 3.2 (macOS): "${arr[@]}" na pustej tablicy pod `set -u` to "unbound variable"
set -- "${ARGS[@]+"${ARGS[@]}"}"

UA="kruczek/${VERSION} (+${CONTACT:-brak-kontaktu}; ${KRUCZEK_MODEL:-claude})"

# Kontaktu wymagają wyłącznie tryby uderzające w archive.org — to ICH polityka botów.
# Tryb `lokalnie` pobiera stronę bezpośrednio i musi działać bez żadnej konfiguracji pod IA:
# własna kopia jest fundamentem dowodu, Wayback tylko go wzmacnia.
wymagaj_kontaktu() {
  [ -n "$CONTACT" ] && return 0
  echo "BŁĄD: brak kontaktu do operatora bota." >&2
  echo "Internet Archive wymaga go w User-Agencie (archive.org/developers/bots.html)." >&2
  echo >&2
  echo "Podaj --kontakt <e-mail> — weź e-mail w sprawach spornych z pliku" >&2
  echo "_SZABLONY/dane-nadawcy.md. Jeśli plik nie jest wypełniony: /kruczek:dane-nadawcy." >&2
  echo >&2
  echo "Nie blokuje to zabezpieczenia dowodu — własną kopię zrobisz bez kontaktu:" >&2
  echo "  archiwa.sh lokalnie \"<url>\" <sprawa>/ARCHIWUM" >&2
  exit 1
}

# W sesjach chmurowych (Cowork) proxy egress blokuje web.archive.org niezależnie
# od ustawień allowlisty organizacji — sprawdź to jednym krótkim requestem,
# zamiast czekać na timeout przy właściwym wywołaniu.
check_egress() {
  if ! curl -sf -m 5 -A "$UA" http://web.archive.org/ >/dev/null 2>&1; then
    echo "BŁĄD: web.archive.org jest niedostępny z tej sesji." >&2
    echo "Prawdopodobnie sesja chmurowa (Cowork) z wymuszonym proxy egress —" >&2
    echo "web.archive.org jest tam zablokowany bez możliwości obejścia." >&2
    echo "Przekaż komendę użytkownikowi do wykonania lokalnie (wzorzec z" >&2
    echo "skills/fallback-przegladarka) albo uruchom to w Claude Code lokalnie." >&2
    exit 1
  fi
}

MODE="${1:?Podaj tryb: lokalnie | save | pobierz | historia | cdx-url}"
URL="${2:?Podaj URL}"

case "$MODE" in
  lokalnie)
    # Własna kopia — fundament. Nie zależy od Internet Archive: działa, gdy SPN zwraca 520,
    # blokuje bota albo serwis jest wyłączony. Wayback dokłada do tego niezależne
    # poświadczenie strony trzeciej, ale nie jest warunkiem posiadania dowodu.
    OUTDIR="${3:?Podaj katalog wyjściowy (zwykle <sprawa>/ARCHIWUM)}"
    mkdir -p "$OUTDIR"
    TS=$(date -u +%Y%m%d%H%M%S)
    DOMAIN=$(echo "$URL" | sed -E 's|https?://||; s|/.*||')
    BASE="${OUTDIR}/${TS}-${DOMAIN}"
    echo "Zrzut lokalny: $URL"
    # -D: nagłówki do osobnego pliku; -w: łańcuch przekierowań i realny kod odpowiedzi.
    # Bez -f: stronę błędu 4xx/5xx TEŻ chcemy zachować (sama w sobie bywa dowodem),
    # ale zapisujemy wtedy jawnie jej kod, żeby nikt nie wziął jej za treść właściwą.
    HTTP=$(curl -sSL --max-time 60 -A "$UA" -D "${BASE}.naglowki.txt" \
             -w '%{http_code} %{url_effective}' -o "${BASE}.html" "$URL") || {
      echo "BŁĄD: nie udało się pobrać $URL — nic nie zapisano." >&2
      rm -f "${BASE}.html" "${BASE}.naglowki.txt"
      exit 1
    }
    KOD="${HTTP%% *}"; KONCOWY="${HTTP#* }"
    HASH=$(sha256 "${BASE}.html")
    cat > "${BASE}.zrzut.md" <<META
# Zrzut lokalny — \`${URL}\`

| Pole | Wartość |
|---|---|
| URL żądany | ${URL} |
| URL końcowy (po przekierowaniach) | ${KONCOWY} |
| Kod odpowiedzi | ${KOD} |
| Data i godzina pobrania | $(date -u +%FT%TZ) (UTC) |
| Metoda | curl, User-Agent: \`${UA}\` |
| Plik treści | \`$(basename "${BASE}.html")\` |
| SHA-256 treści | \`${HASH}\` |
| Nagłówki odpowiedzi | \`$(basename "${BASE}.naglowki.txt")\` |

**Wartość dowodowa.** To kopia wykonana przez nadawcę — dowodzi, co nadawca pobrał o tej
godzinie, nie jest poświadczeniem strony trzeciej. Niezależne potwierdzenie daje dopiero
snapshot w Wayback Machine (\`archiwa.sh save\`), jeśli uda się go wykonać. Brak snapshotu
nie unieważnia tego zrzutu.
META
    echo "Zapisano:"
    echo "  treść:     ${BASE}.html"
    echo "  nagłówki:  ${BASE}.naglowki.txt"
    echo "  metryczka: ${BASE}.zrzut.md"
    echo "HTTP ${KOD}, SHA-256: ${HASH}"
    [ "$KOD" != "200" ] && echo "UWAGA: kod ${KOD} — zapisana treść to prawdopodobnie strona błędu." >&2
    echo "Teraz (opcjonalnie) niezależny snapshot: archiwa.sh save \"${URL}\" --kontakt <e-mail>"
    ;;

  save)
    wymagaj_kontaktu
    check_egress
    echo "Archiwizuję: $URL"
    # `|| true` i osobny kod wyjścia: pod `set -e` samo podstawienie z niezerowym curl-em
    # ubijało skrypt, zanim zdążył wypisać cokolwiek diagnostycznego (gałąź else niżej).
    # Save Page Now potrafi mielić długo — stąd --max-time zamiast czekania w nieskończoność.
    RESP=$(curl -sI --max-time 120 -A "$UA" "https://web.archive.org/save/${URL}" 2>&1) || CURL_RC=$?
    if [ -n "${CURL_RC:-}" ]; then
      echo "BŁĄD: curl zakończył się kodem ${CURL_RC} przy zapisie ${URL}" >&2
      [ "$CURL_RC" = 28 ] && echo "(kod 28 = przekroczony limit czasu 120 s)" >&2
      echo "Odpowiedź/komunikat:" >&2
      echo "$RESP" | head -20 >&2
      echo "Spróbuj ręcznie: https://web.archive.org/save/${URL}" >&2
      exit 1
    fi
    LOCATION=$(echo "$RESP" | grep -i '^location:' | tr -d '\r' | awk '{print $2}' || true)
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
    wymagaj_kontaktu
    check_egress
    TIMESTAMP="${3:?Podaj timestamp (14 cyfr, np. 20260818120000)}"
    OUTDIR="${4:?Podaj katalog wyjściowy}"
    mkdir -p "$OUTDIR"
    # sed -E: BSD sed na macOS nie zna \? w BRE — bez tego DOMAIN wychodziło jako "https:"
    # i wszystkie snapshoty lądowały pod nazwą wayback-<ts>-https:.html
    DOMAIN=$(echo "$URL" | sed -E 's|https?://||; s|/.*||')
    OUTFILE="${OUTDIR}/wayback-${TIMESTAMP}-${DOMAIN}.html"
    echo "Pobieram: https://web.archive.org/web/${TIMESTAMP}id_/${URL}"
    # -f: kod HTTP 4xx/5xx ma być błędem, nie treścią pliku. Bez tego do ARCHIWUM trafiała
    # strona błędu albo plik pusty — i dostawała sumę kontrolną jak prawdziwy dowód.
    if ! curl -sfL --max-time 120 -A "$UA" "https://web.archive.org/web/${TIMESTAMP}id_/${URL}" -o "$OUTFILE"; then
      RC=$?
      rm -f "$OUTFILE"
      echo "BŁĄD: nie udało się pobrać snapshotu (curl ${RC}); nic nie zapisano." >&2
      echo "Sprawdź, czy timestamp ${TIMESTAMP} istnieje: archiwa.sh historia \"${URL}\"" >&2
      exit 1
    fi
    if [ ! -s "$OUTFILE" ]; then
      rm -f "$OUTFILE"
      echo "BŁĄD: snapshot pobrał się pusty; nic nie zapisano." >&2
      exit 1
    fi
    HASH=$(sha256 "$OUTFILE")
    echo "Zapisano: $OUTFILE"
    echo "SHA-256:  $HASH"
    ;;

  historia)
    wymagaj_kontaktu
    check_egress
    echo "Historia snapshotów (po jednym na każdą zmianę digestu): $URL"
    curl -s -A "$UA" "http://web.archive.org/cdx/search/cdx?url=${URL}&output=json&fl=timestamp,digest,statuscode,length&collapse=digest" \
      | python3 -c "
import json, sys
# CDX przy przeciążeniu/limicie zwraca pustą odpowiedź albo HTML — bez tego json.load
# wywalał traceback, nieodróżnialny od błędu skryptu.
raw = sys.stdin.read().strip()
if not raw:
    print('Brak odpowiedzi z CDX (puste ciało). Możliwy limit zapytań — spróbuj ponownie za chwilę.', file=sys.stderr)
    sys.exit(1)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print('CDX zwróciło odpowiedź, która nie jest JSON-em (pierwsze 200 znaków):', file=sys.stderr)
    print(raw[:200], file=sys.stderr)
    sys.exit(1)
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

  cdx-url)
    wymagaj_kontaktu
    check_egress
    echo "CDX — wszystkie URL-e w domenie (łącznie z usuniętymi): $URL"
    curl -s -A "$UA" "http://web.archive.org/cdx/search/cdx?url=${URL}*&output=json&fl=timestamp,original,statuscode&collapse=urlkey&limit=200" \
      | python3 -c "
import json, sys
raw = sys.stdin.read().strip()
if not raw:
    print('Brak odpowiedzi z CDX (puste ciało). Możliwy limit zapytań — spróbuj ponownie za chwilę.', file=sys.stderr)
    sys.exit(1)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print('CDX zwróciło odpowiedź, która nie jest JSON-em (pierwsze 200 znaków):', file=sys.stderr)
    print(raw[:200], file=sys.stderr)
    sys.exit(1)
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
    echo "Dostępne: lokalnie | save | pobierz | historia | cdx-url" >&2
    exit 1
    ;;
esac
