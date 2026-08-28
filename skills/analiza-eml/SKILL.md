---
name: analiza-eml
description: Analiza wiadomości e-mail (.eml) pod kątem dowodowym — droga wiadomości, uwierzytelnienie SPF/DKIM, rotacja domen, sfingowany wątek, tokeny śledzące i techniki obchodzenia filtrów antyspamowych. Użyj przy każdym pliku .eml i przy sprawach o spam lub marketing bez zgody.
when_to_use: Plik .eml w sprawie, spam, niezamówiona informacja handlowa, marketing bez zgody, nagłówki maila, kto naprawdę wysłał wiadomość, czy mail jest podszyciem.
model: haiku
effort: low
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eml_forensics.py *)
---

# Analiza dowodowa wiadomości e-mail

Robotę wykonuje skrypt. Twoim zadaniem jest go uruchomić i opisać wynik — nie liczyć niczego ręcznie.

```
${CLAUDE_PLUGIN_ROOT}/scripts/eml_forensics.py <plik.eml> --outdir <sprawa>/ARCHIWUM
```

Skrypt zapisuje obok oryginału: `_naglowki.txt`, `_tresc.html`, `_analiza.md` (gotowy raport
markdown nadający się na załącznik do pisma) i wypisuje sumy kontrolne wszystkiego.

## Co skrypt wykrywa i co to znaczy

**Droga wiadomości** — nagłówki `Received` od najstarszego. Pokazują, z jakiego komputera i łącza
nadano wiadomość. Nazwa hosta typu `user-…play-internet.pl` wskazuje na wysyłkę z domowego lub
mobilnego łącza, a nie z infrastruktury dostawcy usług mailingowych. Wiarygodny dowodowo jest
tylko nagłówek `Received` dodany przez serwer odbiorczy — wcześniejsze da się sfałszować.

**Uwierzytelnienie** — `dkim=pass` i `spf=pass` potwierdzają, że wiadomość wyszła z infrastruktury
autoryzowanej przez domenę z `d=…`. Sprawdź, czy ta domena odpowiada domenie z `From` — jeśli tak,
osłabia to linię obrony „ktoś podszył się pod naszą firmę". Nie wyklucza to jednak wysyłki
z przejętego konta ani z domeny łudząco podobnej.

**Rozbieżność domen** — inna domena w `From`, inna w `Reply-To`, jeszcze inna w linku. Typowa
rotacja domen służąca omijaniu list blokujących. Sprawdź daty rejestracji domen
(`podmiot.sh domena <domena>`) — domena zarejestrowana kilka dni przed wysyłką to poszlaka,
mocna dopiero w zestawieniu z pozostałymi ustaleniami.

**Sfingowany wątek** — temat z prefiksem „Re:" przy braku nagłówków `In-Reply-To` i `References`.
Oznacza brak technicznego powiązania z wcześniejszą korespondencją; „Re:" bywa też wpisane ręcznie
albo zgubione przez klienta pocztowego. Jeśli użytkownik potwierdza, że wątku nie było — to
poszlaka sfingowania.

**Tokeny śledzące** — zakodowany w Base64 adres odbiorcy w parametrze URL. Dowodzi, że wysyłka
była **spersonalizowana per odbiorca**, i wskazuje, że nadawca dysponował adresem w formie
umożliwiającej powiązanie wejścia na stronę z konkretną osobą. Ma to znaczenie dla kwalifikacji
adresu jako danej osobowej.

**Techniki obchodzenia filtrów** — skrypt liczy: komentarze HTML wewnątrz wyrazów, znaki zerowej
szerokości (U+200B/C/D, U+FEFF), numeryczne encje HTML zamiast liter, puste znaczniki `<span>`
rozbijające słowa, tekst biały na białym (hash busting), elementy ukryte CSS-em.

**Dlaczego to jest ważne dowodowo:** żadna z tych technik nie powstaje samoczynnie w programie
pocztowym — każda wymaga ingerencji w kod HTML. Ich współwystępowanie jest **okolicznością
obciążającą przy ocenie umyślności**, ale nie dowodzi jej samo w sobie: część z nich (znaki
zerowej szerokości, elementy ukryte CSS-em w preheaderze) wstawiają rutynowo szablony i systemy
mailingowe, bez wiedzy nadawcy. Umyślność wykazuje dopiero zestawienie z innymi okolicznościami
— powtarzalnością wysyłek mimo sprzeciwu, rotacją domen.

## Granica, której nie przekraczasz

Ustalenia techniczne z nagłówków to **poszlaki, nie dowody zamiaru**. Opisuj co skrypt zmierzył
(„nagłówek zawiera X", „wykryto N znaków zerowej szerokości"), nie co z tego wynika o stanie
świadomości nadawcy. Wnioski o umyślności, prowadzeniu bazy adresowej czy sfingowaniu wątku
wchodzą do pisma wyłącznie jako zestawienie kilku ustaleń albo jako żądanie wyjaśnienia —
nigdy jako samodzielne twierdzenie.

Powtarzalność wzorca w wielu wiadomościach wzmacnia pozostałe ustalenia, ale nie jest
samodzielnym dowodem — zestaw ją z nimi, nie przedstawiaj osobno.

## Po analizie

1. Wynik `_analiza.md` dołącz do pisma jako załącznik (`build_pismo.py -z`).
2. Sprawdź domeny w RDAP i zapisz łańcuch przekierowań (`podmiot.sh domena` / `podmiot.sh strona`)
   — przekierowanie może zniknąć, więc trzeba je udokumentować teraz.
3. Zaktualizuj manifest i chronologię (`/kruczek:dowod` robi to za ciebie).
4. Kwalifikację prawną prowadź osobno — sprawdź `BAZA_WIEDZY/przepisy/`, a jeśli pusto,
   zbierz podstawy przez `zrodla-prawa`. **Nie cytuj przepisów z pamięci** — przepisy o spamie
   w Polsce zmieniły się w listopadzie 2024 r. i większość poradników w internecie jest nieaktualna.

## Delegowanie

Przy wielu wiadomościach naraz zleć subagentowi `analizuj-eml` (haiku) — to praca mechaniczna,
skrypt liczy, agent tylko zestawia wyniki.
