#!/usr/bin/env bash
# orzecznictwo.sh — przeszukiwanie otwartych baz orzeczeń i decyzji. Bez kluczy API.
#
#   orzecznictwo.sh saos "informacja handlowa" [strona]   — SAOS (sądy powszechne, SN, NSA, TK)
#   orzecznictwo.sh saos-tresc 123456                     — pełna treść orzeczenia z SAOS
#   orzecznictwo.sh saos-przepis 2024/1221                — orzeczenia powołujące dany Dz.U. (rok/pozycja)
#   orzecznictwo.sh uodo "marketing"                      — decyzje Prezesa UODO (pełnotekstowo)
#   orzecznictwo.sh uodo-tresc DKN.5131.34.2023           — treść decyzji UODO (HTML) + link do PDF
#   orzecznictwo.sh cbosa 6C317F6401                      — orzeczenie NSA/WSA po ID z CBOSA
#   orzecznictwo.sh sn "III SZP 7/15"                     — PDF orzeczenia SN po sygnaturze
#   orzecznictwo.sh uke 2025                              — Dziennik Urzędowy UKE, pozycje z rocznika
#
# UWAGA — czego NIE da się zrobić automatycznie (stan 08.2026):
#   * wyszukiwarka CBOSA (/cbo/find) ignoruje filtry — ID zdobądź przez wyszukiwarkę
#     internetową z operatorem  site:orzeczenia.nsa.gov.pl
#   * wyszukiwarka Portalu Orzeczeń SP i UOKiK to formularze POST — tylko przez site:
#   * baza SAOS bywa nieaktualna dla części sądów (dużo kończy się ok. 2018 r.) — zawsze
#     sprawdź datę i nie zakładaj kompletności
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

case "${1:-}" in
  saos)
    curl -sSfL --max-time 60 "https://www.saos.org.pl/api/search/judgments?all=$(urlencode "$2")&pageSize=20&pageNumber=${3:-0}" \
    | jq '{found: .info.totalResults, items: [.items[] | {id, courtType, judgmentType, judgmentDate,
            sygnatury: [.courtCases[].caseNumber], sad: (.division.court.name // .chamber.name // null)}]}'
    ;;
  saos-tresc)
    curl -sSfL --max-time 60 "https://www.saos.org.pl/api/judgments/$2" \
    | jq '{sygnatury:[.data.courtCases[].caseNumber], judgmentDate:.data.judgmentDate,
           przepisy:[.data.referencedRegulations[]?.journalTitle], tekst:.data.textContent}'
    ;;
  saos-przepis)
    curl -sSfL --max-time 60 "https://www.saos.org.pl/api/search/judgments?lawJournalEntryCode=$(urlencode "$2")&pageSize=20" \
    | jq '{found: .info.totalResults, items: [.items[] | {id, judgmentDate, sygnatury:[.courtCases[].caseNumber]}]}'
    ;;
  uodo)
    curl -sSfL --max-time 60 "https://orzeczenia.uodo.gov.pl/api/documents/search/PublicDocument/,/content_pl:glob:*$(urlencode "$2")*?order=-id&fields=refname,refid,date_publication,title_pl&count=25" \
    | jq '[.. | objects | select(has("refname")) | {sygnatura: .refname, refid, data: .date_publication, tytul: .title_pl}]'
    ;;
  uodo-tresc)
    sig=$(printf %s "$2" | tr 'A-Z.' 'a-z_')
    rok=$(printf %s "$2" | grep -oE '[0-9]{4}$' || true)
    base=${sig%_"$rok"}
    refid="urn:ndoc:gov:pl:uodo:${rok}:${base}"
    echo "refid: $refid"
    echo "PDF:   https://orzeczenia.uodo.gov.pl/api/documents/public/items/${refid}:0/body.pdf"
    # "|| true" na końcu: gdy head ucina strumień wcześniej niż curl/sed skończą pisać,
    # writer dostaje SIGPIPE i pod `set -o pipefail` cały skrypt by się ubił (exit 141) —
    # obcięcie na 200 linii jest tu celowe, nie błędem, więc nie ma co propagować.
    curl -sSfL --max-time 60 "https://orzeczenia.uodo.gov.pl/api/documents/public/items/${refid}:0/body.html" \
      | sed -e 's/<[^>]*>//g' -e '/^[[:space:]]*$/d' | head -200 || true
    ;;
  cbosa)
    # patrz uwaga o "|| true" wyżej (uodo-tresc) — ten sam wzorzec, ten sam powód.
    curl -sSfL --max-time 60 "https://orzeczenia.nsa.gov.pl/doc/$2" \
      | sed -e 's/<[^>]*>//g' -e '/^[[:space:]]*$/d' | head -400 || true
    ;;
  sn)
    f=$(printf %s "$2" | tr 'A-Z' 'a-z' | sed 's#/#-#g; s/ /%20/g')
    url="https://www.sn.pl/sites/orzecznictwo/orzeczenia3/${f}.pdf"
    echo "$url"
    curl -sSfL --max-time 60 -o "${2//[ \/]/_}.pdf" "$url" \
      && echo "Zapisano ${2//[ \/]/_}.pdf" \
      || echo "404 — nie każda sygnatura trafia w ten wzorzec; poszukaj przez site:sn.pl"
    ;;
  uke)
    curl -sSfL --max-time 60 "https://edziennik.uke.gov.pl/api/eli/acts/UKE/${2:-$(date +%Y)}" \
    | jq '[.items[]? | {pozycja: .pos, tytul: .title, data: .promulgation}]'
    ;;
  *) sed -n '2,26p' "$0"; exit 1 ;;
esac
