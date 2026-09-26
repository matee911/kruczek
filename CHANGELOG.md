# Changelog

Format wg [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
wersjonowanie wg [SemVer](https://semver.org/lang/pl/).

## [Unreleased]

## [0.7.0] — 2026-09-26

### Dodane
- **Subagent `sprawdz-forme`** — weryfikacja formy czynności prawnych w materiałach sprawy:
  jakiej formy i podpisu wymagała czynność (dokumentowa, pisemna, elektroniczna z podpisem
  kwalifikowanym, akt notarialny), jaką faktycznie zachowano i czy forma jest nieodpowiednia —
  ze skutkiem wg rygoru (nieważność, ograniczenia dowodowe z art. 74 k.c. z wyjątkami dla
  konsumenta i między przedsiębiorcami, skutek szczególny, nieskuteczność z art. 20 ust. 2 u.p.k.).
  Sprawdza oświadczenia obu stron, także użytkownika. Tabela wymogów ustawowych (k.c., u.p.k.,
  ustawa o kredycie konsumenckim, Pke, ustawa o ochronie praw lokatorów, k.p.) i skutków podpisu
  zaufanego, osobistego i kwalifikowanego sprawdzona w tekstach ujednoliconych ELI i na EUR-Lex
- Techniczna weryfikacja podpisów elektronicznych przez `pdfsig` (podpisujący, czas, integralność
  — „Not total document signed" = dopisano coś po podpisie) oraz odczyt XAdES. Status
  „kwalifikowany" nie jest zgadywany z nazwy wystawcy
- `/kruczek:dowod` wywołuje `sprawdz-forme` przy umowach, aneksach, wypowiedzeniach, odstąpieniach,
  pełnomocnictwach, e-mailach będących oświadczeniem woli i skanach umów; pliki podpisu
  (`.xml`/`.xades`/`.sig`) archiwizowane razem z dokumentem

### Zmienione
- `redagowanie-pism` §7 — wyjątek dla podpisu zaufanego wobec operatora telekomunikacyjnego
  (art. 20ae ust. 2a ustawy o informatyzacji): działa wyłącznie przy potwierdzeniu danych abonenta
  (art. 296 ust. 3 pkt 2 lit. e Pke) i za zgodą obu stron, nie jako podpis pod umową
- `redagowanie-pism` §7 — podpis osobisty wobec podmiotu niepublicznego równoważny własnoręcznemu,
  jeżeli obie strony wyrażą zgodę (art. 12d ust. 2 ustawy o dowodach osobistych)

## [0.6.0] — 2026-09-25

### Dodane
- **`eurlex.sh`** — pobieranie dokumentów z EUR-Lex po numerze CELEX: `html` i `pdf`, dowolna
  z 24 wersji językowych UE (domyślnie PL), zapis do pliku z SHA-256, URL-em i datą pobrania.
  Uczciwy User-Agent kruczka, odstęp 10 s między wywołaniami (`Crawl-delay` z robots.txt).
  Wyzwanie AWS WAF (`202`, `x-amzn-waf-action: challenge`) kończy się kodem 2 z instrukcją,
  nie próbą obejścia

### Zmienione
- Dokumentacja EUR-Lex (`zrodla-prawa`, `pobierz-przepis`, `fallback-przegladarka`): blokada
  anty-botowa jest czasowa i dotyczy każdego narzędzia, także WebFetch — nie tylko curla

## [0.5.1] — 2026-09-22

### Naprawione
- **`marketplace.json` nie deklarował wersji pluginu**, więc zainstalowana kopia zostawała na
  starym wydaniu mimo podbicia `version` w `plugin.json`. Pole `version` w `plugins[]` jest
  wspierane i używane przez inne marketplace'y — u nas nie było go od początku, przez co
  wydanie 0.5.0 nie dochodziło do zainstalowanego pluginu. Oba manifesty trzeba podbijać razem

## [0.5.0] — 2026-09-20

### Dodane
- **`eml_forensics` czyta treść jako materiał dowodowy, nie jako zrzut tekstu** — nowe podsekcje
  pod §22: dane kontaktowe podane w treści (telefon rozpoznawany po sygnale — prefiks `+48`,
  słowo-kotwica albo separatory — bo goły ciąg dziewięciu cyfr to równie dobrze numer BDO),
  kwoty, wartości procentowe i daty zbierane dosłownie, oraz zestawienia pól deklarujących
  to samo: `Subject` wobec `<title>`, wyrazy z `Subject` nieobecne w treści, obecność domeny
  z `From` w treści. Brak którejkolwiek klasy jest ustaleniem negatywnym — dla wezwania do
  zapłaty „treść nie zawiera kwoty" bywa najmocniejszym materiałem
- Podmioty nazwane w treści wyciągane po formie prawnej (`sp. z o.o.`, `S.A.`, `sp.j.`, `S.C.`),
  z ujawnioną w raporcie metodą wycinania
- **`review_eml_forensics.sh`** — przebieg recenzji raportów: przerywa się po wyczerpaniu limitu
  (kod wyjścia 2) zamiast przelatywać całą listę z identycznymi ostrzeżeniami, rozróżnia przyczynę
  (limit / sieć / pusta odpowiedź), a `--brakujace` wznawia przebieg pomijając pliki z aktualną
  oceną — porównanie po sumie kontrolnej raportu, więc wznowienie nie płaci drugi raz za to,
  co się już udało
- **Parser DOM tam, gdzie zmierzono brak utraty danych** — `find_hidden_elements`,
  `classify_comments` i `find_word_splitting_spans`; decyzja podejmowana per funkcja i poparta
  porównaniem wyników na całym korpusie. `extract_html_resources` świadomie zostaje na regexie:
  drzewo traktuje komentarz warunkowy jako nieprzezroczysty, więc atrybucja „piksel VML
  renderowany wyłącznie przez Outlooka" by zniknęła
- Testy 343 → 509, w tym `test_manifest.py` (pokrycie `manifest.py` 11% → 100%),
  `test_kontrola_pisma.py`, `test_build_pismo.py`, `test_dane_nadawcy_status.py`.
  Nowe testy pilnują **zakresu twierdzenia**, nie pojedynczego przypadku
- `skills/zrodla-rejestry` — **Portal Rejestrów Sądowych**: co daje ponad API (akta rejestrowe
  i sprawozdania finansowe), dlaczego nie da się go pobrać WebFetchem i jak to obejść przeglądarką

### Zmienione
- **`eml_forensics` rozbity na warstwy** (ports & adapters): `eml_forensics_logika.py` —
  ekstrakcja faktów bez I/O, `eml_forensics_raport.py` — renderowanie markdown bez I/O,
  `eml_forensics.py` — CLI i orchestracja
- Kod po angielsku, output po polsku — wcześniej jedno wyrażenie mieszało oba języki. Rename
  po tokenach, nie `sed`-em, więc docstringi i teksty raportu zostały nietknięte
- Objętość raportu −19% bez utraty dowodu: puste elementy układu zestawione zbiorczo
- Proza w docstringach skrócona — opis stanu sprzed poprawki należy do historii gita

### Naprawione
- **Raport nie był odtwarzalny.** Iteracja po zbiorze łańcuchów uzależniała kolejność wierszy
  od `PYTHONHASHSEED`, więc ten sam plik wejściowy dawał dokumenty o różnych sumach kontrolnych,
  a dwie osoby analizujące ten sam materiał dostawały różne wyniki. Dla materiału dowodowego
  to dyskwalifikujące
- Przebieg recenzji przerywał się komunikatem o wyczerpanym limicie przy 4% zużycia okna.
  Wzorzec zawierał gołe `429`, dopasowywane jako podciąg liczby `1429` **zacytowanej w recenzji**.
  Decyzja opiera się teraz na kształcie odpowiedzi, nie na słowach w jej treści — recenzja
  jest materiałem dowodowym i może zacytować dowolny komunikat błędu
- Znaczniki czasu bez `;` przed datą nie były parsowane (SendGrid, warstwy w Go), przez co
  skoki wypadały z osi czasu
- Nagłówek `X-Received` liczony jako skok przekazania — sekcja o osi czasu przeczyła sekcji
  o drodze wiadomości w tym samym dokumencie
- Encje rozwijane przed usuwaniem znaczników zjadały część `Message-ID` przed `@`
- Atrybuty `<a>` stojące za `href` były niewidoczne dla ekstraktora
- Brak nagłówków `Received` powodował wyjście z całej sekcji o drodze wiadomości, razem
  z inwentarzem adresów — ginął jedyny zapisany w pliku adres nadawcy
- `smoketest` — moduły bez CLI (`eml_forensics_logika.py`, `eml_forensics_raport.py`,
  `build_pismo_logic.py`, `test_*.py`) wykluczone z kontroli bitu `+x` w **obu** niezależnych
  warstwach; nadanie im `+x` byłoby nieprawdziwą deklaracją o ich roli
- Testy wołające CLI przez subprocess działały wyłącznie z katalogu repo, a jeden z nich
  **przechodził z błędnego powodu**: dostawał niezerowy kod wyjścia dlatego, że interpreter
  nie znalazł skryptu, a nie dlatego, że skrypt odrzucił nieistniejący plik
- Doctest `all_requirements_met` zależał od wersji Pythona (3.14 usuwa wcięcie docstringów
  przy kompilacji, 3.12 nie) — przechodził lokalnie, padał w CI
- 36 błędów `ruff` w `scripts/`

### Bezpieczeństwo dowodowe
- **Komentarz HTML nie jest treścią dokumentu.** Element z regułą ukrywającą zapisany wewnątrz
  komentarza był liczony jako ukryta treść — czyli jako dowód na coś, czego odbiorca nie dostał
- `@keyframes fade{from{opacity:0}}` trafiało do tabeli jako reguła ukrywająca; to klatka
  startowa animacji. Dodane wykluczenie reguł `@`, które nie niosą treści
- Warunki zagnieżdżonych reguł warunkowych **kumulują się** — raport podawał wyłącznie warunek
  wewnętrzny, więc regułę obowiązującą warunkowo przedstawiał jako obowiązującą szerzej
- Fałszywy pozytyw ciągłości łańcucha `Received`: kanoniczne `by` porównywane z deklaracją HELO
  dawało „przerwę", której plik nie pokazuje. Werdykt jest teraz trójwartościowy
  (`tak`/`nie`/`?`), rDNS ma pierwszeństwo przed HELO, a ustalenie negatywne obejmuje wyłącznie
  przejścia rozstrzygnięte
- Zakres porównania nagłówków tożsamościowych podawany zawsze — zdanie „bajty różnią się: N"
  czytało się jak twierdzenie o wszystkich nagłówkach, a dotyczyło pięciu
- Liczniki treści i indeks Jaccarda liczone razem z adnotacją, którą sam raport wstawia:
  w jednym pliku 134 znaki adnotacji dawały 16% licznika, a 12 „słów wyłącznie w `text/html`"
  pochodziło z tekstu raportu, nie z wiadomości
- DarkReader — usunięte zdanie „obecne w wysłanej treści": rozszerzenie wstrzykuje atrybuty
  w przeglądarce **odbiorcy**, więc była to hipoteza o pochodzeniu w raporcie deklarującym
  brak hipotez
- `<span>` bez zawartości między literami wyrazu zostaje wykryty jako rozbicie wyrazu —
  to klasyczna technika omijania filtrów, a poprawka fałszywego pozytywu chwilowo ją wyłączyła

## [0.4.0] — 2026-08-28

### Dodane
- `archiwa.sh lokalnie <url> <katalog>` — **własna kopia strony jako fundament dowodu**:
  treść, nagłówki, kod HTTP, URL końcowy po przekierowaniach, SHA-256 i metryczka
  `.zrzut.md` z datą odczytu. Nie wymaga `--kontakt` ani żadnej konfiguracji, bo dowód
  nie może zależeć od dostępności cudzej usługi. Wayback (`save`) jest teraz dodatkiem
  dającym niezależne poświadczenie strony trzeciej — nieudany snapshot nie unieważnia
  zabezpieczonego dowodu
- `templates/dane-nadawcy.md` — sekcja **„osoby, które reprezentuję"**: sprawy prowadzone
  w cudzym imieniu (nadawcą jest ta osoba, wymagane pełnomocnictwo jako załącznik)
- `scripts/dane_nadawcy_status.py` + `scripts/smoketest.sh` + `.github/workflows/smoketest.yml`
  — status pól krytycznych bez ujawniania wartości oraz mechaniczny smoketest skryptów
  (osobny job dla systemowego basha 3.2 na macOS)
- `lib.sh` — przenośna funkcja `sha256()` (`sha256sum` → `shasum` → `python3`)

### Zmienione
- **„Występuję jako" przeniesione z projektu do sprawy.** To cecha pojedynczej sprawy, nie
  pliku danych nadawcy: ta sama osoba prowadzi jedną sprawę prywatnie, drugą jako
  przedsiębiorca, trzecią w cudzym imieniu. `dane-nadawcy.md` trzyma teraz **tożsamości**
  (ja / moja działalność / osoby reprezentowane), a wybór trafia do nagłówka `index.md`
  sprawy. Pyta o niego `nowa-sprawa`, czyta `pismo`
- `archiwa.sh` — kontakt do User-Agenta podawany przez `--kontakt <e-mail>` z
  `_SZABLONY/dane-nadawcy.md` zamiast zmiennej środowiskowej `KRUCZEK_CONTACT`
  (zostaje jako fallback dla CI). Konfiguracja przez konwencję, nie przez grzebanie
  w środowisku użytkownika; wymagają go wyłącznie tryby uderzające w archive.org
- `skills/nowa-sprawa` — nie pyta już o cel sprawy na starcie (sprawa nie jest jeszcze
  poznana); to pytanie zostaje w `skills/pismo`, po zebraniu i analizie dowodów

### Naprawione
- **`podmiot.sh ceidg` nie działał w ogóle** — endpoint `/raport?nip=` zwraca 404 (w API v3
  raport jest pod `/raport/{id}`). Poprawiono na `/firma?nip=`; filtr `jq` przepisany wg
  oficjalnej specyfikacji OpenAPI, bo żadne z dotychczasowych pól nie istniało pod tą nazwą
  (odpowiedź to `{"firma":[…]}`, dane właściciela w zagnieżdżonym `wlasciciel`,
  `dataRozpoczecia` zamiast `dataPoczatkuDzialalnosci`). Dodano obsługę 204 (NIP spoza
  CEIDG — nie błąd) i 401/403 (token wygasł)
- **Przenośność macOS/BSD** — `sed 's/[^a-z0-9]\+/-/g'` w `nowa-sprawa.sh` nie tworzył sluga
  (katalogi spraw ze spacjami i kropkami), a `sed 's|https\?://||'` w `archiwa.sh` dawał
  `DOMAIN=https:`, przez co wszystkie snapshoty zapisywały się pod jedną nazwą. BSD sed nie
  zna `\+` ani `\?` w BRE — wszędzie `sed -E`. `eli.sh` używał nieobecnego na macOS
  `sha256sum`, `archiwa.sh` — `shasum`; oba przez wspólny helper
- `archiwa.sh save` — kończył się w ciszy: pod `set -e` niezerowy `curl` ubijał skrypt przed
  wypisaniem diagnostyki. Dodano jawny kod błędu, `--max-time 120` i komunikat dla timeoutu
- `archiwa.sh pobierz` — bez `-f` zapisywał stronę błędu 4xx/5xx lub plik pusty **i liczył mu
  SHA-256**, tworząc pozorny dowód. Teraz kasuje plik i kończy niezerowo
- `archiwa.sh historia`/`cdx-url` — pusta lub nie-JSON-owa odpowiedź CDX (limit zapytań)
  wywalała traceback Pythona zamiast komunikatu
- `smoketest.sh` — `SCRIPTS_DIR` z argumentu nie był normalizowany do ścieżki bezwzględnej,
  przez co wywołanie z CI (`smoketest.sh scripts`) wywracało trzy testy na `exit=127`
- `archiwa.sh` — dodano opisowy User-Agent we wszystkich wywołaniach Wayback Machine
  (SPN i CDX), zgodny z wymaganiami Internet Archive (`archive.org/developers/bots.html`);
  wersja w UA czytana z `plugin.json`, nazwa modelu przez opcjonalne `KRUCZEK_MODEL`
- `archiwa.sh` — wykrywanie zablokowanego egressu do `web.archive.org` (typowe w sesjach
  chmurowych) przed właściwym wywołaniem, zamiast czekania na timeout
- `skills/archiwa` — dopisano, że w sesji chmurowej trzeba przekazać komendę użytkownikowi
  do uruchomienia lokalnie (wzorzec z `skills/fallback-przegladarka`)

### Bezpieczeństwo dowodowe
- **Audyt zbyt mocnych stwierdzeń** — 16 miejsc opisywało poszlakę jako dowód albo przesądzało
  kwalifikację prawną. M.in.: data rejestracji domeny „dowodzi (…) czego nie da się wytłumaczyć
  przypadkiem" (sprzeczne z `dns.sh`), `dkim=pass`/`spf=pass` jako „to nie jest podszycie"
  (dotyczy domeny z `d=`, nie marki z `From`), brak NIP-u w serwisie jako „samodzielne naruszenie
  art. 5 u.ś.u.d.e.", rada, by napisać w piśmie, że milczenie adresata „będzie traktowane jako
  potwierdzenie odpowiedzialności" (takie domniemanie nie istnieje), tabela „gotowe zarzuty"
  w `skills/metadane`. Sekcję „Granica, której nie przekraczasz" dodano do `analiza-eml`,
  `analizuj-eml` i `metadane`, gdzie skupiała się większość przypadków
- Sprostowano dane obiecywane przez CEIDG API v3 w `README`, `ustal-strone` i `zrodla-rejestry`
  — API **nie zwraca** adresu zamieszkania ani daty urodzenia

## [0.3.5] — 2026-08-19

### Zmienione
- `skills/dane-nadawcy` — weryfikacja rejestrowa po wypełnieniu danych: JDG przez CEIDG
  (adres doręczeń, e-mail, status, pełna firma), spółka przez NIP+KRS (siedziba, reprezentacja,
  status); raport rozbieżności z pytaniem które dane użyć; pominięcie dla osób fizycznych

## [0.3.4] — 2026-08-19

### Zmienione
- `gen-claude-md.sh` — usuniięto dane osobowe z CLAUDE.md; skrypt nie wymaga już
  `dane-nadawcy.md` i jest bezpieczny do commitowania; CLAUDE.md wskazuje na plik
  `_SZABLONY/dane-nadawcy.md` zamiast kopiować jego zawartość
- `skills/dane-nadawcy` — skill nie wywołuje już `gen-claude-md.sh`; zarządza wyłącznie
  `_SZABLONY/dane-nadawcy.md`

## [0.3.3] — 2026-08-19

### Naprawione
- `agents/weryfikuj-cytaty`, `agents/recenzuj`, `agents/napisz-pismo` — pułapka chronologiczna:
  przepis musi obowiązywać w **dacie zdarzenia**, nie tylko dziś. Nowa sekcja w `weryfikuj-cytaty`
  z procedurą (`eli.sh referencje`, sprawdzenie daty uchylenia per zdarzenie); w `recenzuj` i
  `napisz-pismo` — wprost opisany błąd powołania uchylonego przepisu jako 🔴 BLOKUJE WYSYŁKĘ

## [0.3.2] — 2026-08-19

### Dodane
- `/kruczek:dane-nadawcy` (skill, sonnet) — wypełnia `_SZABLONY/dane-nadawcy.md` i generuje `CLAUDE.md`
  z danymi nadawcy i nawigacją; działa przy nowym projekcie i jako ręczna aktualizacja
- `scripts/gen-claude-md.sh` — generuje `CLAUDE.md` z `dane-nadawcy.md`; wywoływany przez
  `init-projekt.sh` i przez skill `dane-nadawcy`; bezpieczny do wielokrotnego wywołania (nadpisuje)
- `podmiot.sh regon` — wyszukiwanie na białej liście VAT po REGON-ie (gdy NIP nieznany)

### Zmienione
- `agents/ustal-strone`, `skills/zrodla-rejestry` — nowa sekcja „Gdy masz tylko nazwę firmy":
  kolejność prób (WebFetch stopki → rejestr.io → REGON → pytanie użytkownika z gotowymi linkami);
  wyraźny zakaz próbowania `/search/name` (endpoint nie istnieje w API MF)
- `skills/zrodla-prawa` — procedura weryfikacji aktualności przepisu przed analizą: `eli.sh obowiazuje`
  → tekst jednolity → nagłówek „Opracowano na podstawie" → `eli.sh referencje`; ostrzeżenie że tekst
  ogłoszony (pierwotny) jest niezdatny do cytowania nawet gdy plik jest już w bazie
- `skills/baza-wiedzy` — weryfikacja aktualności przy każdym dostępie do istniejącego pliku;
  szablon Publikatora wymaga t.j., nie tekstu ogłoszonego
- `skills/nowy-projekt` — krok 4 deleguje do `/kruczek:dane-nadawcy` zamiast AskUserQuestion

## [0.3.1] — 2026-08-19

### Naprawione
- `scripts/archiwa.sh save` — szukanie nagłówka `location:` zamiast `Content-Location:` (HTTP/2 Wayback Machine zwraca lowercase, skrypt nie znajdował timestamp i kończył błędem)

## [0.3.0] — 2026-08-19

### Dodane
- `/kruczek:archiwa` (skill, sonnet) + agent `archiwizuj-strone` — archiwizacja stron przez CDX API,
  Wayback Machine i curl z diff między wersjami; obsługa `.eu` bez RDAP
- `/kruczek:fakt` (skill, haiku) — dopisanie jednego faktu do chronologii w `index.md`
- `/kruczek:metadane` (skill, haiku) + `scripts/metadane.sh` — ekstrakcja metadanych plików
  (data, autor, GPS, rozbieżności dat); obsługa PDF, DOCX/XLSX/PPTX, JPEG/PNG, EML
- `/kruczek:gmail` (skill, sonnet) — wyszukiwanie i zestawianie wiadomości przez Gmail MCP
- `/kruczek:podsumowanie` (skill, opus) — synteza stanu sprawy z kwalifikacją ryzyk
- agent `sprawdz-klauzule` (sonnet) — analiza klauzul abuzywnych w umowach
- `scripts/podmiot.sh ceidg` — CEIDG API v3: imię, nazwisko, adres zamieszkania JDG; auto-token
  z `~/.kruczek/ceidg_token`; `pelny` automatycznie odpytuje CEIDG gdy brak KRS
- `skills/zrodla-rejestry`: dodane CRBR (beneficjenci rzeczywiści), Rejestr.io (powiązania
  kapitałowe), MSiG/imsig.pl (ogłoszenia), sprawozdania finansowe z repozytorium KRS —
  wszystkie z instrukcją obejścia przez `fallback-przegladarka`

### Zmienione
- **Przemianowanie agentów** na imperatywne polskie czasowniki: `recenzent` → `recenzuj`,
  `weryfikator-cytatow` → `weryfikuj-cytaty`, `forensyk-spamu` → `analizuj-eml`,
  `kontroler-zalacznikow` → `sprawdz-zalaczniki`, `kronikarz` → `dopisz-chronologie`,
  `transkryber` → `transkrybuj`, `archiwista` → `archiwizuj`,
  `researcher-orzecznictwa` → `szukaj-orzeczen`, `redaktor-pism` → `napisz-pismo`,
  `zrodlo-prawa` → `pobierz-przepis`, `archiwista-sieci` → `archiwizuj-strone`
- `ustalacz-podmiotu` → `ustal-strone` (termin procesowy)
- `init-projekt` → `nowy-projekt` (spójna polska nazwa)
- `wykrywacz-flag` → `sprawdz-klauzule` (opisuje działanie)
- Globalne zastąpienie `przeciwnik` → `druga strona` we wszystkich plikach (termin procesowy)
- `agents/recenzuj`: dodana sekcja "Podstawy prawne" (przeniesiona z `skills/recenzja`)
- `skills/recenzja`: uprzątnięte — teraz czysty orkiestrator: deleguje do `weryfikuj-cytaty`
  i `recenzuj` równolegle, syntetyzuje wyniki; usunięto duplikację sekcji 1–6
- `scripts/metadane.sh`: `grep -oP` → `ggrep -oP` z fallbackiem (BSD grep na macOS nie ma PCRE)
- `scripts/check-deps.sh`: `weasyprint` przed `wkhtmltopdf`; dodane `ggrep` (macOS), `exiftool`,
  `unzip`; `ggrep` sprawdzany tylko na macOS
- `docs/MODELE.md`: dodane wszystkie nowe komponenty do tabeli
- `README.md`: zaktualizowane zależności, szybki start i tabela źródeł

### Naprawione
- `agents/`: pole `tools` używało granularnych wzorców `Bash(cmd *)` — poprawione na prostą listę
  (`Bash, Read, Write`); granularne wzorce obsługuje tylko `allowed-tools` w skillach
- `skills/archiwa`: usunięte `disable-model-invocation: true` (blokował delegację do subagenta)
- `skills/kontrola`, `skills/komendy`: usunięte redundantne `disable-model-invocation: false`

## [0.2.0] — 2026-08-18

### Dodane
- `/kruczek:kontrola` (haiku) — mechaniczna kontrola pisma: niewypełnione pola, ciągłość numeracji
  załączników, zgodność odesłań i tytułów, sumy kontrolne, wymogi Envelo i e-Doręczeń
- `/kruczek:recenzja` (opus) — recenzja przed wysyłką: fakty kontra dowody, ryzyko dla nadawcy,
  język, siła oddziaływania
- skill `zrodla-dns-poczta` (haiku) + `scripts/dns.sh` — rekordy DNS przez DNS-over-HTTPS,
  SPF/DKIM/DMARC, porównanie infrastruktury wielu domen
- skill `fallback-przegladarka` — drabinka obejść dla źródeł zablokowanych dla automatu:
  zmiana narzędzia, boczne API, Claude in Chrome, Playwright, computer use, przekazanie użytkownikowi
- agenci `recenzuj` (opus) i `sprawdz-zalaczniki` (haiku)
- `scripts/kontrola_pisma.py` — mechaniczna kontrola spójności gotowego PDF-u
- `templates/tldr.md` — dokument dla użytkownika: co wysyłasz, co możesz ugrać, gdzie jesteśmy słabi
- `templates/dane-nadawcy.md` — trwała pamięć danych korespondencyjnych, żeby nie pytać za każdym razem

### Zmienione
- **`templates/pismo.html` przepisany.** Marginesy 25/20/25/20 mm (spełniają Envelo min. 8/15 mm,
  PUH e-Doręczenia min. 10/8/15 mm, ISO 838 na wpięcie akt), font Liberation Serif 12 pt
  metrycznie zgodny z Times New Roman, interlinia 1,4
- **Numeracja generowana licznikami CSS** wg hierarchii z Zasad techniki prawodawczej:
  `I.` → `1.` (ciągłe przez całe pismo) → `1)` → `a)` → `–`. Koniec z mylącym „1." wewnątrz „1."
- `build_pismo.py` ustawia marginesy, sprawdza osadzenie fontów, rozmiar pliku i liczbę kartek
  pod wymogi print&mail
- `redagowanie-pism` rozbudowany o pełną konwencję: skład, hierarchia numeracji, układ nagłówka,
  oznaczenie stron wg art. 43⁴ k.c. i art. 126 k.p.c., załączniki, **dobór podpisu**
  (własnoręczny / zaufany / kwalifikowany / niepotrzebny) z podstawami prawnymi, kanały wysyłki
- `pismo` przebudowany: fact-checking **przed** pisaniem, pytanie o dane raz i zapis do
  `dane-nadawcy.md`, obowiązkowa kontrola i recenzja, generowanie TL;DR
- `manifest.py` pomija `index.md` i `SHA256SUMS.txt` (odwołanie cykliczne przy zapisie manifestu)

### Naprawione
- `manifest.py sprawdz` zgłaszał wszystkie pliki jako nowe (nieobcięty znak nowego wiersza)
- `build_pismo.py` błędnie raportował fonty jako nieosadzone (kolumna `type` bywa dwuwyrazowa)
- `eml_forensics.py` nie wykrywał tokenu Base64 bez nazwy parametru (`?bWF0ZWU…`)

## [0.1.0] — 2026-08-18

Pierwsze wydanie.

### Dodane
- 10 komend: `nowy-projekt`, `nowa-sprawa`, `dowod`, `chronologia`, `status`, `baza-wiedzy`,
  `pismo`, `weryfikuj`, `eskalacja`, `komendy`
- 7 skilli wiedzy: `konwencje-teczki`, `redagowanie-pism`, `zrodla-prawa`, `zrodla-orzecznictwa`,
  `zrodla-rejestry`, `analiza-eml`, `ocr-transkrypcja`
- 9 subagentów z dobranymi modelami: `analizuj-eml`, `archiwizuj`, `dopisz-chronologie`,
  `ustal-strone` (haiku), `transkrybuj`, `pobierz-przepis`, `szukaj-orzeczen` (sonnet),
  `napisz-pismo`, `weryfikuj-cytaty` (opus)
- 8 skryptów: `init-projekt.sh`, `nowa-sprawa.sh`, `eml_forensics.py`, `manifest.py`, `eli.sh`,
  `orzecznictwo.sh`, `podmiot.sh`, `build_pismo.py`
- szablon pisma A4 z wdrukowywanymi załącznikami
