---
name: zrodla-orzecznictwa
description: Gdzie i jak szukać polskich orzeczeń sądowych oraz decyzji organów (UODO, UKE, UOKiK) — które bazy mają API, które są zablokowane i jak je obejść. Użyj, gdy potrzebujesz sygnatury, tezy orzeczenia albo decyzji organu do pisma.
when_to_use: Szukanie wyroku, sygnatury, tezy, orzecznictwa do pisma, decyzji Prezesa UODO, kar UKE, decyzji UOKiK, linii orzeczniczej.
---

# Źródła orzecznictwa i decyzji organów

Wrapper: `${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh`

## Co działa, a co nie

| Źródło | Zakres | Dostęp |
|---|---|---|
| **SAOS** `saos.org.pl/api` | sądy powszechne, SN, NSA, TK | pełne REST API, bez klucza — **zacznij tutaj** |
| **UODO** `orzeczenia.uodo.gov.pl/api` | decyzje Prezesa UODO (581 szt.) | pełne REST API, wyszukiwanie pełnotekstowe |
| **CBOSA** `orzeczenia.nsa.gov.pl` | NSA i WSA | dokument po ID działa, **wyszukiwarka nie** |
| **SN** `sn.pl` | Sąd Najwyższy | PDF po sygnaturze, wyszukiwarka wymaga JS |
| **Portal Orzeczeń SP** `orzeczenia.ms.gov.pl` | sądy powszechne | dokumenty po GET, wyszukiwarka to POST |
| **UOKiK** `decyzje.uokik.gov.pl` | decyzje Prezesa UOKiK | drzewo i PDF-y po GET, wyszukiwarka martwa |
| **UKE** `edziennik.uke.gov.pl/api` | Dziennik Urzędowy UKE | API + PDF |

```bash
orzecznictwo.sh saos "informacja handlowa"      # start dla orzeczeń sądowych
orzecznictwo.sh saos-przepis 2024/1221          # kto powołuje ten Dz.U.
orzecznictwo.sh saos-tresc <id>                 # pełna treść
orzecznictwo.sh uodo "marketing"                # decyzje UODO pełnotekstowo
orzecznictwo.sh uodo-tresc DKN.5131.34.2023     # treść konkretnej decyzji
orzecznictwo.sh cbosa 6C317F6401                # orzeczenie NSA/WSA po ID
orzecznictwo.sh sn "III SZP 7/15"               # PDF z SN
orzecznictwo.sh uke 2025                        # Dziennik Urzędowy UKE
```

## Obejścia zablokowanych wyszukiwarek

**CBOSA, Portal Orzeczeń SP, UOKiK** mają wyszukiwarki, których nie da się odpytać programowo
(filtry ignorowane albo formularz POST z tokenem). Ścieżka: wyszukiwarka internetowa z operatorem
`site:`, wyciągnięcie identyfikatora z URL-a, potem pobranie dokumentu bezpośrednio.

```
site:orzeczenia.nsa.gov.pl "niezamówiona informacja handlowa"
site:orzeczenia.ms.gov.pl "nadużywanie technicznych środków"
site:decyzje.uokik.gov.pl marketing bez zgody
```

ID z CBOSA to 10 znaków hex w `/doc/<ID>`.

**UOKiK — pułapka:** linki z drzewa mają postać `/bp/dec_prez.nsf/{UNID_kategorii}/{UNID}?OpenDocument`
i zwracają 404. Podmień UNID kategorii na `0`: `/bp/dec_prez.nsf/0/{UNID}?OpenDocument`.

**SN — wzorzec URL:** sygnatura na małe litery, spacja → `%20`, `/` → `-`.
`III CZP 30/25` → `https://www.sn.pl/sites/orzecznictwo/orzeczenia3/iii%20czp%2030-25.pdf`
Nie każda sygnatura trafia (część plików ma sufiksy) — wtedy `site:sn.pl`.

**UODO — konstrukcja refid:** `urn:ndoc:gov:pl:uodo:<rok>:<sygnatura małymi literami, kropki → _>`.
`DKN.5131.34.2023` → `urn:ndoc:gov:pl:uodo:2023:dkn_5131_34`.
Prefiksy sygnatur w bazie: DKE, ZSOŚS, DKN, ZKE, ZSPU, ZSZZS, DOKE, ZSPR, DS, ZWAD, DWKSN, ZWOS.

## Gdy nic nie działa

Zanim uznasz źródło za niedostępne, przejdź drabinkę obejść ze skillu **`fallback-przegladarka`**: zmiana narzędzia (WebFetch ↔ curl), boczne API, Claude in Chrome z sesją użytkownika, Playwright dla stron renderowanych JS-em, a na końcu przekazanie zadania użytkownikowi z gotową instrukcją krok po kroku. Nie omijamy captcha ani logowania.

## Ograniczenia, o których trzeba pamiętać

- **SAOS bywa nieaktualny** — dla części sądów baza kończy się ok. 2018 r. Nie zakładaj kompletności
  i zawsze sprawdzaj datę orzeczenia.
- **Decyzje UKE nie mają publikowanych sygnatur** w komunikatach prasowych — pełne teksty są
  w Dzienniku Urzędowym UKE.
- Orzeczenie może dotyczyć **uchylonego** stanu prawnego. Sprawdź, czy przepis, na tle którego
  zapadło, nadal obowiązuje (`eli.sh obowiazuje`), i czy teza pozostaje aktualna.

## Reguła cytowania

Do pisma trafia wyłącznie orzeczenie, które **potwierdziłeś w źródle**: sąd, data, sygnatura,
dosłowny cytat tezy. Sygnatura wymyślona lub przekręcona jest gorsza niż jej brak — przeciwnik
sprawdzi ją w minutę i podważy całe pismo.

Czego nie potwierdziłeś, oznacz `⚠ NIEPOTWIERDZONE` w bazie wiedzy i **nie cytuj**.

## Delegowanie

Research po wielu źródłach zleć subagentowi `researcher-orzecznictwa` (sonnet) — ma opisane
wszystkie obejścia i zwraca gotowe pozycje z sygnaturami i URL-ami.
