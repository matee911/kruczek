#!/usr/bin/env bash
# podmiot.sh — ustalanie tożsamości drugiej strony z otwartych rejestrów.
#
#   podmiot.sh nip 5252344078        — Biała lista VAT (MF): nazwa, REGON, KRS, adres, rachunki
#   podmiot.sh regon 140182840       — Biała lista VAT po REGON-ie (gdy NIP nieznany)
#   podmiot.sh krs 0000240611 [P|S]  — Odpis aktualny z KRS (P=przedsiębiorcy, S=stowarzyszenia)
#   podmiot.sh ceidg 5252344078      — CEIDG API v3: pełne dane JDG (imię, nazwisko, adres zam.)
#   podmiot.sh domena example.pl     — RDAP: rejestrator, abonent, daty, nameservery (.pl przez NASK)
#   podmiot.sh strona https://x.pl   — nagłówki HTTP + łańcuch przekierowań (dowód na rotację domen)
#   podmiot.sh pelny 5252344078      — nip -> (jeśli jest KRS) krs -> (jeśli JDG) ceidg, jednym ciągiem
#
# CEIDG API v3 wymaga tokenu Bearer. Uzyskaj go raz:
#   https://biznes.gov.pl/pl/e-uslugi/00_9999_00 → START → Profil Zaufany → wypełnij wniosek
#   Token przychodzi mailem w ciągu kilku minut. Zapisz w ~/.kruczek/ceidg_token lub ustaw
#   zmienną środowiskową CEIDG_TOKEN przed wywołaniem skryptu.
#
# Ograniczenia (stan 08.2026):
#   .eu nie ma publicznego RDAP/WHOIS po HTTP (EURid za anty-botem).
set -euo pipefail
today=$(date +%F)

_ceidg_token() {
  if [ -n "${CEIDG_TOKEN:-}" ]; then
    echo "$CEIDG_TOKEN"
  elif [ -f ~/.kruczek/ceidg_token ]; then
    cat ~/.kruczek/ceidg_token
  else
    echo ""
  fi
}

ceidg() {
  local n="${1//[^0-9]/}"
  local token; token=$(_ceidg_token)
  if [ -z "$token" ]; then
    echo "BRAK TOKENU CEIDG. Uzyskaj go na: https://biznes.gov.pl/pl/e-uslugi/00_9999_00"
    echo "Zapisz w ~/.kruczek/ceidg_token lub ustaw CEIDG_TOKEN=... przed wywołaniem."
    exit 1
  fi
  curl -sSfL --max-time 30 \
    -H "Authorization: Bearer $token" \
    "https://dane.biznes.gov.pl/api/ceidg/v3/raport?nip=${n}" \
  | jq '{imie, nazwisko, nip, regon, adresZamieszkania, adresDzialalnosci,
         dataPoczatkuDzialalnosci, dataZawieszenia, dataWznowienia, dataWykreslenia,
         statusDzialalnosci, pkd}'
}

nip() {
  local n="${1//[^0-9]/}"
  curl -sSfL --max-time 30 "https://wl-api.mf.gov.pl/api/search/nip/${n}?date=${today}" \
  | jq '.result.subject | {name, nip, regon, krs, statusVat, workingAddress, residenceAddress,
                           registrationLegalDate, representatives, accountNumbers}'
}
regon() {
  local r="${1//[^0-9]/}"
  curl -sSfL --max-time 30 "https://wl-api.mf.gov.pl/api/search/regon/${r}?date=${today}" \
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
  regon)  regon "$2" ;;
  krs)    krs "$2" "${3:-P}" ;;
  ceidg)  ceidg "$2" ;;
  domena) domena "$2" ;;
  strona) strona "$2" ;;
  pelny)
    nip_out=$(nip "$2")
    echo "### Biała lista VAT"
    printf '%s\n' "$nip_out"
    k=$(printf '%s\n' "$nip_out" | jq -r '.krs // empty')
    if [ -n "$k" ]; then
      echo
      echo "### KRS $k"
      krs "$k" P
    else
      echo
      echo "(brak numeru KRS — prawdopodobnie JDG)"
      token=$(_ceidg_token)
      if [ -n "$token" ]; then
        echo
        echo "### CEIDG (JDG)"
        ceidg "$2"
      else
        echo "(brak tokenu CEIDG — dla pełnych danych JDG uzyskaj token: https://biznes.gov.pl/pl/e-uslugi/00_9999_00)"
      fi
    fi ;;
  *) sed -n '2,22p' "$0"; exit 1 ;;
esac
