---
name: podsumowanie
description: Generuje podsumowanie sprawy w prostym języku — TL;DR na górze, co wiemy na pewno (z dowodem), czego brakuje (z konkretną sugestią jak zdobyć), ocena pozycji negocjacyjnej (mocne/słabe/ryzyko) i jeden następny krok. Dla osoby prowadzącej sprawę, nie dla adresata pisma. Użyj w dowolnym momencie sprawy.
argument-hint: "[katalog sprawy]"
disable-model-invocation: true
model: opus
effort: medium
allowed-tools: Read Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(ls *) Bash(date *) Write
---

# Podsumowanie sprawy

Sprawa: `$ARGUMENTS`

Wczytaj `index.md` i przejrzyj `ARCHIWUM/` (nazwy plików i opisy z manifestu — nie czytaj
treści każdego dowodu). Odróżniaj fakty z pewnością `dowód` od `własne_oświadczenie` i hipotez.

Następnie wygeneruj dokument według poniższej struktury. Pisz dla osoby, która nie zna prawa —
zero żargonu, zero artykułów, zero skrótów bez wyjaśnienia. Jeśli coś jest złe — napisz to wprost.

---

## Struktura wyjściowa

```markdown
# Podsumowanie sprawy: [Nazwa podmiotu]
_Wygenerowano: RRRR-MM-DD_

---

## TL;DR
[2–3 zdania: co się wydarzyło prostymi słowami, gdzie jesteśmy, jaki jest najbliższy krok]

---

## Co wiemy na pewno
[Tylko fakty potwierdzone plikiem w archiwum — bez własnych oświadczeń, bez hipotez]

- [Opis faktu] _(dowód: nazwa_pliku.pdf)_
- ...

Jeśli archiwum jest puste lub zawiera tylko własne oświadczenia: „Na razie nie mamy
żadnego dokumentu od drugiej strony ani z zewnętrznego źródła."

---

## Czego brakuje — i jak to zdobyć

[Każdy brak = konkretny brakujący dowód + konkretna sugestia, nie ogólna rada]

| Brakuje | Jak to zdobyć |
|---|---|
| Potwierdzenie doręczenia pierwszego pisma | Sprawdź autoresponder w Gmail: `in:anywhere from:*@domena.pl subject:(zgłoszenie OR przyjęte)` |
| Historia zmian regulaminu | `/kruczek:archiwa diff https://serwis.pl/regulamin` |
| Dane rejestrowe spółki | `/kruczek:nowa-sprawa` → podmiot.sh pobierze z KRS automatycznie |
| Poprzednia wersja OWU | Wayback CDX: `/kruczek:archiwa https://serwis.pl/owu` |
| [inny brak] | [konkretna czynność lub komenda] |

---

## Jak stoimy

🟢 **Na naszą korzyść:**
- [konkretny mocny punkt — co mamy dobrze udokumentowane]

🟡 **Słabe miejsca:**
- [gdzie jesteśmy narażeni na kontrargument i dlaczego]

🔴 **Ryzyko:**
- [co może wywrócić całą sprawę — brak kluczowego dowodu, hipoteza w piśmie, upływający termin]

---

## Następny krok

**[Jedna konkretna czynność]** — [dlaczego akurat to, a nie coś innego]

Komenda: `/kruczek:[nazwa]` albo: [opis ręcznej czynności]

---

_Podsumowanie wygenerowane przez kruczek. Nie zastępuje porady prawnika.
Przy stawce powyżej kilku tysięcy złotych lub przy sprawach z urzędami —
skonsultuj kluczowe tezy z radcą prawnym lub adwokatem._
```

---

## Po wygenerowaniu

Zapisz jako: `<katalog-sprawy>/ROBOCZE/podsumowanie-RRRR-MM-DD.md`

Ten plik jest **tylko dla użytkownika** — nie dołącza się go do pism, nie wysyła.
