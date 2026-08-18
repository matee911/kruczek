---
name: kontrola
description: "Mechaniczna kontrola gotowego pisma przed przekazaniem użytkownikowi — niewypełnione pola, ciągłość numeracji, zgodność nazw i numerów załączników w treści i na stronach załączników, sumy kontrolne, wymogi druku. Uruchamiaj po każdym build-pismo.py, zanim pokażesz pismo."
argument-hint: "[pismo.pdf] [katalog sprawy]"
disable-model-invocation: false
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kontrola-pisma.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(pdftotext *) Bash(unzip -l *) Read
---

# Kontrola mechaniczna pisma

Argumenty: `$ARGUMENTS`

Zadanie mechaniczne. Uruchamiasz skrypt, czytasz wynik, raportujesz. Nie oceniasz treści ani prawa —
od tego jest `/kruczek:recenzja`.

**Ta kontrola jest obowiązkowa przed pokazaniem pisma użytkownikowi.** Nie melduj gotowości pisma,
zanim jej nie uruchomisz.

## Uruchom

```
${CLAUDE_PLUGIN_ROOT}/scripts/kontrola-pisma.py <pismo.pdf> --sprawa <katalog-sprawy> --zip <dowody.zip>
${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py sprawdz <katalog-sprawy>
```

## Co skrypt sprawdza

| Kontrola | Dlaczego to ma znaczenie |
|---|---|
| Niewypełnione pola `[…]` i placeholdery | pismo z `[NIP]` w nagłówku kompromituje przy pierwszym spojrzeniu |
| Ciągłość numeracji załączników | dziura w numeracji = odbiorca twierdzi, że czegoś nie dostał |
| Każde `(zał. N)` w treści ma odpowiadający załącznik | odesłanie w próżnię podważa cały wywód |
| Załącznik dołączony, ale nieprzywołany w treści | dowód, do którego pismo się nie odwołuje, nic nie wnosi |
| Tytuł na liście = tytuł na stronie załącznika | rozjazd nazw to klasyczny powód sporu o kompletność |
| Każda suma SHA-256 z pisma odpowiada realnemu plikowi | suma w piśmie jest zobowiązaniem |
| Ciągłość numeracji ustępów, brak powtórzeń | powtórzone „1." to najczęstszy błąd redakcyjny |
| `dowody.zip`: niepusty, nieuszkodzony, z `SHA256SUMS.txt` | odbiorca musi móc zweryfikować |
| Rozmiar ≤ 2 MB, ≤ 98 kartek, fonty osadzone | Envelo i e-Doręczenia odrzucą plik, który tego nie spełnia |
| Widoczny blok podpisu | brak miejsca na podpis = pismo do przerobienia |

## Czego skrypt nie sprawdzi — sprawdź to sam, patrząc

1. **Czy załączniki się nie ucięły.** Otwórz strony załączników (`pdftotext -f N -l M`) i zobacz,
   czy tabela nie wyszła poza margines i czy tekst nie urwał się w połowie.
2. **Czy polskie znaki renderują się poprawnie** — poszukaj w tekście `ą ę ł ń ó ś ź ż`.
   Kwadraty albo braki oznaczają problem z fontem.
3. **Czy nazwy plików załączników są sensowne.** `zalacznik1.pdf` nic nie mówi;
   `2026-08-12_email_naglowki.txt` mówi wszystko. Nazwa pliku trafia do stopki załącznika w PDF
   i odbiorca ją widzi.
4. **Czy nazwa katalogu wysyłki** ma postać `<RRRR_MM_DD>-<CO>-<DO_KOGO>-DO_WYSYLKI`.

## Raport

Wypisz dokładnie to, co zwrócił skrypt, w dwóch grupach: **błędy blokujące** i **ostrzeżenia**.
Przy każdym błędzie podaj, co konkretnie poprawić.

Jeśli skrypt zwrócił kod 0 i nie ma ostrzeżeń — jedno zdanie: kontrola mechaniczna czysta,
następny krok to `/kruczek:recenzja`.

**Nie poprawiaj pisma samodzielnie**, jeśli błąd dotyczy treści merytorycznej — zgłoś go
i przekaż do `/kruczek:pismo`. Sam poprawiaj tylko rzeczy jednoznacznie mechaniczne: literówkę
w nazwie pliku, brakujący wpis na liście załączników, nieaktualną sumę kontrolną.
