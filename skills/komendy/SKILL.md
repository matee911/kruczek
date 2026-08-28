---
name: komendy
description: Spis wszystkich komend, skilli, subagentów i skryptów pluginu kruczek wraz z przypisanymi modelami. Użyj, gdy ktoś pyta "co potrafi kruczek", "jakie są komendy", "lista skilli" albo szuka właściwego narzędzia do zadania.
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
| `/kruczek:nowy-projekt` | zakłada repozytorium spraw: BAZA_WIEDZY, KONWENCJE.md, rejestr | sonnet |
| `/kruczek:dane-nadawcy` | wypełnia/aktualizuje _SZABLONY/dane-nadawcy.md | sonnet |
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
| `/kruczek:fakt` | rejestruje fakt słowny (kontekstowy lub zdarzeniowy) z oznaczeniem pewności | haiku |
| `/kruczek:archiwa` | archiwizuje URL w Wayback, historia CDX, diff snapshotów | sonnet |
| `/kruczek:metadane` | tabela metadanych plików od drugiej strony, flagi rozbieżności dat | haiku |
| `/kruczek:gmail` | generator zapytań Gmail, filtry sprawy, zestaw dowodu negatywnego | sonnet |
| `/kruczek:podsumowanie` | stan sprawy w prostym języku: co wiadomo, czego brakuje (z sugestiami), ocena pozycji, następny krok | opus |

## Skille wiedzy (Claude ładuje sam, gdy pasują)

| Skill | Kiedy się włącza | Model |
|---|---|---|
| `konwencje-teczki` | przy każdej pracy na plikach sprawy — zasady archiwum, nazewnictwa, chronologii | dziedziczy |
| `redagowanie-pism` | gdy powstaje pismo — struktura, ton, cytowanie, częste błędy | dziedziczy |
| `zrodla-prawa` | gdy potrzebny tekst przepisu — API ELI Sejmu, EUR-Lex | dziedziczy |
| `zrodla-orzecznictwa` | gdy potrzebne orzeczenie lub decyzja organu | dziedziczy |
| `zrodla-rejestry` | gdy trzeba ustalić dane drugiej strony lub domeny | dziedziczy |
| `analiza-eml` | gdy w sprawie pojawia się plik `.eml` lub pytanie o spam | haiku |
| `zrodla-dns-poczta` | gdy trzeba sprawdzić DNS, SPF/DKIM/DMARC albo dane domeny | haiku |
| `fallback-przegladarka` | gdy źródło jest zablokowane dla automatu — obejścia przez przeglądarkę | dziedziczy |
| `ocr-transkrypcja` | gdy dowód jest skanem, zdjęciem, PDF-em z obrazem lub nagraniem | sonnet |

## Subagenci

| Agent | Rola | Model | Dlaczego taki model |
|---|---|---|---|
| `analizuj-eml` | wykrywa techniki obchodzenia filtrów w `.eml` | haiku | robotę robi skrypt, agent tylko czyta wynik i opisuje |
| `archiwizuj` | sumy kontrolne, manifest, porządek w archiwum | haiku | czysto mechaniczne, deterministyczne |
| `dopisz-chronologie` | dopisuje zdarzenia do chronologii | haiku | jedna tabela, ustalony format |
| `ustal-strone` | NIP, KRS, RDAP, DNS, przekierowania domen | haiku | uruchamia skrypty i przepisuje pola JSON |
| `sprawdz-zalaczniki` | spójność numeracji, nazw i sum kontrolnych w gotowym piśmie | haiku | porównywanie łańcuchów, zero uznaniowości |
| `transkrybuj` | OCR i transkrypcja do `.md` | sonnet | odczyt obrazu i polskiej fleksji, haiku gubi znaki diakrytyczne |
| `pobierz-przepis` | pobiera i cytuje przepisy ze źródeł urzędowych | sonnet | nawigacja po API i długich PDF-ach |
| `szukaj-orzeczen` | szuka orzeczeń i decyzji organów | sonnet | wiele źródeł, część zablokowana, trzeba kombinować |
| `napisz-pismo` | pisze argumentację prawną | opus | subsumpcja i konstrukcja wywodu |
| `weryfikuj-cytaty` | adwersaryjny cross-check przepisów i sygnatur | opus | najdroższy błąd w całym procesie |
| `recenzuj` | fakty kontra dowody, ryzyko dla nadawcy, język, siła pisma | opus | ostatnia bramka przed nadaniem |
| `archiwizuj-strone` | CDX API, Save Page Now, diff digestów, interpretacja zmian stron | sonnet | nawigacja po API + Python parsing |
| `sprawdz-klauzule` | checklista red flags w regulaminach i OWU | sonnet | przeszukiwanie wzorców, zero uznaniowości |

## Skrypty (`${CLAUDE_PLUGIN_ROOT}/scripts/`)

| Skrypt | Do czego |
|---|---|
| `init-projekt.sh` | struktura repozytorium |
| `gen-claude-md.sh` | generuje CLAUDE.md z danych nadawcy (wołany też przez init-projekt.sh) |
| `nowa-sprawa.sh` | katalog sprawy + `index.md` |
| `eml-forensics.py` | pełna analiza `.eml` → raport markdown |
| `manifest.py` | sumy kontrolne, manifest, weryfikacja spójności |
| `eli.sh` | API ELI Sejmu: teksty ujednolicone, status aktu, nowelizacje |
| `orzecznictwo.sh` | SAOS, UODO, CBOSA, SN, Dziennik Urzędowy UKE |
| `podmiot.sh` | biała lista VAT, KRS, RDAP, przekierowania |
| `dns.sh` | rekordy DNS, SPF/DKIM/DMARC, porównanie infrastruktury domen |
| `build-pismo.py` | HTML → PDF z wdrukowanymi załącznikami, marginesy pod Envelo i e-Doręczenia |
| `kontrola-pisma.py` | mechaniczna kontrola spójności gotowego pisma |
| `archiwa.sh` | Wayback Machine CDX, Save Page Now, diff snapshotów |
| `metadane.sh` | zbiorcza tabela metadanych PDF/DOCX/XLSX/obrazów z flagami rozbieżności |

Wszystkie skrypty wypisują pomoc po uruchomieniu bez argumentów.
