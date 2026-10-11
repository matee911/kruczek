---
name: serve
description: Otwiera lokalną stronę teczki w przeglądarce — Po terminie, Teraz, Czekam, Wkrótce i ekran każdej sprawy; „Zrobione” i data doręczenia zapisują się od razu, z „Cofnij”. Użyj, gdy chcesz zobaczyć wszystkie sprawy naraz albo odhaczać zadania bez wpisywania poleceń.
argument-hint: "[katalog projektu]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kruczek_serve.py *) Bash(command -v uv)
---

# Strona teczki

1. Sprawdź `command -v uv`. Brak `uv` → powiedz, że strona wymaga `uv` (https://docs.astral.sh/uv/), i zakończ.
2. Katalog projektu: `$1`, a bez argumentu bieżący katalog. Uruchom **w tle** (to serwer, nie kończy się sam):
   `${CLAUDE_PLUGIN_ROOT}/scripts/kruczek_serve.py <katalog> --port 8765`
3. Podaj adres z pierwszej linii wyjścia (`http://127.0.0.1:8765/`). Strona działa tylko na tym komputerze
   (127.0.0.1), nie łączy się z internetem i nie udostępnia plików dowodów — pokazuje tylko ich nazwy.
4. Kod 1 z „port … jest zajęty” → uruchom z portem z komunikatu (`--port 8766`). Inny błąd — przekaż komunikat.
5. Ze strony zapisują się tylko „Zrobione” i data doręczenia (do `sprawa.json`, tak samo jak przez `teczka.py`).
   Resztę strona podaje jako polecenie do wklejenia tutaj (np. `/kruczek:eskalacja <sprawa>`) — wykonaj je jak zwykle.
6. Zatrzymanie: zakończ proces w tle.
