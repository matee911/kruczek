---
name: komendy
description: Spis wszystkich komend, skilli, subagentów i skryptów pluginu kruczek wraz z przypisanymi modelami. Użyj, gdy ktoś pyta "co potrafi kruczek", "jakie są komendy", "lista skilli" albo szuka właściwego narzędzia do zadania.
disable-model-invocation: false
model: haiku
effort: low
---

# kruczek — spis treści

Prowadzenie spraw spornych z firmami i instytucjami: teczka sprawy, archiwum dowodów z sumami
kontrolnymi, pisma z dosłownymi cytatami ze źródeł urzędowych, baza wiedzy wielokrotnego użytku.

Wypisz użytkownikowi poniższe tabele. Nie dodawaj nic od siebie poza jednym zdaniem podsumowania,
a jeśli z rozmowy wynika konkretna potrzeba — wskaż jedną, właściwą pozycję.

## Komendy (wywołujesz sam)

| Komenda | Co robi | Model |
|---|---|---|
| `/kruczek:komendy` | ten spis | haiku |
| `/kruczek:init-projekt` | zakłada repozytorium spraw: BAZA_WIEDZY, KONWENCJE.md, rejestr | sonnet |
| `/kruczek:nowa-sprawa` | zakłada teczkę sprawy z chronologią, manifestem i TODO | sonnet |
| `/kruczek:dowod` | wciąga dowód do archiwum: suma kontrolna, OCR/transkrypcja, wpis w chronologii | haiku |
| `/kruczek:chronologia` | dopisuje zdarzenie do chronologii sprawy | haiku |
| `/kruczek:status` | przegląd spraw: terminy, zaległości, następne kroki | haiku |
| `/kruczek:baza-wiedzy` | dopisuje zweryfikowany przepis lub orzeczenie do bazy wiedzy | sonnet |
| `/kruczek:pismo` | buduje pismo: argumentacja, cytaty, PDF z załącznikami, dowody.zip | opus |
| `/kruczek:kontrola` | mechaniczna kontrola pisma: numeracja, nazwy załączników, sumy, wymogi druku | haiku |
| `/kruczek:weryfikuj` | cross-check przepisów i sygnatur w źródłach urzędowych | opus |
| `/kruczek:recenzja` | recenzja przed wysyłką: fakty, ryzyko, język, siła oddziaływania | opus |
| `/kruczek:eskalacja` | plan kolejnych kroków po bezskutecznym terminie | opus |

## Skille wiedzy (Claude ładuje sam, gdy pasują)

| Skill | Kiedy się włącza | Model |
|---|---|---|
| `konwencje-teczki` | przy każdej pracy na plikach sprawy — zasady archiwum, nazewnictwa, chronologii | dziedziczy |
| `redagowanie-pism` | gdy powstaje pismo — struktura, ton, cytowanie, częste błędy | dziedziczy |
| `zrodla-prawa` | gdy potrzebny tekst przepisu — API ELI Sejmu, EUR-Lex | dziedziczy |
| `zrodla-orzecznictwa` | gdy potrzebne orzeczenie lub decyzja organu | dziedziczy |
| `zrodla-rejestry` | gdy trzeba ustalić dane przeciwnika lub domeny | dziedziczy |
| `analiza-eml` | gdy w sprawie pojawia się plik `.eml` lub pytanie o spam | haiku |
| `zrodla-dns-poczta` | gdy trzeba sprawdzić DNS, SPF/DKIM/DMARC albo dane domeny | haiku |
| `fallback-przegladarka` | gdy źródło jest zablokowane dla automatu — obejścia przez przeglądarkę | dziedziczy |
| `ocr-transkrypcja` | gdy dowód jest skanem, zdjęciem, PDF-em z obrazem lub nagraniem | sonnet |

## Subagenci

| Agent | Rola | Model | Dlaczego taki model |
|---|---|---|---|
| `forensyk-spamu` | wykrywa techniki obchodzenia filtrów w `.eml` | haiku | robotę robi skrypt, agent tylko czyta wynik i opisuje |
| `archiwista` | sumy kontrolne, manifest, porządek w archiwum | haiku | czysto mechaniczne, deterministyczne |
| `kronikarz` | dopisuje zdarzenia do chronologii | haiku | jedna tabela, ustalony format |
| `ustalacz-podmiotu` | NIP, KRS, RDAP, DNS, przekierowania domen | haiku | uruchamia skrypty i przepisuje pola JSON |
| `kontroler-zalacznikow` | spójność numeracji, nazw i sum kontrolnych w gotowym piśmie | haiku | porównywanie łańcuchów, zero uznaniowości |
| `transkryber` | OCR i transkrypcja do `.md` | sonnet | odczyt obrazu i polskiej fleksji, haiku gubi znaki diakrytyczne |
| `zrodlo-prawa` | pobiera i cytuje przepisy ze źródeł urzędowych | sonnet | nawigacja po API i długich PDF-ach |
| `researcher-orzecznictwa` | szuka orzeczeń i decyzji organów | sonnet | wiele źródeł, część zablokowana, trzeba kombinować |
| `redaktor-pism` | pisze argumentację prawną | opus | subsumpcja i konstrukcja wywodu |
| `weryfikator-cytatow` | adwersaryjny cross-check przepisów i sygnatur | opus | najdroższy błąd w całym procesie |
| `recenzent` | fakty kontra dowody, ryzyko dla nadawcy, język, siła pisma | opus | ostatnia bramka przed nadaniem |

## Skrypty (`${CLAUDE_PLUGIN_ROOT}/scripts/`)

| Skrypt | Do czego |
|---|---|
| `init-projekt.sh` | struktura repozytorium |
| `nowa-sprawa.sh` | katalog sprawy + `index.md` |
| `eml-forensics.py` | pełna analiza `.eml` → raport markdown |
| `manifest.py` | sumy kontrolne, manifest, weryfikacja spójności |
| `eli.sh` | API ELI Sejmu: teksty ujednolicone, status aktu, nowelizacje |
| `orzecznictwo.sh` | SAOS, UODO, CBOSA, SN, Dziennik Urzędowy UKE |
| `podmiot.sh` | biała lista VAT, KRS, RDAP, przekierowania |
| `dns.sh` | rekordy DNS, SPF/DKIM/DMARC, porównanie infrastruktury domen |
| `build-pismo.py` | HTML → PDF z wdrukowanymi załącznikami, marginesy pod Envelo i e-Doręczenia |
| `kontrola-pisma.py` | mechaniczna kontrola spójności gotowego pisma |

Wszystkie skrypty wypisują pomoc po uruchomieniu bez argumentów.
