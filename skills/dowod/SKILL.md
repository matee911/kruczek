---
name: dowod
description: Wciąga dowód do archiwum sprawy — kopiuje oryginał, liczy sumę kontrolną, robi OCR/transkrypcję dla plików nietekstowych, aktualizuje manifest i zapisuje zdarzenie w teczce. Użyj przy każdym nowym mailu, skanie, zdjęciu, nagraniu, PDF-ie czy zrzucie ekranu w sprawie.
argument-hint: "[ścieżka do pliku] [katalog sprawy]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eml_forensics.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/metadane.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/linki_dowodu.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py *) Bash(cp *) Bash(mkdir *) Bash(sha256sum *) Bash(file *) Bash(ls *) Bash(qpdf *) Bash(unzip *) Bash(7z *) Read Write Edit AskUserQuestion
---

# Wciągnięcie dowodu do archiwum

Argumenty: `$ARGUMENTS`

To zadanie ma dwie warstwy: **mechaniczną** (kopia, hash, tekst) i **rozpoznawczą** (co to jest i co dalej).
Trzymaj się kolejności kroków.

## 0. Plik zaszyfrowany? Odszyfruj PRZED intake

Sprawdź typ pliku:
```bash
file <plik>
```

Jeśli PDF zaszyfrowany, .zip lub .7z:
- Zapytaj o hasło: „Plik jest zabezpieczony hasłem. Jakie hasło? (Przy plikach z urzędów/firm często PESEL lub data urodzenia.)"
- Odszyfruj:
  ```bash
  # PDF
  qpdf --password=<haslo> --decrypt <plik>.pdf <plik>_odszyfrowany.pdf
  # ZIP
  unzip -P <haslo> <plik>.zip -d <katalog>/
  # 7z
  7z x -p'<haslo>' <plik>.7z -o<katalog>/
  ```
- Do archiwum trafiają **oba**: oryginał jako `<nazwa>_ORYGINAŁ.<ext>` i odszyfrowany jako `<nazwa>.<ext>`
- **Hasło NIE trafia do `index.md` ani chronologii** — zapisz wyłącznie: „plik był zaszyfrowany, odszyfrowano RRRR-MM-DD"

## 1. Ustal plik i sprawę

Pytania do użytkownika zadawaj narzędziem AskUserQuestion — kilka naraz w jednym wywołaniu, gdy znasz je
z góry (najwyżej 4), zamiast pytać w treści odpowiedzi.

Jeśli nie podano ścieżki — zapytaj krótko. Jeśli nie podano sprawy — sprawdź `index.md`
w bieżącym katalogu albo zapytaj.

## 2. Wykryj duplikat

```bash
sha256sum <plik>
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py skan <sprawa>
```
Sprawdź, czy SHA-256 nowego pliku występuje w tabeli ze `skan`. Ten krok tylko czyta —
**nie uruchamiaj tu `sumy`**, bo to zapis do `SHA256SUMS.txt`, a plik jeszcze nie jest w archiwum.
Jeśli duplikat: „Ten plik już jest w archiwum jako [nazwa]. Dodać mimo to?"

## 3. Nazwij zgodnie z konwencją

`RRRR-MM-DD_<rodzaj>_<krotki-opis>.<ext>`

Data to data **powstania** dowodu (nadania, wysłania, wykonania), nie dzisiejsza.
Rodzaj: `email`, `list`, `umowa`, `faktura`, `zdjecie`, `skan`, `nagranie`, `zrzut`, `wydruk`, `zgloszenie`.

## 4. Skopiuj do ARCHIWUM — nigdy nie przenoś, nigdy nie edytuj

```bash
cp <źródło> <sprawa>/ARCHIWUM/<nazwa-wg-konwencji>
```

## 5. Routing po typie pliku — wywołaj właściwe podsystemy

