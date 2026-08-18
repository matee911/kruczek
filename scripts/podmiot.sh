#!/usr/bin/env bash
# podmiot.sh — ustalanie tożsamości przeciwnika z otwartych rejestrów. Bez kluczy API.
#
#   podmiot.sh nip 5252344078        — Biała lista VAT (MF): nazwa, REGON, KRS, adres, rachunki
#   podmiot.sh krs 0000240611 [P|S]  — Odpis aktualny z KRS (P=przedsiębiorcy, S=stowarzyszenia)
#   podmiot.sh domena example.pl     — RDAP: rejestrator, abonent, daty, nameservery (.pl przez NASK)
#   podmiot.sh strona https://x.pl   — nagłówki HTTP + łańcuch przekierowań (dowód na rotację domen)
#   podmiot.sh pelny 5252344078      — nip -> (jeśli jest KRS) krs, jednym ciągiem
#
# Ograniczenia (stan 08.2026):
#   CEIDG API v3 wymaga tokenu Bearer — brak wsparcia.
#   .eu nie ma publicznego RDAP/WHOIS po HTTP (EURid za anty-botem).
set -euo pipefail
today=$(date +%F)

nip() {
  local n="${1//[^0-9]/}"
  curl -sSfL --max-time 30 "https://wl-api.mf.gov.pl/api/search/nip/${n}?date=${today}" \
  | jq '.result.subject | {name, nip, regon, krs, statusVat, workingAddress, residenceAddress,
                           registrationLegalDate, representatives, accountNumbers}'
}
krs() {
  curl -sSfL --max-time 30 "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/${1}?rejestr=${2:-P}&format=json" \
  | jq '{
      nazwa:   .odpis.dane.dzial1.danePodmiotu.nazwa,
      forma:   .odpis.dane.dzial1.danePodmiotu.formaPrawna,
      nip:     .odpis.dane.dzial1.danePodmiotu.identyfikatory.nip,
      regon:   .odpis.dane.dzial1.danePodmiotu.identyfikatory.regon,
      siedziba:.odpis.dane.dzial1.siedzibaIAdres,
      reprezentacja: .odpis.dane.dzial2.reprezentacja,
      wspolnicy:     .odpis.dane.dzial1.wspolnicy}'
}
domena() {
  local d="${1#*://}"; d="${d%%/*}"
  case "$d" in
    *.pl) curl -sSfL --max-time 30 "https://rdap.dns.pl/domain/${d}" ;;
    *)    curl -sSfL --max-time 30 "https://rdap.org/domain/${d}" ;;
  esac | jq '{ldhName, status, events,
              rejestrator: [.entities[]? | select(.roles[]?=="registrar") | .vcardArray[1][]? | select(.[0]=="fn") | .[3]],
              abonent:     [.entities[]? | select(.roles[]?=="registrant") | .vcardArray[1][]? | select(.[0]=="fn" or .[0]=="adr")],
              nameservery: [.nameservers[]?.ldhName]}' \
  || echo "RDAP niedostępny dla $d (m.in. .eu nie ma publicznego RDAP po HTTP) — udokumentuj ręcznie."
}
strona() {
  echo "== łańcuch przekierowań =="
  curl -sSIL --max-time 30 -o /dev/null -w '%{url_effective} <- %{http_code}\n' "$1" || true
  echo
  echo "== nagłówki pierwszej odpowiedzi =="
  curl -sSI --max-time 30 "$1" | sed -n '1,20p'
}

case "${1:-}" in
  nip)    nip "$2" ;;
  krs)    krs "$2" "${3:-P}" ;;
  domena) domena "$2" ;;
  strona) strona "$2" ;;
  pelny)
    echo "### Biała lista VAT"; nip "$2" | tee /tmp/.kruczek_nip.json
    k=$(jq -r '.krs // empty' /tmp/.kruczek_nip.json)
    if [ -n "$k" ] && [ "$k" != "null" ]; then echo; echo "### KRS $k"; krs "$k" P; else echo; echo "(brak numeru KRS — prawdopodobnie JDG lub spółka cywilna; wspólników ustal z innych źródeł)"; fi
    rm -f /tmp/.kruczek_nip.json ;;
  *) sed -n '2,18p' "$0"; exit 1 ;;
esac
