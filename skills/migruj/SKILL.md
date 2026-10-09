---
name: migruj
description: Przenosi starą teczkę (index.md bez sprawa.json) na nowy format — czyta chronologię i TODO, pokazuje podgląd zdarzeń, terminów i zadań, zapisuje dopiero po akceptacji, z kopią starego index.md. Użyj, gdy status albo inna komenda mówi „stary format”.
argument-hint: "[sprawa albo katalog projektu]"
disable-model-invocation: true
model: sonnet
effort: medium
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py *) Bash(date *) Bash(ls *) Read Write Edit
---

# Migracja teczki na sprawa.json

Argument: `$1` — katalog sprawy albo projektu (domyślnie bieżący).

Zasada: **nic nie ginie i nic nie jest zgadywane.** Stary `index.md` zostaje (kopia w `ROBOCZE/`,
stara tabela chronologii pod nagłówkiem „Chronologia sprzed migracji (archiwalna)”). Zdarzenie bez
pewnej daty nie trafia do `sprawa.json` — wypisujesz je użytkownikowi.

`teczka.py migruj` bez `--zapisz` to tylko podgląd (nic nie zapisuje). Zapis robi dopiero z `--zapisz`,
po akceptacji użytkownika.

## 0. Przygotuj projekt

W `.gitignore` projektu muszą być linie `.sprawa.lock` i `.*.tmp` — dopisz brakujące (Edit), nie ruszaj reszty.

## 1. Lista spraw

`${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py co-robic <projekt>` → sekcja `STARY FORMAT`.
Jeśli `$1` to jedna sprawa — tylko ona. Migrujesz **po jednej**, każdą z akceptacją.

- Wpis `podprojekt/sprawa` to sprawa w podprojekcie („# Rejestr spraw”). Migrujesz ją jako
  `<projekt>/podprojekt/sprawa`; samego podprojektu `migruj` nie przeniesie.
- Foldery z sekcji `POMINIĘTO (brak index.md)` — powiedz użytkownikowi, że je pominięto; nie migruj ich.

## 2. Propozycja

Przeczytaj `index.md` sprawy i listę plików `ARCHIWUM/` (`ls`). Jeśli `index.md` nie jest w UTF-8,
`migruj` odmówi — powiedz o tym użytkownikowi i pomiń sprawę. Zapisz `ROBOCZE/migracja-propozycja.json`:

```json
{
  "tytul": "<przedmiot sprawy z nagłówka>",
  "strona_przeciwna": "<podmiot>",
  "zamknieta": false,
  "wynik": null,
  "watki": [{"id": "<krótko, np. firma, uodo>", "adresat": "<nazwa>"}],
  "zdarzenia": [
    {"klucz": "<unikalny, np. reklamacja>", "data": "RRRR-MM-DD", "godzina": "GG:MM albo null",
     "typ": "nadanie|doreczenie|odpowiedz|wplyw|fakt|telefon|inne", "opis": "<z tabeli>",
     "watek": "<id wątku albo null>", "dowody": ["ARCHIWUM/<plik>"], "pewnosc": null,
     "termin": {"dlugosc": "14d", "podstawa": "<z pisma albo przepisu>"}, "dotyczy": "<klucz nadania albo null>"}
  ],
  "zadania": [{"opis": "<niezaznaczona pozycja TODO>", "aktywne_od": "<dziś>", "termin": null, "watek": null}]
}
```

Reguły przepisywania:
- Nagłówek `# SPRAWA:` albo `# Sprawa:` — wielkość liter bez znaczenia; z niego bierz tytuł.
- Wiersze w przyszłości typu „UPŁYW terminu …” **nie są zdarzeniami** — to `termin` przy nadaniu,
  którego dotyczą (długość i podstawa z pisma/przepisu; jeśli ich nie ma w teczce — bez terminu
  i zadanie „ustal termin odpowiedzi na <pismo>”).
- Potwierdzenie odbioru / EPO → `doreczenie` z `dotyczy` = `klucz` nadania (nie id — id powstaje dopiero
  przy zapisie). Gdy podgląd prosi o wskazanie nadania, bo czekają naraz dwa Twoje pisma, ustaw
  `"dotyczy": "<klucz nadania>"` w propozycji.
- Pismo od firmy → `odpowiedz`; decyzja, wezwanie, nakaz → `wplyw` (z `termin`, jeśli wyznacza Tobie).
- Wątek = korespondencja tam i z powrotem z jednym adresatem (pismo → odpowiedź → kontra → …).
  Wszystkie zdarzenia z jedną firmą to jeden wątek; nigdy jeden wątek na pismo. Osobny wątek tylko dla
  innego adresata (np. UODO).
- „Status: zamknięta / wygrana / ugoda” → `zamknieta: true` i `wynik` (`wygrana`, `ugoda`, `porzucona`).
- Niezaznaczone TODO → `zadania` (aktywne od dziś); zaznaczone pomiń. TODO „Wpisać termin kontrolny do
  chronologii” też pomiń — termin daje nadanie z `--termin`.
- Fakty z oznaczeniem pewności → `pewnosc` (`dowod`, `poszlaka`, `wlasne_oswiadczenie`).
- Wiersz bez daty albo z datą niepewną → **nie wpisuj**; zanotuj do listy „nieprzeniesione”.

## 3. Podgląd

`${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py migruj <sprawa> <sprawa>/ROBOCZE/migracja-propozycja.json`

Błąd (kod 1) → popraw propozycję i uruchom ponownie. Pokaż użytkownikowi zwięźle: wątki, liczby,
wygenerowaną chronologię i terminy, ostrzeżenia `uwaga:` i listę „nieprzeniesione”. Potem jedno
AskUserQuestion: **Zapisz** / **Popraw** (co) / **Pomiń tę sprawę**.

## 4. Zapis

Po „Zapisz”: to samo polecenie z `--zapisz`. Kopia starego `index.md` ląduje w `ROBOCZE/` — podaj
ścieżkę. Kod 1 = nic nie zapisano (pokaż komunikat). Kod 0 z `uwaga:` = `sprawa.json` zapisana, tylko
`index.md` się nie odświeżył — nie powtarzaj polecenia. Jeśli podgląd ostrzegał o starych zadaniach —
zapytaj, które oznaczyć jako zrobione (`teczka.py zrobione <sprawa> <id>`, po jednym).

## 5. Następna sprawa

Wróć do kroku 2. Na końcu jedna linia: ile spraw przeniesiono, ile pominięto, ile zostało.
