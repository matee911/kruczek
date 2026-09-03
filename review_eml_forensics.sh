#!/bin/bash
# review_eml_forensics.sh — uruchamia eml_forensics.py dla każdego .eml,
# potem spawnia Claude do weryfikacji poprawności raportu.
#
# Użycie:
#   ./review_eml_forensics.sh                 # wszystkie .eml w do_not_commit/
#   ./review_eml_forensics.sh a.eml b.eml     # tylko wskazane
#   ./review_eml_forensics.sh --brakujace     # tylko te, których ocena jest
#                                             # starsza niż raport albo pusta
#
# Zawężanie ma znaczenie kosztowe: każda ocena to osobne wywołanie płatnego
# modelu, więc powtarzanie ocen już aktualnych to czysta strata.
#
# ZACHOWANIE PRZY WYCZERPANYM LIMICIE
#   Skrypt PRZERYWA przebieg (kod wyjścia 2) zamiast lecieć dalej. Po limicie
#   każde kolejne wywołanie padnie tak samo, więc przelecenie do końca listy
#   pali czas i zostawia szesnaście identycznych ostrzeżeń zamiast jednego
#   zdania o tym, co się stało. Przy przerwaniu wypisuje, ile ocen zapisano,
#   ile zostało, i podpowiada ponowne uruchomienie z `--brakujace`.
#
#   Żadna istniejąca ocena nie jest wtedy nadpisywana — wynik trafia najpierw
#   do pliku tymczasowego. To nie jest ostrożność teoretyczna: w jednym
#   z wcześniejszych przebiegów `tee` nadpisał dwanaście dobrych ocen
#   stubajtowym komunikatem o limicie.

# Bez `set -e`: jeden plik, którego nie da się przetworzyć, nie może przerywać
# całego przebiegu. Wcześniej `set -e` w parze z wyciszonym stderr kończył skrypt
# po pierwszym błędzie i nie zostawiał ani jednego słowa wyjaśnienia.
set -uo pipefail

EML_DIR="do_not_commit"
FORENSICS_SCRIPT="scripts/eml_forensics.py"

# ROZPOZNAWANIE BŁĘDU — najpierw KSZTAŁT odpowiedzi, dopiero potem treść.
#
# Poprzednia wersja szukała słów w całym pliku i wzorzec zawierał gołe `429`.
# Raport oceniany w trzecim pliku zawierał liczbę `1429`; recenzja ją zacytowała
# i cały przebieg został przerwany komunikatem o wyczerpanym limicie przy 4%
# zużycia. Szukanie słów-kluczy w MATERIALE DOWODOWYM jest z zasady zawodne:
# recenzja może cytować dowolną liczbę i dowolny komunikat błędu z badanej
# wiadomości. Rozstrzyga więc to, czym odpowiedź JEST:
#
#   - ocena ma strukturę markdown (nagłówek `#` albo wiersz tabeli `|`)
#     i sensowną objętość,
#   - komunikat błędu CLI to kilkadziesiąt–kilkaset bajtów płaskiego tekstu.
#
# Wzorce służą już tylko do NAZWANIA przyczyny w komunikacie, nie do decyzji.

#: Minimalna objętość odpowiedzi, którą w ogóle rozważamy jako ocenę.
MIN_OCENA_BAJTOW=1000

#: Nazwanie przyczyny — stosowane wyłącznie do odpowiedzi już uznanej za błąd.
LIMIT_PATTERN='spend limit|credit balance|rate limit|usage limit|quota|insufficient|too many requests|overloaded|status code 429|http 429'
NETWORK_PATTERN='enotfound|econnrefused|etimedout|network error|connection (refused|reset)|unable to connect'

#: Ile ocen faktycznie zapisano w tym przebiegu — do komunikatu przy przerwaniu.
ZAPISANE=0

# `python` bywa nieobecny — pyenv wystawia shim tylko dla wersji, w których go
# zainstalowano, więc w powłoce bez aktywnego środowiska `python` kończy się
# błędem „command not found”. `python3` jest obecny zawsze.
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "❌ Nie znaleziono interpretera '$PYTHON'."
    echo "   Wskaż własny:  PYTHON=/ścieżka/do/python ./$(basename "$0")"
    exit 1
fi

