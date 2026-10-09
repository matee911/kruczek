---
name: status
description: Przegląd wszystkich spraw w repozytorium — terminy, zaległości, sprawy bez ruchu, niespójne sumy kontrolne. Użyj, gdy pytasz "co mam do zrobienia", "jak stoją sprawy", "czy coś mi ucieka".
argument-hint: "[katalog projektu]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py co-robic *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sprawdz *) Bash(ls *) Bash(date *) Read
---

# Status spraw

Katalog: `$1` (domyślnie bieżący). Zadanie mechaniczne — liczy kod, Ty porządkujesz.

## 1. Przegląd

`${CLAUDE_PLUGIN_ROOT}/scripts/teczka.py co-robic <katalog albo .>` — zawsze podaj ścieżkę (`$1`, a gdy
go brak, `.`).
Kod 1 = sekcja `BŁĘDY` (nieczytelna sprawa) — reszta przeglądu i tak jest; wypisz błąd z nazwą pliku.

## 2. Spójność

Dla każdej sprawy z przeglądu: `${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sprawdz <sprawa>` —
zgłoś każdą niezgodną sumę (plik zmieniony po zaewidencjonowaniu albo nieaktualny manifest).

## 3. Wypisz — w tej kolejności

**🔴 Po terminie** — pozycje z `PO TERMINIE`. **🟠 Teraz** — reszta `TERAZ`, z terminem na górze.
**⏳ Czekam** — `CZEKAM` (data i „szacunek”, jeśli jest). **🗓 Wkrótce** — `WKRÓTCE`.
**⚪ Bez ruchu** — `BEZ RUCHU`. **📦 Stary format** — `STARY FORMAT` → `/kruczek:migruj`.
**⚠ Problemy techniczne** — `BŁĘDY`, niezgodne sumy.

Każda pozycja z nazwą folderu i id zadania, żeby dało się odpisać `teczka.py zrobione <folder> <id>`.
Na końcu **jedna** rekomendacja: co najpilniejsze i jaka komenda to posunie. Wszystko w porządku —
jedno zdanie.
