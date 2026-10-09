# Konwencje prowadzenia spraw

## 1. Archiwum jest niezmienne
`ARCHIWUM/` jest **append-only**. Oryginał dowodu nigdy nie jest edytowany, przycinany ani
konwertowany „w miejscu”. Każda obróbka tworzy **nowy** plik obok oryginału.

Jeżeli ktoś prosi o poprawienie pliku w `ARCHIWUM/` — wyjaśnij, dlaczego tego nie robisz, i utwórz
wersję poprawioną jako nowy plik z sufiksem.

Nazewnictwo: `RRRR-MM-DD_<rodzaj>_<krotki-opis>.<ext>`, gdzie data to **data powstania dowodu**
(nadania listu, wysłania maila, wykonania zdjęcia), a nie data dodania do teczki.
Bez polskich znaków i spacji w nazwach — myślniki i podkreślenia. Rodzaje: `email`, `list`, `umowa`,
`faktura`, `zdjecie`, `skan`, `nagranie`, `zrzut`, `wydruk`, `zgloszenie`, `potwierdzenie`.

## 2. Każdy dowód ma sumę kontrolną
Po dodaniu czegokolwiek do `ARCHIWUM/`:
```
manifest.py sumy   <katalog-sprawy>
manifest.py wstaw  <katalog-sprawy>/index.md <katalog-sprawy>
```
`sumy` tylko dopisuje nowe pliki. Wpisu, którego suma się zmieniła, nie nadpisuje — zgłasza
niezgodność (exit 1), żeby ślad podmiany dowodu nie zniknął.
Manifest w `index.md` jest generowany między znacznikami `<!-- KRUCZEK:MANIFEST:START/END -->`
— nie edytuj go ręcznie. Opisy plików prowadź w osobnej tabeli **nad** manifestem.

Suma SHA-256 oryginału trafia też do treści pisma — to zabezpiecza przed zarzutem podmiany.

## 3. Dowody nietekstowe dostają wersję tekstową
Skan, zdjęcie, PDF z obrazem, nagranie rozmowy, screenshot — **od razu** przy dodaniu powstaje
plik `.md` obok oryginału, o tej samej nazwie bazowej z sufiksem `_tekst.md`:
- skan / zdjęcie / PDF-obraz → OCR (`ocrmypdf`, `tesseract -l pol`) albo odczyt modelem vision
- nagranie audio/wideo → transkrypcja z **znacznikami czasu** i oznaczeniem mówców
- e-mail `.eml` → `eml_forensics.py` (nagłówki + treść + analiza)

W nagłówku pliku tekstowego zapisz: metodę (OCR/vision/transkrypcja), narzędzie, datę,
oraz **wyraźne ostrzeżenie, że to odczyt pomocniczy, a wiążący jest oryginał**.
Fragmenty nieczytelne oznaczaj `[nieczytelne]`, niepewne `[?]`. Nie zgaduj.

## 4. Chronologia jest ciągła
Zdarzenia (wpływ pisma, nadanie, doręczenie, telefon), terminy i zadania sprawy są w `sprawa.json`
i zapisuje je wyłącznie `teczka.py` (przez komendy kruczka). Tabele „Chronologia”, „Terminy” i
„Zadania” w `index.md` są generowane między znacznikami `<!-- kruczek:… -->` — nie edytuj ich ręcznie.
Daty względne („za tydzień”) zawsze zamieniaj na bezwzględne. Bez wpisu zdarzenie nie istnieje.

## 5. Wysyłka ma własny katalog
`<YYYY_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/` — data przygotowania. W środku `ROBOCZE/`, plik `.PDF`
z pismem i `dowody.zip`. Jeśli odbiorca wymaga listu papierowego, **załączniki są wdrukowane w PDF**,
żeby wydruk był kompletny bez dokładania czegokolwiek.

## 6. Pisma cytują źródła
Każde twierdzenie prawne ma dosłowny cytat przepisu z publikatorem (Dz.U. rok/pozycja) i — jeśli
istnieje — sygnaturę orzeczenia. Cytaty pochodzą z BAZY WIEDZY albo ze źródła urzędowego,
nigdy z pamięci. Przed wysyłką: cross-check i double check (`/kruczek:weryfikuj`).

## 7. Hipotezy są oznaczone
Ustalenie niepotwierdzone dowodem (np. „to prawdopodobnie ta sama spółka”) trafia do `index.md`
z nagłówkiem `⚠ HIPOTEZY — NIE cytować w pismach` i wprost wskazanym brakującym ogniwem.
Zbieżność adresu, branży albo nazwiska to trop, nie dowód.

Najgorszy błąd w całym procesie to hipoteza napisana w piśmie w trybie oznajmującym — druga strona
obala jedno niepotwierdzone twierdzenie i podważa wszystko pozostałe.

## 8. Dane osobowe
`_SZABLONY/dane-nadawcy.md` i teczki spraw zawierają dane osobowe. Jeżeli repozytorium ma trafić
do gita — pamiętaj o `.gitignore`. Nie wysyłaj danych z teczki do usług zewnętrznych bez potrzeby.

## 9. Język
Cała dokumentacja i wszystkie pisma po polsku. Nazwy plików i katalogów bez polskich znaków.
W pismach: forma bezosobowa lub pierwsza osoba, bez emocji, bez sarkazmu, bez wykrzykników.
