# Changelog

Format wg [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
wersjonowanie wg [SemVer](https://semver.org/lang/pl/).

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
- agenci `recenzent` (opus) i `kontroler-zalacznikow` (haiku)
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
- 10 komend: `init-projekt`, `nowa-sprawa`, `dowod`, `chronologia`, `status`, `baza-wiedzy`,
  `pismo`, `weryfikuj`, `eskalacja`, `komendy`
- 7 skilli wiedzy: `konwencje-teczki`, `redagowanie-pism`, `zrodla-prawa`, `zrodla-orzecznictwa`,
  `zrodla-rejestry`, `analiza-eml`, `ocr-transkrypcja`
- 9 subagentów z dobranymi modelami: `forensyk-spamu`, `archiwista`, `kronikarz`,
  `ustalacz-podmiotu` (haiku), `transkryber`, `zrodlo-prawa`, `researcher-orzecznictwa` (sonnet),
  `redaktor-pism`, `weryfikator-cytatow` (opus)
- 8 skryptów: `init-projekt.sh`, `nowa-sprawa.sh`, `eml-forensics.py`, `manifest.py`, `eli.sh`,
  `orzecznictwo.sh`, `podmiot.sh`, `build-pismo.py`
- szablon pisma A4 z wdrukowywanymi załącznikami
