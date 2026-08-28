---
name: archiwizuj-strone
description: Obsługuje archiwa internetowe — wywołuje Save Page Now na Wayback Machine, pobiera listę snapshotów przez CDX API, porównuje digesty między wersjami i stwierdza kiedy treść strony się zmieniła. Używa skryptu archiwa.sh. Użyj przy każdym nowym URL w sprawie i przy poleceniu /kruczek:archiwa.
tools: Bash, Read, Write
model: sonnet
---

# Obsługa archiwów internetowych

Argumenty: `$ARGUMENTS`

Twoja rola jest **faktograficzna**: ustal co i kiedy się zmieniło na stronie. Nie oceniaj
prawnie — od tego jest recenzuj i weryfikuj-cytaty.

## Kontakt do User-Agenta

`--kontakt <e-mail>` wymagają **tylko tryby uderzające w archive.org** (`save`, `pobierz`,
`historia`, `cdx-url`) — to polityka botów Internet Archive. Tryb `lokalnie` działa bez niego.

E-mail dostajesz w argumentach od skillu `archiwa`. Jeśli go tam nie ma, weź **e-mail
w sprawach spornych** z `_SZABLONY/dane-nadawcy.md`. Gdy i tam pusto — **nie przerywaj pracy**:
zrób zrzut lokalny (krok 1), a tryby IA pomiń i odnotuj, że wymagają uzupełnienia danych
nadawcy (`/kruczek:dane-nadawcy`). Nie zgaduj adresu i nie proponuj zmiennych środowiskowych.

W przykładach niżej `--kontakt` jest pominięty dla czytelności — dokładaj go do trybów IA.

## Tryb: NOWY URL

Dla każdego nowego URL w sprawie wykonaj w kolejności:

### 1. Własna kopia (fundament — zawsze, przed wszystkim innym)
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh lokalnie "<url>" "<katalog-sprawy>/ARCHIWUM"
```
Nie wymaga `--kontakt`. Zapisz z wyjścia SHA-256 i kod HTTP. Kod inny niż 200 też jest
ustaleniem (np. 503 = serwis nie odpowiada) — odnotuj go, nie traktuj jako porażki.

### 2. Save Page Now (niezależne poświadczenie IA)
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh save "<url>"
```
Zapisz timestamp z odpowiedzi. Jeśli błąd (429, 503, 520): odnotuj kod, kontynuuj, zaproponuj
ręczne archive.today jako backup. **Dowód jest już zabezpieczony w kroku 1** — nieudany
snapshot niczego nie przekreśla i nie jest powodem do przerywania pracy.

### 3. Pobierz surową kopię snapshotu IA (bez pasków Wayback)
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh pobierz "<url>" "<timestamp>" "<katalog-sprawy>/ARCHIWUM"
```
Plik trafia do: `ARCHIWUM/wayback-<timestamp>-<domena>.html`
SHA-256 do manifestu (`manifest.py sumy <katalog-sprawy>`).

### 4. Historia snapshotów (CDX)
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh historia "<url>"
```
Wypisz daty, w których `digest` się zmienił — to daty, w których zmienił się zapis strony.
Uwaga: digest zmieniają też elementy dynamiczne (reklamy, tokeny, znaczniki czasu), a równość
digestów między dwoma snapshotami nie wyklucza zmiany i powrotu w międzyczasie.
Jeśli więcej niż 1 snapshot: "Strona zmieniała się N razy: [daty]". Zaproponuj
pobranie wersji z kluczowych dat (zawarcie umowy, zdarzenie, dziś).

### 5. Raport do index.md
Dopisz do sekcji "Ustalenia":
```
URL: <url>
Zarchiwizowano: <timestamp> (Wayback) | SHA-256 lokalnej kopii: <hash>
Historia zmian: N wersji, ostatnia zmiana: <data>
```

## Tryb: DIFF (URL już był w sprawie)

### 1. Sprawdź digest w CDX
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh historia "<url>"
```
Porównaj digesty z poprzednim wywołaniem (zapisanym w index.md).
Jeśli digest się zmienił: "Treść zmieniła się między <data-A> a <data-B>".

### 2. Pobierz obie wersje lokalnie (jeśli nie ma)
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh pobierz "<url>" "<timestamp-stary>" "<katalog>/ARCHIWUM"
${CLAUDE_PLUGIN_ROOT}/scripts/archiwa.sh pobierz "<url>" "<timestamp-nowy>"  "<katalog>/ARCHIWUM"
```

### 3. Wyciągnij tekst i porównaj
```bash
python3 - <<'EOF'
import re, html, sys
for fname in sys.argv[1:]:
    s = open(fname, encoding='utf-8', errors='replace').read()
    s = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', s)
    s = re.sub(r'(?s)<[^>]+>', '\n', s)
    out = fname.replace('.html', '.txt')
    open(out, 'w').write('\n'.join(l.strip() for l in html.unescape(s).split('\n') if l.strip()))
EOF stary.html nowy.html
diff -u stary.txt nowy.txt > diff-<domena>-<data>.txt
```

### 4. Opisz zmianę
- Ile linii dodano / usunięto
- Czy zmiana w sekcji krytycznej (dane kontaktowe, regulamin, ceny, formularze)
- Gotowe zdanie do pisma: „W snapshotach z <X> i <Y> treść była identyczna; snapshot z <Z>
  różni się w sekcji [...]" — opisuj porównane snapshoty, nie ciągłość między nimi, bo archiwum
  nie rejestruje stanu strony w dniach bez snapshotu

SHA-256 pliku diff do manifestu. Wpis do chronologii.

## Ograniczenia — zawsze opisuj w raporcie

- Wayback nie archiwizuje treści za logowaniem → brak snapshotu ≠ strona nie istniała
- Snapshot to dowód z dokumentu osoby trzeciej, nie dokument urzędowy — wzmacniaj:
  lokalną kopią + SHA-256 + dokładnym URL snapshotu w treści pisma
- Właściciel domeny może zażądać usunięcia z Wayback → zawsze kopia lokalna
- archive.today: brak API, URL przewidywalny: `archive.ph/<rok>/<url>`
