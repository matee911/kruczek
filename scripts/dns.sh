#!/usr/bin/env bash
# dns.sh — rekordy DNS i konfiguracja poczty przez DNS-over-HTTPS. Bez dig/whois, bez kluczy.
#
#   dns.sh rekordy <domena>              A, AAAA, MX, NS, TXT, SOA, CNAME
#   dns.sh poczta <domena>               MX + SPF + DMARC + typowe selektory DKIM
#   dns.sh dkim <domena> <selektor>      konkretny selektor DKIM (selektor bierz z nagłówka s= wiadomości)
#   dns.sh typ <domena> <TYP>            dowolny typ rekordu
#   dns.sh raport <domena>               pełny raport markdown do załączenia jako dowód
#   dns.sh porownaj <d1> <d2> [d3...]    czy domeny stoją na tej samej infrastrukturze
#
# Rozstrzygacze: dns.google i cloudflare-dns.com (dwa niezależne — rozbieżność bywa istotna).
# DNS pokazuje stan NA TERAZ. Jeśli rekord ma znaczenie dowodowe, zapisz raport do ARCHIWUM
# z datą odczytu — za miesiąc może go już nie być.
set -euo pipefail
Q() { # $1=nazwa $2=typ $3=resolver(google|cf)
  if [ "${3:-google}" = cf ]; then
    curl -sSfL --max-time 20 -H "accept: application/dns-json" \
      "https://cloudflare-dns.com/dns-query?name=$1&type=$2"
  else
    curl -sSfL --max-time 20 "https://dns.google/resolve?name=$1&type=$2"
  fi
}
DATA() { Q "$1" "$2" "${3:-google}" | jq -r '.Answer[]?.data // empty'; }
POKAZ() { local v; v=$(DATA "$1" "$2" "${3:-}" || true); [ -n "$v" ] && printf '%-6s %s\n' "$2" "$(echo "$v" | paste -sd' | ' -)" || printf '%-6s —\n' "$2"; }

rekordy() {
  echo "== DNS: $1  (odczyt: $(date -u +%FT%TZ), resolver dns.google) =="
  for t in A AAAA CNAME MX NS TXT SOA CAA; do POKAZ "$1" "$t"; done
}
spf()   { DATA "$1" TXT | grep -i 'v=spf1' || echo "BRAK rekordu SPF"; }
dmarc() { DATA "_dmarc.$1" TXT | grep -i 'v=DMARC1' || echo "BRAK rekordu DMARC"; }
dkim()  { DATA "$2._domainkey.$1" TXT || echo "brak selektora $2"; }

poczta() {
  local d="$1"
  echo "== Konfiguracja poczty: $d  (odczyt: $(date -u +%FT%TZ)) =="
  echo "-- MX --";    DATA "$d" MX || echo "BRAK MX"
  echo "-- SPF --";   spf "$d"
  echo "-- DMARC --"; dmarc "$d"
  echo "-- DKIM (typowe selektory) --"
  for s in default dkim mail google selector1 selector2 s1 s2 k1 key1 smtp zoho mandrill sendgrid; do
    v=$(DATA "${s}._domainkey.$d" TXT || true)
    [ -n "$v" ] && echo "  $s: ${v:0:120}…"
  done
  echo
  echo "Wskazówka: prawdziwy selektor DKIM znajdziesz w nagłówku wiadomości —"
  echo "  DKIM-Signature: ... s=<selektor>; d=<domena>"
  echo "Potem: dns.sh dkim $d <selektor>"
}

raport() {
  local d="$1" ts; ts=$(date -u +%FT%TZ)
  cat <<EOF
# Raport DNS — \`$d\`

- **Data i godzina odczytu:** $ts (UTC)
- **Rozstrzygacze:** dns.google oraz cloudflare-dns.com (DNS-over-HTTPS)
- **Uwaga dowodowa:** DNS odzwierciedla stan na moment odczytu. Rekordy można zmienić w kilka minut,
  dlatego raport zachowuje datę i godzinę. Wynik z dwóch niezależnych rozstrzygaczy zmniejsza ryzyko
  zarzutu, że odczyt pochodzi z zatrutej pamięci podręcznej.

## Rekordy podstawowe

| Typ | Wartość |
|---|---|
EOF
  for t in A AAAA CNAME MX NS TXT SOA CAA; do
    v=$(DATA "$d" "$t" || true)
    if [ -n "$v" ]; then echo "$v" | while read -r l; do printf '| %s | `%s` |\n' "$t" "$l"; done
    else printf '| %s | — |\n' "$t"; fi
  done
  cat <<EOF

## Poczta

| Element | Wartość |
|---|---|
| SPF | \`$(spf "$d" | head -1)\` |
| DMARC | \`$(dmarc "$d" | head -1)\` |

## Kontrola krzyżowa (cloudflare-dns.com)

| Typ | Wartość |
|---|---|
EOF
  for t in A MX NS; do
    v=$(DATA "$d" "$t" cf || true)
    if [ -n "$v" ]; then echo "$v" | while read -r l; do printf '| %s | `%s` |\n' "$t" "$l"; done
    else printf '| %s | — |\n' "$t"; fi
  done
  echo
  echo "## Dane rejestracyjne domeny"
  echo
  echo 'Uzupełnij przez `podmiot.sh domena '"$d"'` (RDAP). Data rejestracji bliska dacie spornego'
  echo 'zdarzenia jest samodzielnym dowodem — domena założona na potrzeby jednej akcji.'
}

porownaj() {
  echo "== Porównanie infrastruktury  (odczyt: $(date -u +%FT%TZ)) =="
  printf '%-32s %-28s %-28s %s\n' "DOMENA" "NS" "MX" "A"
  for d in "$@"; do
    printf '%-32s %-28s %-28s %s\n' "$d" \
      "$(DATA "$d" NS | sort | paste -sd, - | cut -c1-27)" \
      "$(DATA "$d" MX | sort | paste -sd, - | cut -c1-27)" \
      "$(DATA "$d" A  | sort | paste -sd, - | cut -c1-24)"
  done
  echo
  echo "Wspólne serwery nazw, wspólny MX albo ten sam adres IP to poszlaka, że domenami"
  echo "dysponuje jeden podmiot. Poszlaka — nie dowód: współdzielony hosting daje ten sam"
  echo "wynik dla tysięcy niepowiązanych klientów. Wzmocnij ustaleniem z RDAP i treścią stron."
}

case "${1:-}" in
  rekordy)  rekordy "$2" ;;
  poczta)   poczta "$2" ;;
  dkim)     dkim "$2" "$3" ;;
  typ)      DATA "$2" "$3" ;;
  raport)   raport "$2" ;;
  porownaj) shift; porownaj "$@" ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