### `.eml` / `.msg`
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/eml_forensics.py <plik> --outdir <sprawa>/ARCHIWUM
```
Zleć subagentowi `analizuj-eml` (haiku).

Jeśli wiadomość **sama jest oświadczeniem woli** (zawarcie, zmiana, wypowiedzenie, odstąpienie,
potwierdzenie umowy zawartej przez telefon) — zleć też `sprawdz-forme` (sonnet): e-mail to
najwyżej forma dokumentowa, a część czynności wymaga więcej.

Linki i domeny z wiadomości zabezpieczasz według kroku 6. Zapytania Gmail: zleć `/kruczek:gmail` z domenami
z adresów From, Reply-To i Return-Path.

### `.pdf` / `.docx` / `.xlsx`

Zapytaj jeśli źródło nieznane: „Od kogo pochodzi ten plik?"

Jeśli od **drugiej strony**:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/metadane.sh <plik>
```
(lub zleć skill `/kruczek:metadane`)

Jeśli nazwa lub treść zawiera „regulamin", „OWU", „wzorzec", „ogólne warunki" — **niezależnie od źródła**:
zleć subagentowi `sprawdz-klauzule` (sonnet).

Jeśli to **umowa, aneks, porozumienie, wypowiedzenie, odstąpienie, pełnomocnictwo, cesja,
poręczenie** albo inne oświadczenie woli — **niezależnie od tego, czy od drugiej strony, czy
od użytkownika** — zleć subagentowi `sprawdz-forme` (sonnet). Sprawdza, jakiej formy i podpisu
czynność wymagała, jaką zachowano (w tym `pdfsig` dla podpisów elektronicznych) i wskazuje
formę nieodpowiednią.

### Plik podpisu `.xml` / `.xades` / `.sig` obok dokumentu

Skopiuj **razem** z podpisanym dokumentem (bez niego podpis jest nieweryfikowalny) i zleć
`sprawdz-forme` dla pary.

### Zrzut strony (`.html` / `.mhtml` / obraz z URL w nazwie)

Wyciągnij URL z nazwy pliku lub pytaj.
- Jeśli URL już był w sprawie → `/kruczek:archiwa diff <url>`
- Jeśli URL nowy w sprawie → `/kruczek:archiwa <url>` (pełne rozpoznanie + CDX)

### Obraz / skan bez URL

Zleć subagentowi `transkrybuj` (sonnet). Jeśli skan przedstawia umowę lub oświadczenie woli —
po transkrypcji zleć `sprawdz-forme`: skan dowodzi istnienia podpisanego oryginału, ale sam
nim nie jest.

## 6. Linki i domeny z pliku — lista z rekomendacją, potem archiwizacja

