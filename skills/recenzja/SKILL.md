---
name: recenzja
description: "Recenzja gotowego pisma i załączników przed wysyłką — czy wszystko zgadza się z faktami, dowodami i prawem, czy nie ma literówek i błędów językowych, czy nie ma twierdzeń kontrowersyjnych lub niepewnych, i czy pismo ma maksymalny możliwy wpływ. Ostatni krok przed nadaniem."
argument-hint: "[katalog wysyłki lub pismo.pdf]"
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/kontrola-pisma.py *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/manifest.py *) Bash(pdftotext *) Read Grep Glob
---

# Recenzja pisma przed wysyłką

Cel: `$ARGUMENTS`

Jesteś ostatnią bramką. Po tobie pismo idzie do drugiej strony i nie da się go cofnąć.
Pracujesz **przeciwko** pismu: szukasz tego, co druga strona wykorzysta.

Najpierw upewnij się, że przeszła kontrola mechaniczna (`/kruczek:kontrola`) — bez tego nie ma
po co recenzować.

Zleć równolegle:
- `weryfikuj-cytaty` — przepisy, sygnatury, daty, sumy, hipotezy w `index.md`
- `recenzuj` — fakty kontra dowody, ryzyko dla nadawcy, język, siła argumentacji

Zsyntetyzuj wyniki w jeden raport poniższym formatem.

## Raport

**🔴 BLOKUJE WYSYŁKĘ** — fakt bez pokrycia w dowodzie, hipoteza w trybie oznajmującym, uchylony
przepis, niepotwierdzona sygnatura, twierdzenie, które może zaszkodzić nadawcy, błąd w danych
adresata. Przy każdym: co jest źle, gdzie dokładnie, i propozycja poprawki.

**🟠 OSŁABIA** — argument zapraszający kontrargument, żądanie bez terminu, groźba niewykonalna,
niezręczność językowa, zła kolejność argumentów.

**🟡 LINIA OBRONY ADRESATA** — co zaneguje, co przemilczy, co obróci przeciwko nadawcy;
luki dowodowe; możliwe zarzuty procesowe. Krótka rekomendacja przy każdym.

**🟢 DO ROZWAŻENIA** — co jeszcze wzmocniłoby pismo, gdyby użytkownik chciał je jeszcze poprawić.

**Werdykt** — jedno zdanie: gotowe do wysyłki albo nie, i dlaczego.

Jeśli nie ma nic w 🔴, powiedz to wprost. **Nie dorabiaj zastrzeżeń, żeby raport wyglądał na
pracowity** — fałszywy alarm kosztuje tyle samo zaufania co przeoczenie.
