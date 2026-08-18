---
name: konwencje-teczki
description: Zasady prowadzenia teczki sprawy — niezmienne archiwum, nazewnictwo plików, sumy kontrolne, chronologia, oddzielanie faktów od hipotez, katalogi do wysyłki. Obowiązują przy każdej pracy na plikach sprawy.
when_to_use: Praca na plikach w katalogu sprawy, dodawanie dowodów, edycja index.md, przygotowanie wysyłki, pytania o strukturę teczki.
user-invocable: false
---

# Konwencje teczki sprawy

## Archiwum jest niezmienne

`ARCHIWUM/` jest **append-only**. Oryginał dowodu nigdy nie jest edytowany, przycinany,
kompresowany ani konwertowany „w miejscu". Każda obróbka tworzy **nowy** plik obok oryginału.

Jeżeli ktoś prosi o poprawienie pliku w archiwum — wyjaśnij, dlaczego tego nie robisz, i utwórz
wersję poprawioną jako nowy plik z sufiksem.

## Nazewnictwo

`RRRR-MM-DD_<rodzaj>_<krotki-opis>.<ext>`

Data to **data powstania dowodu** (nadania, wysłania, wykonania zdjęcia), nie data dodania do teczki.
Bez polskich znaków i spacji w nazwach — myślniki i podkreślenia. Rodzaje: `email`, `list`, `umowa`,
`faktura`, `zdjecie`, `skan`, `nagranie`, `zrzut`, `wydruk`, `zgloszenie`, `potwierdzenie`.

Katalog wysyłki: `<RRRR_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI/` (data przygotowania), w środku
`ROBOCZE/`, plik `.PDF` z pismem i `dowody.zip`.

## Sumy kontrolne

Po każdej zmianie w `ARCHIWUM/`:
```
manifest.py sumy  <sprawa>
manifest.py wstaw <sprawa>/index.md <sprawa>
```
Manifest w `index.md` jest generowany między znacznikami `<!-- KRUCZEK:MANIFEST:START/END -->`
— nie edytuj go ręcznie. Opisy plików prowadź w osobnej tabeli **nad** manifestem.

Suma SHA-256 oryginału trafia też do treści pisma — zabezpiecza przed zarzutem podmiany dowodu.

## Dowody nietekstowe mają wersję tekstową

Skan, zdjęcie, PDF-obraz, nagranie, zrzut ekranu — **od razu** przy dodaniu powstaje `.md` obok
oryginału, z nagłówkiem informującym o metodzie odczytu i o tym, że wiążący jest oryginał.
Fragmenty nieczytelne: `[nieczytelne]`, niepewne: `[?]`. Nigdy nie uzupełniaj domysłem.

## Chronologia jest ciągła

Tabela `| Data | Godz. | Zdarzenie | Dowód |` w sekcji 1 `index.md`. Każde zdarzenie: wpływ pisma,
nadanie, doręczenie, telefon, upływ terminu. Daty względne zawsze zamieniaj na bezwzględne.
Przyszłe terminy wpisuj jako wiersze w przyszłości. Bez wpisu zdarzenie nie istnieje.

## Fakty ≠ hipotezy

Ustalenie bez pełnego dowodu trafia do sekcji `⚠ HIPOTEZY — NIE cytować w pismach`, z wyraźnie
wskazanym brakującym ogniwem. Zbieżność adresu, branży czy nazwiska to poszlaka, nie dowód.

Najgorszy błąd w całym procesie to hipoteza napisana w piśmie w trybie oznajmującym — druga strona
obala jedno niepotwierdzone twierdzenie i podważa wszystko pozostałe.

## Dane osobowe

`_SZABLONY/dane-nadawcy.md` i teczki spraw zawierają dane osobowe. Jeżeli repozytorium ma trafić
do gita — przypomnij o `.gitignore`. Nie wysyłaj danych z teczki do usług zewnętrznych bez potrzeby.

## Język

Cała dokumentacja i wszystkie pisma po polsku. Nazwy plików i katalogów bez polskich znaków.
W pismach: forma bezosobowa lub pierwsza osoba, bez emocji, bez sarkazmu, bez wykrzykników.
