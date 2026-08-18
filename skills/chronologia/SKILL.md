---
name: chronologia
description: Dopisuje zdarzenie do chronologii sprawy albo pokazuje pełną oś czasu z terminami. Użyj po każdym nadaniu pisma, doręczeniu, telefonie, mailu i upływie terminu.
argument-hint: "[sprawa] [opis zdarzenia]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Read Edit Bash(date *) Bash(ls *)
---

# Chronologia sprawy

Argumenty: `$ARGUMENTS`

Zadanie mechaniczne: jeden wiersz w tabeli, właściwe miejsce, właściwy format.

## Format

Tabela w sekcji „1. Chronologia" pliku `index.md` sprawy:

```
| Data | Godz. | Zdarzenie | Dowód |
```

Zasady:

1. **Daty bezwzględne.** „Za tydzień", „w przyszły piątek", „wczoraj" zamień na `RRRR-MM-DD`
   (sprawdź dzisiejszą datę przez `date +%F`). Jeśli zamiana wymaga założenia — dopisz je w opisie.
2. **Porządek chronologiczny.** Wstaw wiersz w odpowiednie miejsce, nie na koniec tabeli.
3. **Godzina, jeśli jest znana.** Przy mailach i telefonach potrafi rozstrzygnąć spór o kolejność.
4. **Kolumna „Dowód"** wskazuje plik z `ARCHIWUM/` albo `—`, gdy dowodu nie ma. Zdarzenie bez dowodu
   też wpisujesz — ale wtedy dopisz w TODO, żeby dowód pozyskać (np. potwierdzenie nadania).
5. **Terminy liczysz i wpisujesz jako osobne wiersze w przyszłości**, np.
   `| 2026-09-02 | | UPŁYW 14-dniowego terminu z wezwania z 19.08.2026 | — |`.
   Zaktualizuj też pole „Najbliższy termin" w tabeli nagłówkowej.

## Typowe zdarzenia, o których się zapomina

- nadanie listu (numer nadania!) i data doręczenia z EPO
- data odbioru wynikająca z awizo / fikcja doręczenia
- rozmowa telefoniczna: kto dzwonił, z jakiego numeru, co ustalono
- automatyczna odpowiedź „potwierdzamy przyjęcie zgłoszenia" z numerem sprawy
- upływ terminu ustawowego (np. 14 dni na reklamację, miesiąc z art. 12 ust. 3 RODO)

## Gdy proszą o przegląd, nie o dopisanie

Wypisz oś czasu w kolejności i **osobno** zaznacz: terminy już upłynięte, terminy najbliższe
(≤ 7 dni), zdarzenia bez dowodu. Nie doradzaj prawnie — od tego jest `/kruczek:eskalacja`.
