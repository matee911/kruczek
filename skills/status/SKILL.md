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

## 3. Terminy spraw w starym formacie

Sprawy z sekcji `STARY FORMAT` nie mają `sprawa.json`, więc ich terminów nie ma w `TERAZ` ani `CZEKAM`.
Dla każdej przeczytaj `<katalog>/<sprawa z listy>/index.md` i wypisz z niego dosłownie: wiersz
„Najbliższy termin” z nagłówka oraz wiersze chronologii z datą od dziś (`date +%F`) wzwyż, zwłaszcza
„UPŁYW …”. Cytuj to, co jest w pliku — nie licz, nie poprawiaj i nie zgaduj dat. Brak takich wierszy —
napisz „brak terminu w index.md”.

## 4. Wypisz — w tej kolejności

**🔴 Po terminie** — pozycje z `PO TERMINIE`. **🟠 Teraz** — reszta `TERAZ`, z terminem na górze.
**⏳ Czekam** — `CZEKAM` (data i „szacunek”, jeśli jest). **🗓 Wkrótce** — `WKRÓTCE`.
**⚪ Bez ruchu** — `BEZ RUCHU`. **📦 Stary format** — `STARY FORMAT` → `/kruczek:migruj` (podpowiedź dla użytkownika); pod każdą sprawą
jej terminy z kroku 3, osobno, z dopiskiem „nie liczone kodem — zmigruj (/kruczek:migruj)” (podpowiedź dla użytkownika).
**⚠ Problemy techniczne** — `BŁĘDY`, niezgodne sumy.
**Pominięte** — `POMINIĘTO (brak index.md)`: wypisz te foldery jednym zdaniem (to zwykle kopie albo duplikaty,
nie ma czego migrować). Nie proponuj ich migracji.

Każda pozycja ze ścieżką sprawy (folder z `co-robic`, względem katalogu projektu) i id zadania, żeby dało się
odpisać `teczka.py zrobione <ścieżka sprawy> <id>`. Wyjątek: „sprawdź datę doręczenia” zamyka się wpisaniem
doręczenia (`teczka.py zdarzenie <ścieżka sprawy> --typ doreczenie --data <data z EPO> --watek <w>`), nie przez
`zrobione` — dopiero doręczenie przelicza termin adresata.
Na końcu **jedna** rekomendacja: co najpilniejsze i jaka komenda to posunie. Wszystko w porządku —
jedno zdanie.
