---
name: chronologia
description: Zapisuje zdarzenie w teczce sprawy albo pokazuje pełną oś czasu z terminami. Użyj po każdym nadaniu pisma, doręczeniu, telefonie, mailu i upływie terminu.
argument-hint: "[sprawa] [opis zdarzenia]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py *) Bash(date *) Bash(ls *) Read AskUserQuestion
---

# Chronologia sprawy

Argumenty: `$ARGUMENTS`

Zadanie mechaniczne: jedno zdarzenie, właściwy typ, data bezwzględna. Zapis przez `teczka.py`
według sekcji „Zapis do teczki — teczka.py” w `konwencje-teczki`.

## Dopisanie

Pytania do użytkownika zadawaj narzędziem AskUserQuestion — kilka naraz w jednym wywołaniu, gdy znasz je
z góry (najwyżej 4), zamiast pytać w treści odpowiedzi.

1. Data `RRRR-MM-DD` (dziś: `date +%F`); „za tydzień”, „wczoraj” zamień na datę bezwzględną.
   Godzina, jeśli znana (maile, telefony).
2. Typ według kierunku (tabela w `konwencje-teczki`) i wątek (zwykle istniejący — korespondencja tam i z powrotem).
3. **Nadanie:** termin dla adresata weź z `Termin, który wyznaczasz` w najnowszym `*-DO_WYSYLKI/TLDR.md`
   tej sprawy (długość + „wyznaczony w piśmie”) albo z przepisu, na który pismo się powołuje. Brak — zapytaj.
4. **Odpowiedź / wpływ:** zapytaj jednym zdaniem, czy pismo wyznacza Tobie termin (np. 14 dni na odwołanie).
   `--termin` zawsze razem z `--podstawa` wziętą z pisma albo przepisu; nie wiesz — zapytaj użytkownika, nie zgaduj.
5. Dowód: plik z `ARCHIWUM/` (`--dowod`); brak dowodu → zdarzenie i tak zapisz, a potem
   `teczka.py zadanie <sprawa> "Pozyskaj dowód: <opis>"`.

```
${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py zdarzenie <sprawa> --typ <typ> --data <data> [--godzina GG:MM] \
  [--watek <id>] [--dotyczy <id nadania>] --opis "<opis>" [--dowod ARCHIWUM/<plik>] [--termin 14d --podstawa "<podstawa>"]
```

Gdy `teczka.py` odpowie, że czeka kilka pism — pokaż je użytkownikowi i powtórz polecenie z `--dotyczy <id nadania>`.

Zamelduj jedną linią: co zapisano i jaki termin z tego wynika (z wyjścia `teczka.py`).

## Typowe zdarzenia, o których się zapomina

- nadanie listu (numer nadania!) i data doręczenia z EPO
- data odbioru wynikająca z awizo / fikcja doręczenia
- rozmowa telefoniczna: kto dzwonił, z jakiego numeru, co ustalono
- automatyczna odpowiedź „potwierdzamy przyjęcie zgłoszenia" z numerem sprawy
- upływ terminu ustawowego (np. 14 dni na reklamację, miesiąc z art. 12 ust. 3 RODO)

## Gdy proszą o przegląd, nie o dopisanie

Przeczytaj bloki „Chronologia”, „Terminy” i „Zadania” w `index.md` (są aktualne po każdym zapisie).
Brak bloków `<!-- kruczek:… -->` w `index.md` = stary format — zaproponuj `/kruczek:migruj`.
Zaznacz osobno: terminy minione, najbliższe (≤ 7 dni), zdarzenia bez dowodu. Bez porady prawnej —
od tego jest `/kruczek:eskalacja` (podpowiedź dla użytkownika).
