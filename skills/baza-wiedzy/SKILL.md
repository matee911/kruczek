---
name: baza-wiedzy
description: Dopisuje zweryfikowany przepis, orzeczenie lub decyzję organu do BAZY WIEDZY, żeby nie szukać tego samego w internecie przy każdej sprawie. Użyj po każdym researchu prawnym.
argument-hint: "[czego dotyczy]"
disable-model-invocation: true
model: sonnet
effort: medium
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(date *) Read Write Edit
---

# Dopisanie do bazy wiedzy

Temat: `$ARGUMENTS`

Baza wiedzy ma jeden cel: **nie szukać dwa razy tego samego**. Wszystko, co zweryfikowałeś
w źródle urzędowym, ma tu wylądować w formie gotowej do wklejenia do pisma.

## 1. Sprawdź, czy tego już nie ma

Przejrzyj `BAZA_WIEDZY/index.md` i pliki w `przepisy/`, `orzecznictwo/`, `decyzje/`.
Jeśli wpis istnieje — **zaktualizuj go**, nie twórz drugiego.

**Zawsze weryfikuj aktualność, nawet gdy plik już jest:**
- Sprawdź pole `Publikator` — czy to tekst jednolity (`t.j. Dz.U. z … poz. …`), czy pierwotny
  (sam rok uchwalenia). Tekst pierwotny/ogłoszony bez oznaczenia t.j. jest **niezdatny do cytowania**.
- `eli.sh obowiazuje DU <rok> <poz>` — status + czy istnieje nowszy tekst jednolity
- `eli.sh referencje` — nowelizacje po dacie tekstu jednolitego

Jeśli plik w bazie ma tekst ogłoszony zamiast jednolitego — oznacz go `⚠ NIEAKTUALNY — tekst ogłoszony,
nie cytować` i pobierz właściwy tekst jednolity zanim zaczniesz analizę.

## 2. Nazwij plik

- `przepisy/<SKRÓT-USTAWY>_art-<numery>.md` — np. `PKE_art-398_446_448.md`
- `orzecznictwo/<temat>.md` — jeden plik na zagadnienie, nie na orzeczenie
- `decyzje/<organ>_<temat>.md`
- `metodyka/<temat>.md` — sposoby postępowania, katalogi technik, checklisty
- `wzory/<rodzaj-pisma>.md` — sprawdzone sformułowania

## 3. Struktura pliku z przepisami

```markdown
# <Nazwa ustawy> — <czego dotyczą przepisy>

- **Akt:** <pełna nazwa z datą>
- **Publikator:** t.j. Dz. U. z <rok> r. poz. <poz> ← ZAWSZE tekst jednolity; jeśli nie istnieje, podaj ogłoszony + oznacz ⚠ NIEAKTUALNY
- **Status:** obowiązujący / uchylony od <data> przez <akt>
- **Źródło:** <URL do api.sejm.gov.pl / EUR-Lex>
- **Zweryfikowano:** <RRRR-MM-DD>

## Art. N — <tytuł jednostki>

> <DOSŁOWNY cytat, wszystkie ustępy>

### Wnioski praktyczne
1. <co z tego wynika w sporze — konkretnie, nie ogólnikowo>
2. <na kim spoczywa ciężar dowodu>
3. <czym się różni od poprzedniego stanu prawnego, jeśli był>

### ⚠ Pułapki
- <częsty błąd w cytowaniu tego przepisu>
```

## 4. Struktura pliku z orzecznictwem

Dla każdej pozycji: **sąd, data, sygnatura**, dosłowny cytat tezy, URL źródła, jedno zdanie
o tym, do czego się przydaje. Rozbieżne linie orzecznicze opisuj uczciwie — „ZA" i „PRZECIW"
w osobnych sekcjach, plus akapit **🔑 STRATEGIA**, na czym opierać sprawę wobec tej rozbieżności.

## 5. Oznacz to, czego nie potwierdziłeś

Wszystko bez potwierdzenia w źródle urzędowym → `⚠ NIEPOTWIERDZONE` plus wskazanie, gdzie
szukać dalej. Na końcu pliku sekcja „Luki do uzupełnienia".

Zasada bezwzględna: **pozycji oznaczonej ⚠ nie wolno cytować w piśmie.** Napisz to w pliku.

## 6. Zaktualizuj indeks

Dopisz wiersz do tabeli w `BAZA_WIEDZY/index.md`: nazwa pliku + zakres. Jeśli ustaliłeś coś,
co zmienia sposób prowadzenia wszystkich spraw danego typu (np. że kluczowy przepis został
uchylony) — wypisz to na górze `index.md` jako ostrzeżenie, nie chowaj w tabeli.

## 7. Nie kopiuj internetu

Do bazy trafiają: dosłowne cytaty aktów, tezy orzeczeń z sygnaturami, własne wnioski praktyczne.
**Nie** trafiają: przepisane artykuły z blogów kancelarii, streszczenia bez sygnatur, „ogólnie
przyjmuje się, że…". Jeśli coś znasz tylko z opracowania — zaznacz to i podlinkuj, ale oznacz ⚠.
