---
name: status
description: Przegląd wszystkich spraw w repozytorium — terminy, zaległości, sprawy bez ruchu, niespójne sumy kontrolne. Użyj, gdy pytasz "co mam do zrobienia", "jak stoją sprawy", "czy coś mi ucieka".
argument-hint: "[katalog projektu]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sprawdz *) Bash(ls *) Bash(find *) Bash(date *) Read
---

# Status spraw

Katalog: `$1` (domyślnie bieżący).

Zadanie mechaniczne — zbierz dane, posortuj, wypisz. Bez analizy prawnej.

## 1. Zbierz

Dla każdego katalogu sprawy (ten, który ma `index.md` z nagłówkiem `# SPRAWA:`):
- pole **Status** i **Najbliższy termin** z tabeli nagłówkowej
- ostatni wiersz **chronologii** (data ostatniego ruchu)
- niezaznaczone pozycje **TODO**
- czy istnieje katalog `*-DO_WYSYLKI` i czy pismo zostało nadane (szukaj w chronologii słowa
  „nadanie" / „nadano" / numeru nadania)

## 2. Sprawdź spójność

Dla każdej sprawy uruchom:
```
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sprawdz <sprawa>
```
Zgłoś każdą niezgodność sumy kontrolnej — to znaczy, że plik dowodowy został zmieniony po
zaewidencjonowaniu, albo że manifest jest nieaktualny.

## 3. Wypisz — w tej kolejności

**🔴 Po terminie** — termin minął, brak reakcji w chronologii. Podaj, ile dni temu.

**🟠 W ciągu 7 dni** — najbliższe terminy.

**⚪ Bez ruchu ponad 30 dni** — sprawy, w których nic się nie dzieje. Podaj datę ostatniego wpisu.

**⚠ Problemy techniczne** — niezgodne sumy, brakujące pliki, dowody bez wersji tekstowej,
zdarzenia bez dowodu.

**Pozostałe** — jedna linia na sprawę.

Na końcu **jedna** rekomendacja: która sprawa wymaga uwagi najpilniej i jaka komenda ją posunie.
Jeśli wszystko jest w porządku — powiedz to w jednym zdaniu, bez rozwlekania.
