---
name: fakt
description: Rejestruje fakt słowny (bez pliku) w sprawie — kontekstowy (rola, relacja, stan trwały) lub zdarzeniowy (coś się wydarzyło w czasie). Przy zdarzeniowych pyta o datę i dowód, oznacza pewność, wpisuje do chronologii. Użyj, gdy masz informację bez pliku — telefon, rozmowę, obserwację, rolę osoby.
argument-hint: "[sprawa] [opis faktu]"
disable-model-invocation: true
model: haiku
effort: low
allowed-tools: Read Write Edit
---

# Rejestracja faktu słownego

Argumenty: `$ARGUMENTS`

To komenda dla informacji **bez pliku**. Jeśli masz plik (mail, skan, PDF) — użyj
`/kruczek:dowod`. Jeśli masz plik i opis — najpierw `/kruczek:fakt`, potem `/kruczek:dowod`.

## 1. Klasyfikuj fakt

**Kontekstowy** — rola, relacja, właściwość, stan trwały (nie ma daty wystąpienia):
- „Michał to adwokat po mojej stronie"
- „Spółka X i Y mają tego samego właściciela"
- „Regulamin podlega prawu irlandzkiemu"

**Zdarzeniowy** — coś się wydarzyło w czasie (ma datę):
- „Michał zadzwonił do Y w sprawie ponaglenia"
- „Dzwonili do mnie z XYZ"
- „Recepcja potwierdziła, że przesyłka dotarła"

Kryterium: **czy zdarzenie miało miejsce w czasie?**
Jeśli nie jesteś pewny — zapytaj jednym zdaniem.

## 2. Jeśli KONTEKSTOWY

Potwierdź klasyfikację z użytkownikiem jednym zdaniem.
Dopisz do `index.md` sprawy, sekcja „Kontekst sprawy" (utwórz jeśli nie istnieje):

```markdown
## Kontekst sprawy
- [RRRR-MM-DD dodano] Michał Nowak (tel. XXX) — adwokat po stronie użytkownika. Kontakt: ...
```

Zakończ: „Zapisano jako fakt kontekstowy. Brak wpisu w chronologii."

## 3. Jeśli ZDARZENIOWY

### a) Zapytaj o datę (jeśli nie podano)
„Kiedy to się wydarzyło? Przybliżona data wystarczy."

### b) Zapytaj o dowód — podaj konkretne sugestie dobrane do opisu faktu

| Typ zdarzenia | Sugestie dowodów |
|---|---|
| Rozmowa telefoniczna | historia połączeń (zrzut), notatka sporządzona zaraz po, SMS nawiązujący do rozmowy |
| Kontakt e-mail | .eml z nagłówkami, autoresponder potwierdzający odbiór |
| Zmiana na stronie | zrzut ekranu przed/po, Wayback Machine snapshot |
| Spotkanie / wizyta | potwierdzenie mailowe, faktura, paragon, bilet |
| Płatność / obciążenie | wyciąg bankowy, potwierdzenie transakcji |
| Decyzja firmy | komunikat na stronie, odpowiedź pisemna, regulamin, e-mail |
| Rozmowa osobista | notatka sporządzona zaraz po z datą i miejscem |

Pytaj: „Czy masz coś, co to potwierdza? Na przykład: [sugestia]"

### c) Oznacz pewność

| Poziom | Kiedy |
|---|---|
| `dowód` | plik w archiwum sprawy |
| `poszlaka` | dowód pośredni (np. autoresponder potwierdzający kontakt, ale nie treść) |
| `własne_oświadczenie` | brak zewnętrznego potwierdzenia |

### d) Dopisz do chronologii `index.md`

```markdown
| RRRR-MM-DD | HH:MM (jeśli znane) | [Opis zdarzenia] | pewność: własne_oświadczenie — brak pliku |
```

Zachowaj porządek chronologiczny w tabeli.

### e) Dopisz do sekcji „Ustalenia" z flagą pewności

Dla `własne_oświadczenie`:
```markdown
- [RRRR-MM-DD] [Opis zdarzenia]. ⚠ pewność: własne_oświadczenie — do pisma tylko jako wniosek dowodowy.
```

Dla `poszlaka` lub `dowód` — bez ostrzeżenia.

### f) Jeśli użytkownik ma plik

Napisz: „Masz plik — wciągnij go przez `/kruczek:dowod <ścieżka> <katalog-sprawy>`."
Nie wciągaj pliku samodzielnie z tej komendy.

## 4. Blokada w kontrola

Fakty z pewnością `własne_oświadczenie` są blokowane przez `/kruczek:kontrola`, jeśli
pojawiają się w treści pisma **bez** oznaczenia `[wniosek dowodowy]`. To jest celowe —
nie obchodź tej blokady.

## 5. Zamelduj

Dwie linie: co zapisano, jaką pewnością oznaczono. Jeśli brakuje dowodu — powtórz
najlepszą sugestię.