# Skrypty używają składni PEP 695 (`type X = ...`) i `dataclass(slots=True)`,
# więc wymagają Pythona 3.12+. Na starszym interpreterze padają SyntaxError-em,
# który przy wyciszonym stderr wyglądał jak ciche zatrzymanie się skryptu.
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "❌ '$PYTHON' to $("$PYTHON" -V 2>&1) — potrzebny Python 3.12 lub nowszy."
    echo "   Wskaż inny:  PYTHON=/ścieżka/do/python3.12 ./$(basename "$0")"
    exit 1
fi

if [ ! -d "$EML_DIR" ]; then
    echo "❌ Katalog '$EML_DIR' nie istnieje."
    exit 1
fi

if [ ! -f "$FORENSICS_SCRIPT" ]; then
    echo "❌ Skrypt '$FORENSICS_SCRIPT' nie istnieje."
    exit 1
fi

PROMPT=$(cat <<'PROMPT_EOF'
przeczytaj plik .eml, zapoznaj sie z jego zawartoscia, naglowkami, faktami, a dopiero potem przeczytaj raport w pliku .md. Ocen poprawnosc raportu. Co jest w nim zle i mija sie w faktami. Czego w raportcie zabraklo. Skup sie na faktach i zbieraniu dowodow, a nie na ich ocenie i wyciaganiu wnioskow.
PROMPT_EOF
)