Link w pliku od drugiej strony (mail, zwłaszcza spam i mailing, PDF, zrzut strony) bywa spersonalizowany:
niesie Twój adres wprost, w zakodowanym tokenie albo w krótkim identyfikatorze, albo jest linkiem wypisania.
Otwarcie go potwierdza nadawcy, że skrzynka działa, a snapshot w Wayback Machine publikuje adres. Czy link
zabezpieczyć, rozstrzyga kod:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/linki_dowodu.py <sprawa>/ARCHIWUM/<plik> --odbiorca <e-mail> [--odbiorca <drugi e-mail>] --nazwa "<imię i nazwisko>"
```

Plik: `.eml` i `.html` wprost. Inny dokument (PDF, skan, zrzut ekranu) ma linki dopiero w wersji tekstowej, więc
dla niego krok 6 wykonujesz po kroku 7, na pliku `_tekst.md`. `--odbiorca`: oba e-maile użytkownika
z `_SZABLONY/dane-nadawcy.md` (główny i w sprawach spornych), `--nazwa`: jego imię i nazwisko stamtąd;
odbiorców i ich nazwy z nagłówków `.eml` skrypt dokłada sam.
Wynik to JSON o stałym kształcie. Postępuj według pola `rekomendacja` — przy linkach i przy stronach głównych
z `domeny` — nie zmieniaj jej i nie otwieraj linku inaczej, niż ona mówi:

| `rekomendacja` | Co robisz |
|---|---|
| `ARCHIWIZUJ` | zabezpieczasz go z listy `do_archiwizacji` (niżej), nie osobno |
| `ZAPYTAJ` | wszystkie takie linki w jednym pytaniu AskUserQuestion (niżej); po zgodzie `/kruczek:archiwa <url>` — kopia lokalna i Save Page Now |
| `NIE_ARCHIWIZUJ` | nie otwierasz, nie archiwizujesz, nie podajesz do `save`; w raporcie wypisujesz z polem `powody` |

Lista `do_archiwizacji` to linki `ARCHIWIZUJ` i adresy stron bez Twojego identyfikatora (`czysty_url`: link
bez parametrów albo strona docelowa podana w parametrze przekierowania), bez powtórzeń. Każdy adres z tej listy
zabezpiecz `/kruczek:archiwa <url>` bez pytania — tak strona oferty trafia do Wayback, choć sam link z maila nie.
Strony główne z `domeny`, które już są na liście, pomijasz. Link przez tracker bez adresu docelowego ma
`czysty_url` równe `null`: strony oferty nie da się odsłonić bez użycia linku, więc decyduje pytanie niżej.

Pytanie o linki `ZAPYTAJ`: wypisz je z polem `powody` i powiedz wprost, że otwarcie linku może potwierdzić
nadawcy, że Twój adres działa, a Save Page Now publikuje link razem z jego identyfikatorem i stronę, którą ten
link pokazuje — spersonalizowana strona może zawierać Twoje dane. Przy powodzie `DANE_ODBIORCY` powiedz wprost:
link zawiera Twoje imię i nazwisko albo nazwę Twojej domeny, a Save Page Now je opublikuje. Opcje w tej
kolejności: „żaden (zalecane)”, „wskażę które”, „wszystkie”.

Strony główne z `domeny` zabezpieczasz tylko dla domen nowych w sprawie. Jeśli uważasz, że rekomendacja jest
zła — powiedz to użytkownikowi; link `NIE_ARCHIWIZUJ` otwierasz tylko na jego wyraźną prośbę i tylko kopią
lokalną.

**URL podany przez użytkownika albo ustalony poza plikiem** (np. strona firmy z rejestru) zabezpiecz od razu,
przed analizą. Linki wyciągnięte z pliku idą wyłącznie przez `linki_dowodu.py` i listę wyżej.
```bash
# 1. WŁASNA kopia — fundament, zawsze:
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh lokalnie "<url>" <sprawa>/ARCHIWUM
# 2. Niezależne poświadczenie IA — jeśli się uda:
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh save "<url>" --kontakt "<e-mail nadawcy>"
```
Wayback bywa niedostępny, zwraca błędy i może odmówić zapisu — nie może być jedynym miejscem, w którym istnieje
dowód. `lokalnie` nie wymaga `--kontakt` ani żadnej konfiguracji i zapisuje treść, nagłówki, kod HTTP, łańcuch
przekierowań i SHA-256. Nieudany `save` **nie jest** porażką zabezpieczenia dowodu — odnotuj go i idź dalej.

`--kontakt` (tylko dla `save`) to e-mail w sprawach spornych z `_SZABLONY/dane-nadawcy.md`.
Gdy dane nadawcy są puste — zrób sam zrzut lokalny, a `save` zapisz jako zadanie: `teczka.py zadanie <sprawa> "Wayback save: <url>"`.

## 7. Wersja tekstowa dla plików nietekstowych

| Typ | Co zrobić | Plik wynikowy |
|---|---|---|
| `.eml` / `.msg` | `eml_forensics.py` (krok 5) | `_naglowki.txt`, `_tresc.html`, `_analiza.md` |
| skan / zdjęcie / PDF bez tekstu | `transkrybuj` (sonnet) | `<nazwa>_tekst.md` |
| PDF z warstwą tekstową | `pdftotext -layout` | `<nazwa>_tekst.md` |
| nagranie audio / wideo | `transkrybuj` (sonnet) | `<nazwa>_tekst.md` |

Nagłówek wersji tekstowej (obowiązkowy):
```markdown
> **Odczyt pomocniczy.** Metoda: <OCR/vision/transkrypcja>. Data: RRRR-MM-DD.
> Plik źródłowy: `<nazwa>`, SHA-256: `<suma>`. Wiążąca jest treść oryginału.
> Fragmenty nieczytelne: `[nieczytelne]`, niepewne: `[?]`.
```

## 8. Sumy kontrolne i manifest

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sumy  <sprawa>
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py wstaw <sprawa>/index.md <sprawa>
```

