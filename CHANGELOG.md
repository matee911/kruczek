# Changelog

Format wg [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
wersjonowanie wg [SemVer](https://semver.org/lang/pl/).

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
- `scripts/kontrola-pisma.py` — mechaniczna kontrola spójności gotowego PDF-u
- `templates/tldr.md` — dokument dla użytkownika: co wysyłasz, co możesz ugrać, gdzie jesteśmy słabi
- `templates/dane-nadawcy.md` — trwała pamięć danych korespondencyjnych, żeby nie pytać za każdym razem

### Zmienione
- **`templates/pismo.html` przepisany.** Marginesy 25/20/25/20 mm (spełniają Envelo min. 8/15 mm,
  PUH e-Doręczenia min. 10/8/15 mm, ISO 838 na wpięcie akt), font Liberation Serif 12 pt
  metrycznie zgodny z Times New Roman, interlinia 1,4
- **Numeracja generowana licznikami CSS** wg hierarchii z Zasad techniki prawodawczej:
  `I.` → `1.` (ciągłe przez całe pismo) → `1)` → `a)` → `–`. Koniec z mylącym „1." wewnątrz „1."
- `build-pismo.py` ustawia marginesy, sprawdza osadzenie fontów, rozmiar pliku i liczbę kartek
  pod wymogi print&mail
- `redagowanie-pism` rozbudowany o pełną konwencję: skład, hierarchia numeracji, układ nagłówka,
  oznaczenie stron wg art. 43⁴ k.c. i art. 126 k.p.c., załączniki, **dobór podpisu**
  (własnoręczny / zaufany / kwalifikowany / niepotrzebny) z podstawami prawnymi, kanały wysyłki
- `pismo` przebudowany: fact-checking **przed** pisaniem, pytanie o dane raz i zapis do
  `dane-nadawcy.md`, obowiązkowa kontrola i recenzja, generowanie TL;DR
- `manifest.py` pomija `index.md` i `SHA256SUMS.txt` (odwołanie cykliczne przy zapisie manifestu)

### Naprawione
- `manifest.py sprawdz` zgłaszał wszystkie pliki jako nowe (nieobcięty znak nowego wiersza)
- `build-pismo.py` błędnie raportował fonty jako nieosadzone (kolumna `type` bywa dwuwyrazowa)
- `eml-forensics.py` nie wykrywał tokenu Base64 bez nazwy parametru (`?bWF0ZWU…`)

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
- 8 skryptów: `init-projekt.sh`, `nowa-sprawa.sh`, `eml-forensics.py`, `manifest.py`, `eli.sh`,
  `orzecznictwo.sh`, `podmiot.sh`, `build-pismo.py`
- szablon pisma A4 z wdrukowywanymi załącznikami