# Ustal listę plików do przetworzenia.
FILES=()
if [ "${1:-}" = "--brakujace" ]; then
    for f in "$EML_DIR"/*.eml; do
        [ -f "$f" ] || continue
        stem=$(basename "$f" .eml)
        review="$EML_DIR/${stem}_review.md"
        report="$EML_DIR/${stem}_analiza.md"
        # Aktualność liczymy po sumie kontrolnej ocenianego raportu, nie po mtime:
        # mtime kłamie po odtworzeniu pliku z kopii, a to właśnie wtedy najbardziej
        # zależy nam, żeby nie przeliczać ocen, które są dobre.
        if [ -s "$review" ] && [ -f "$report" ]; then
            want=$(shasum -a 256 "$report" | awk '{print $1}')
            have=$(sed -n 's/^<!-- oceniono raport sha256:\([0-9a-f]*\) -->$/\1/p' "$review" | tail -1)
            if [ "$want" = "$have" ]; then
                continue
            fi
        fi
        FILES+=("$f")
    done
    echo "🔎 Do przeliczenia: ${#FILES[@]} z $(ls -1 "$EML_DIR"/*.eml 2>/dev/null | wc -l | tr -d ' ')"
    echo ""
elif [ "$#" -gt 0 ]; then
    FILES=("$@")
else
    for f in "$EML_DIR"/*.eml; do
        [ -f "$f" ] && FILES+=("$f")
    done
fi

if [ "${#FILES[@]}" -eq 0 ]; then
    echo "✅ Nie ma czego przeliczać — wszystkie oceny są nowsze niż raporty."
    exit 0
fi

for eml_file in "${FILES[@]}"; do
    if [ ! -f "$eml_file" ]; then
        echo "⚠️  Pominięto (brak pliku): $eml_file"
        continue
    fi

    stem=$(basename "$eml_file" .eml)
    md_file="$EML_DIR/${stem}_analiza.md"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📄 Analizuję: $eml_file"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Uruchom eml_forensics.py. Stdout idzie do /dev/null (to sam raport, mamy go
    # w pliku), ale stderr NIE — bez tego błąd interpretera znikał bez śladu.
    if ! "$PYTHON" "$FORENSICS_SCRIPT" "$eml_file" --outdir "$EML_DIR" >/dev/null; then
        echo "⚠️  Nie udało się wygenerować raportu — pomijam ten plik."
        echo ""
        continue
    fi

    # Sprawdź czy raport powstał
    if [ ! -f "$md_file" ]; then
        echo "⚠️  Raport nie został utworzony: $md_file"
        continue
    fi

    echo "✅ Raport stworzony: $(basename "$md_file")"
    echo ""
    echo "🔍 Spawnianie Claude do weryfikacji..."
    echo ""

    # Spawni Claude z promptem, przepuszczając obie ścieżki do -p.
    # Wynik ląduje najpierw w pliku tymczasowym: `tee` prosto do docelowego
    # nadpisywał poprzednią, dobrą ocenę także wtedy, gdy CLI zwróciło samą
    # informację o błędzie (limit wydatków, brak sieci) — kasując materiał,
    # którego nie da się odtworzyć bez ponownego, płatnego przebiegu.
    review_file="$EML_DIR/${stem}_review.md"
    tmp_review="$(mktemp)"
    # Ścieżki MUSZĄ być w treści promptu. Przekazane jako argumenty pozycyjne po
    # `-p` nie docierają do modelu — recenzenci zgadywali plik po sumach kontrolnych
    # i kilkoro oceniło nie ten, który im podstawiono.
    full_prompt="${PROMPT}

Plik źródłowy: ${eml_file}
Raport do oceny: ${md_file}"
    claude -p "$full_prompt" --model claude-opus-5 --effort high | tee "$tmp_review"

    # Filtr musi łapać KAŻDĄ odpowiedź, która nie jest oceną. Pierwsza wersja
    # znała tylko komunikaty o limicie i przepuściła błędy sieciowe
    # (`API Error: Unable to connect to API (ENOTFOUND)`), nadpisując nimi
    # pięć dobrych ocen. Dlatego obok wzorców błędów sprawdzamy też długość:
    # ocena krótsza niż 1000 bajtów nie jest oceną.
    # Ocena to dokument markdown o sensownej objętości. Wszystko inne jest
    # błędem — niezależnie od tego, jakie słowa w sobie zawiera.
    rozmiar=$(wc -c <"$tmp_review" | tr -d ' ')
    powod=""
    if [ "$rozmiar" -lt "$MIN_OCENA_BAJTOW" ] ||
       ! grep -qE '^[[:space:]]*(#|\|)' "$tmp_review"; then
        # Dopiero teraz wzorce — wyłącznie po to, żeby nazwać przyczynę.
        if grep -qiE "$LIMIT_PATTERN" "$tmp_review"; then
            powod="limit"
        elif grep -qiE "$NETWORK_PATTERN" "$tmp_review"; then
            powod="siec"
        else
            powod="pusto"
        fi
    fi

    if [ -n "$powod" ]; then
        # PRZERYWAMY, nie pomijamy. Po wyczerpaniu limitu każde kolejne
        # wywołanie padnie tak samo — przelecenie do końca listy pali czas
        # i zaśmieca wynik szesnastoma identycznymi ostrzeżeniami, zamiast
        # jednym zdaniem o tym, co się stało i co zrobić dalej.
        echo ""
        podpowiedz_czekaj="za jakiś czas"
        case "$powod" in
            limit)
                echo "🛑 STOP: CLI zgłosiło wyczerpany limit."
                podpowiedz_czekaj="gdy limit się odnowi (zwykle kilka godzin)"
                ;;
            siec)
                echo "🛑 STOP: CLI nie mogło połączyć się z API."
                podpowiedz_czekaj="gdy wróci połączenie"
                ;;
            pusto)
                echo "🛑 STOP: CLI zwróciło odpowiedź, która nie jest oceną."
                echo "    Rozmiar: ${rozmiar} B. Pierwsze 200 znaków:"
                echo ""
                head -c 200 "$tmp_review" | sed 's/^/      /'
                echo ""
                ;;
        esac
        echo ""
        echo "    Plik przerwany:      $(basename "$eml_file")"
        echo "    Ocen zapisanych:     $ZAPISANE"
        echo "    Zostało do zrobienia: $((${#FILES[@]} - ZAPISANE))"
        echo ""
        echo "    Poprzednia wersja oceny NIE została nadpisana."
        echo ""
        echo "    Uruchom ponownie ${podpowiedz_czekaj}:"
        echo ""
        echo "        ./$(basename "$0") --brakujace"
        echo ""
        echo "    Flaga --brakujace pomija pliki, które mają już aktualną ocenę"
        echo "    (sprawdzane po sumie kontrolnej raportu), więc nie zapłacisz"
        echo "    drugi raz za to, co już się udało."
        rm -f "$tmp_review"
        exit 2
    fi

    mv "$tmp_review" "$review_file"
    ZAPISANE=$((ZAPISANE + 1))
    # Znacznik wiąże ocenę z konkretną wersją raportu — bez niego nie da się
    # odróżnić oceny aktualnej od takiej, która opisuje kod sprzed poprawek.
    printf '\n<!-- oceniono raport sha256:%s -->\n' \
        "$(shasum -a 256 "$md_file" | awk '{print $1}')" >> "$review_file"

    echo ""
    echo "📝 Ocena zapisana: $(basename "$review_file")"
    echo ""
done

echo ""
echo "✅ Koniec — ocen zapisanych: $ZAPISANE z ${#FILES[@]}"