`sumy` tylko dopisuje nowe pliki — istniejących wpisów w `SHA256SUMS.txt` nie zmienia.
Jeśli zgłosi `NIEZGODNA SUMA` albo `BRAK PLIKU` (exit 1), zatrzymaj się i powiedz o tym
użytkownikowi: dowód w archiwum zmienił się po zaewidencjonowaniu. Nie poprawiaj
`SHA256SUMS.txt` ręcznie.

Jeśli `sumy`, `wstaw` albo odświeżenie `index.md` przez `teczka.py` (krok 10) kończy się błędem lub ostrzeżeniem
(np. „uszkodzone znaczniki manifestu — popraw ręcznie”, „index.md nie odświeżony”), pokaż komunikat
użytkownikowi i nie edytuj `index.md` sam — w tym pliku są notatki użytkownika.

W tabeli opisowej nad manifestem (`index.md` sekcja 4) dopisz: nazwa pliku + jedno zdanie co to jest i co dowodzi.

## 9. Pytanie o brakujący dowód kontekstowy

Przy każdym typie pliku — zaproponuj co mogłoby uzupełnić dowód:

| Typ pliku | Sugestia |
|---|---|
| `.eml` | „Czy masz autoresponder potwierdzający odbiór tej wiadomości?" |
| faktura / potwierdzenie płatności | „Czy masz wyciąg bankowy potwierdzający obciążenie?" |
| regulamin / OWU | „Czy masz poprzednią wersję tego dokumentu do porównania?" |
| umowa / oświadczenie ze skanem podpisu | „Gdzie jest oryginał z podpisem własnoręcznym? Masz plik z podpisem elektronicznym zamiast PDF-a ze skanem?" |
| zrzut ekranu | „Czy zrobiłeś zrzut 'przed' i 'po' zmianie?" |
| nagranie | „Czy masz potwierdzenie mailowe lub SMS nawiązujące do tej rozmowy?" |

## 10. Zapisz zdarzenie w teczce

Data i godzina **zdarzenia** (nie dodania). Typ według kierunku (`konwencje-teczki`): pismo od drugiej
strony → `odpowiedz` (albo `wplyw` dla decyzji/wezwania — zapytaj, czy wyznacza Tobie termin);
potwierdzenie odbioru Twojego pisma → `doreczenie`; inne → `fakt`.

```
${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py zdarzenie <sprawa> --typ <typ> --data <data> [--godzina GG:MM] \
  [--watek <id>] [--dotyczy <id nadania>] --opis "<opis>" --dowod ARCHIWUM/<plik> [--termin 14d --podstawa "<podstawa>"]
```

`--termin` zawsze razem z `--podstawa` wziętą z pisma albo przepisu; nie wiesz — zapytaj użytkownika, nie zgaduj.
Gdy `teczka.py` odpowie, że czeka kilka pism — pokaż je użytkownikowi i powtórz polecenie z `--dotyczy <id nadania>`.

## 11. Raport końcowy

```
Plik:       <nazwa>
SHA-256:    <hash>
Wykryto:    <typ>
Wywołano:   <co uruchomiono — archiwa? metadane? forensyk? sprawdz-klauzule? sprawdz-forme?>
Linki:      <N>: ARCHIWIZUJ <a>, ZAPYTAJ <b> (zabezpieczone za zgodą: <c>), NIE_ARCHIWIZUJ <d>; adresy stron bez identyfikatora: <e>
Pewność:    dowód
⚠ Brakuje: <sugestia jeśli jest>
```
