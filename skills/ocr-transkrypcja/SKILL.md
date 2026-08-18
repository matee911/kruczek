---
name: ocr-transkrypcja
description: Jak zrobić wersję tekstową dowodu nietekstowego — OCR skanu i zdjęcia, odczyt PDF-a bez warstwy tekstowej, transkrypcja nagrania rozmowy, opis zrzutu ekranu. Użyj przy każdym dowodzie, którego nie da się wyszukać tekstem.
when_to_use: Skan, zdjęcie dokumentu, PDF z obrazem, nagranie rozmowy, plik audio lub wideo, zrzut ekranu dodawany do sprawy; potrzeba wersji tekstowej dowodu.
model: sonnet
effort: medium
---

# Wersja tekstowa dowodu nietekstowego

Każdy dowód, którego nie da się przeszukać tekstem, dostaje plik `.md` obok oryginału —
**od razu przy dodaniu do archiwum**, nie „kiedyś potem". Bez tego dowód jest martwy: nie da się
go zacytować w piśmie ani znaleźć za pół roku.

Nazwa: `<nazwa-oryginału-bez-rozszerzenia>_tekst.md`

## Obowiązkowy nagłówek

```markdown
> **Odczyt pomocniczy.** Metoda: <OCR tesseract -l pol / odczyt vision / transkrypcja>.
> Data: RRRR-MM-DD. Plik źródłowy: `<nazwa>`, SHA-256: `<suma>`.
> Wiążąca jest treść oryginału. Fragmenty nieczytelne oznaczono `[nieczytelne]`, niepewne `[?]`.
```

Bez tego nagłówka odczyt może zostać wzięty za dokument — a to jest tylko pomoc w nawigacji.

## Skan, zdjęcie dokumentu, PDF bez warstwy tekstowej

Najpierw sprawdź, czy PDF nie ma już warstwy tekstowej:
```bash
pdftotext -layout plik.pdf - | head -20     # jeśli wychodzi tekst — OCR niepotrzebny
```

Jeśli nie ma:
```bash
ocrmypdf -l pol --skip-text wejscie.pdf wyjscie_ocr.pdf && pdftotext -layout wyjscie_ocr.pdf -
# albo dla obrazów:
tesseract obraz.jpg - -l pol
```
Zawsze `-l pol` — bez tego polskie znaki diakrytyczne wyjdą losowo.

Gdy OCR zawodzi (odręczne pismo, zły skan, tabela) — odczytaj obraz modelem vision (Read na pliku
graficznym). Zachowaj **układ dokumentu**: nagłówki, tabele jako tabele markdown, numerację punktów,
pieczątki i podpisy opisz w nawiasach kwadratowych `[pieczątka okrągła: …]`, `[podpis nieczytelny]`.

## Nagranie audio lub wideo

Transkrypcja ze **znacznikami czasu** co ok. 30 sekund lub przy każdej zmianie mówcy:

```markdown
**[00:00]** KONSULTANT: Dzień dobry, w czym mogę pomóc?
**[00:14]** KLIENT: Dzwonię w sprawie reklamacji numer 4471.
**[01:02]** KONSULTANT: [nieczytelne — zakłócenia] …termin czternastu dni.
```

Mówców oznaczaj rolami, nie imionami, chyba że padły w nagraniu. Notuj długie pauzy, przerywanie,
komunikaty automatu i moment, w którym rozmowa się urywa.

Jeśli nie masz narzędzia do transkrypcji, powiedz to wprost i zaproponuj alternatywę
(`whisper`, usługa zewnętrzna) — **nie zmyślaj treści nagrania**.

## Zrzut ekranu

Opisz to, co widać, i **to, co dowodzi**: pełny widoczny tekst, data i godzina z paska systemowego
lub z interfejsu, adres URL, numer sprawy, stan przycisków i komunikatów. Przy zrzucie z czatu
lub maila zachowaj kolejność i autorstwo wypowiedzi.

## Zasady, od których nie ma wyjątków

1. **Nie uzupełniaj domysłem.** Czego nie widać, oznacz `[nieczytelne]`. Odczyt niepewny — `[?]`.
   Zmyślony fragment odczytu jest gorszy niż jego brak, bo trafi do pisma jako cytat.
2. **Nie poprawiaj oryginału.** Literówki, błędy i dziwne sformułowania w dokumencie drugiej strony
   przepisujesz wiernie — bywają istotne.
3. **Nie streszczaj.** To ma być odczyt, nie podsumowanie. Streszczenie zrób osobno, niżej,
   w sekcji „Podsumowanie" — wyraźnie oddzielonej.
4. **Zaznacz, czego nie objąłeś** — strony, których nie było w skanie, urwane nagranie, ucięty zrzut.

## Po odczycie

Zapisz plik obok oryginału w `ARCHIWUM/`, przelicz sumy (`manifest.py sumy`), dopisz wiersz
do tabeli opisowej i do chronologii. Komenda `/kruczek:dowod` robi to całościowo.

## Delegowanie

Zleć subagentowi `transkrybuj` (sonnet). Haiku nie nadaje się do odczytu polskich skanów —
gubi znaki diakrytyczne i myli podobne litery.
