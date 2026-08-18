---
name: gmail
description: Generuje gotowe zapytania Gmail i filtry dla sprawy — filtr główny, filtr autoresponderów (dowody doręczenia), zapytania do dowodu negatywnego (4 niezależne). Wywoływany automatycznie przez /kruczek:nowa-sprawa i /kruczek:dowod przy .eml. Użyj ręcznie gdy pojawiają się nowe domeny lub adresy w sprawie.
argument-hint: "[sprawa] [domeny lub adresy oddzielone spacją]"
disable-model-invocation: true
model: sonnet
effort: low
allowed-tools: Read Write Edit
---

# Generator zapytań Gmail i filtrów dla sprawy

Argumenty: `$ARGUMENTS`

Odczytaj z `index.md` sprawy:
- Wszystkie domeny i adresy e-mail drugiej strony (z sekcji „Ustalenia" i danych rejestrowych)
- Nazwę sprawy (do etykiety)
- Datę kluczowego zdarzenia (do zapytań z oknem czasowym)

Wygeneruj poniższy zestaw. Wypisz go w bloku kodu, gotowy do skopiowania.

## Filtry Gmail — założyć raz przy nowej sprawie

```
=== FILTR 1: Cała korespondencja ze sprawą (etykieta + nigdy-spam + zawsze-ważne) ===
Zapytanie:
  from:(*@domena.pl OR *@serwis.domena.pl) OR to:(*@domena.pl)

Akcje:
  ✓ Zastosuj etykietę: Sprawa/[NAZWA-SPRAWY]
  ✓ Nigdy nie wysyłaj do spamu
  ✓ Zawsze oznaczaj jako ważne


=== FILTR 2: Autorespondery i potwierdzenia (to są dowody doręczenia) ===
Zapytanie:
  from:(*@domena.pl) subject:(zgłoszenie OR rejestracja OR "przyjęte" OR "potwierdzamy" OR "numer zgłoszenia" OR "ticket")

Akcje:
  ✓ Zastosuj etykietę: Sprawa/[NAZWA-SPRAWY]/Potwierdzenia
  ✓ Nigdy nie wysyłaj do spamu
```

## Zapytania startowe — uruchomić od razu i sprawdzić wyniki

```
=== ZAPYTANIE 1: Cała historyczna korespondencja (łącznie ze spamem i koszem) ===
in:anywhere (from:(*@domena.pl) OR to:(*@domena.pl))

=== ZAPYTANIE 2: Odbicia i raporty niedoręczenia ===
in:anywhere from:(mailer-daemon OR postmaster OR no-reply) subject:(undeliverable OR "delivery status" OR "nie dostarczono" OR failure OR "550")

=== ZAPYTANIE 3: Kody SMTP w treści ===
in:anywhere ("550 5.1.10" OR "550 5.0.1" OR RecipientNotFound OR "Recipient rejected")

=== ZAPYTANIE 4: Korespondencja w oknie czasowym zdarzenia ===
in:anywhere ([NAZWA-PODMIOTU] OR @domena.pl) after:[RRRR/MM/DD-7dni] before:[RRRR/MM/DD+14dni]

=== ZAPYTANIE 5: Tylko z załącznikami (faktury, potwierdzenia, decyzje) ===
in:anywhere from:*@domena.pl has:attachment

=== ZAPYTANIE 6: Wiadomości po Message-ID (gdy znasz ID z nagłówka) ===
rfc822msgid:[WPISZ-MESSAGE-ID-Z-NAGLOWKA]
```

## Dowód negatywny — 4 niezależne zapytania (zrzut każdego z "brak wyników")

Zrób zrzut ekranu każdego zapytania z widocznym paskiem wyszukiwania i komunikatem "brak wyników".
Cztery niezależne zapytania zamiast jednego — żeby nie dało się podważyć doboru frazy.

```
DOWÓD NEGATYWNY 1:
from:mailer-daemon in:anywhere after:[DATA-ZDARZENIA] before:[DATA+7DNI]

DOWÓD NEGATYWNY 2:
from:postmaster in:anywhere after:[DATA-ZDARZENIA] before:[DATA+7DNI]

DOWÓD NEGATYWNY 3:
subject:("Delivery Status Notification" OR "Undelivered" OR "Niedostarczono") in:anywhere after:[DATA-ZDARZENIA] before:[DATA+7DNI]

DOWÓD NEGATYWNY 4:
([NAZWA-PODMIOTU] OR [DOMENA]) in:anywhere after:[DATA-ZDARZENIA] before:[DATA+7DNI]
```

## Operatory kluczowe — pamiętaj

- `in:anywhere` — **obowiązkowo** (bounce'y i powiadomienia lądują w spamie)
- `deliveredto:matee@matee.net OR deliveredto:foto@matee.net` — **po każdym własnym adresie i aliasie** (wiadomość mogła wyjść z jednego adresu, a odbicie wrócić na inny)
- `rfc822msgid:` — odtworzenie konkretnej wiadomości po Message-ID z nagłówka

## Eksport dowodów

- Każda wiadomość dowodowa: Gmail → Więcej → Pobierz wiadomość → `.eml` (pełne nagłówki)
- Cała etykieta sprawy: Google Takeout → wybierz etykietę → format `.mbox`
- Nie drukuj do PDF bez nagłówków — PDF z klienta poczty traci Received i DKIM-Signature
