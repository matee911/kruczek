---
name: nowa-sprawa
description: Zakłada teczkę nowej sprawy — katalog podmiotu, index.md z chronologią, ustaleniami, manifestem i ścieżką eskalacji. Użyj, gdy zaczynasz spór z konkretną firmą lub instytucją.
argument-hint: "[nazwa podmiotu] [przedmiot sprawy]"
disable-model-invocation: true
model: sonnet
effort: medium
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/nowa-sprawa.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh *) Read Write Edit
---

# Nowa sprawa

Argumenty: `$ARGUMENTS`

## 1. Ustal minimum

Potrzebujesz **nazwy podmiotu** i **jednozdaniowego przedmiotu sprawy**. Jeśli ich nie ma
w argumentach ani w rozmowie, zapytaj — jednym wywołaniem AskUserQuestion, razem z pytaniem
o to, co użytkownik chce osiągnąć (zaprzestanie / zwrot pieniędzy / naprawa / informacja /
ukaranie), bo to determinuje całą dalszą ścieżkę.

Jeśli w rozmowie jest już materiał źródłowy (mail, umowa, zdjęcie) — **nie czytaj go teraz w całości**.
Załóż sprawę, a materiał wciągnij przez `/kruczek:dowod`.

## 2. Załóż katalog

```
${CLAUDE_PLUGIN_ROOT}/scripts/nowa-sprawa.sh "<nazwa>" "<przedmiot>" <katalog-projektu>
```

Skrypt tworzy `ARCHIWUM/`, `ROBOCZE/` i `index.md` ze szkieletem: chronologia, ustalenia,
hipotezy, podstawa prawna, manifest, TODO, eskalacja.

## 3. Ustal dane rejestrowe przeciwnika

Jeśli znasz NIP albo KRS — od razu:
```
${CLAUDE_PLUGIN_ROOT}/scripts/podmiot.sh pelny <NIP>
```
Jeśli masz tylko nazwę lub stronę WWW, zleć to subagentowi `ustalacz-podmiotu` (haiku — to
mechaniczne odpytanie rejestrów). Wynik wpisz do tabeli nagłówkowej `index.md`.

**Nie zgaduj tożsamości podmiotu.** Jeśli powiązanie jest tylko prawdopodobne (zbieżny adres,
ta sama branża), wpisz je do sekcji `⚠ HIPOTEZY` z wyraźnym wskazaniem brakującego ogniwa.
Ustalenie tożsamości bywa samodzielnym celem pierwszego pisma.

## 4. Sprawdź bazę wiedzy

Zajrzyj do `BAZA_WIEDZY/index.md`. Jeśli są tam już przepisy pasujące do tego typu sprawy —
wypisz je w sekcji „Podstawa prawna" `index.md` sprawy jako punkt wyjścia. Jeśli baza jest pusta
w tym zakresie, zaznacz to w TODO. **Nie rób teraz researchu prawnego** — to zadanie na etapie pisma.

## 5. Dopisz sprawę do rejestru

Dodaj wiersz do tabeli „Sprawy" w `index.md` projektu.

## 6. Podsumuj

Trzy zdania: gdzie jest teczka, czego brakuje, jaka jest następna komenda
(zwykle `/kruczek:dowod`).
