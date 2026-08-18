---
name: eskalacja
description: Planuje kolejne kroki po bezskutecznym upływie terminu — który organ, jaki tryb, jaki koszt, jakie szanse, w jakiej kolejności. Użyj, gdy przeciwnik milczy, odmówił albo termin właśnie minął.
argument-hint: "[katalog sprawy]"
disable-model-invocation: true
model: opus
effort: high
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/eli.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/orzecznictwo.sh *) Bash(date *) Read Write Edit
---

# Plan eskalacji

Sprawa: `$ARGUMENTS`

## 1. Ustal, gdzie naprawdę jesteśmy

Z `index.md`: co wysłano, kiedy doręczono, jaki był termin, czy minął, co odpowiedziano.
Sprawdź dzisiejszą datę (`date +%F`) i policz. Jeśli termin **jeszcze nie minął** — powiedz to
i nie planuj eskalacji na zapas.

Jeśli przeciwnik odpowiedział — przeczytaj odpowiedź. Odmowa merytoryczna, milczenie i odpowiedź
wymijająca prowadzą do różnych ścieżek.

## 2. Dobierz ścieżki — równolegle, nie sekwencyjnie

Wypisz **wszystkie** dostępne tryby, bo zwykle nie wykluczają się nawzajem. Dla każdego ustal:
kto jest właściwy, jaka podstawa prawna, jaki termin na wniesienie, ile kosztuje, co realnie
daje i czego **nie** daje.

Typowe tryby w polskich sprawach z organizacjami:

| Ścieżka | Kiedy ma sens | Uwaga |
|---|---|---|
| Skarga do organu nadzoru branżowego | jest wyspecjalizowany regulator | tani, ale organ nie zasądzi pieniędzy |
| Skarga do Prezesa UODO | naruszenie ochrony danych | długi czas oczekiwania |
| Zawiadomienie do UOKiK | praktyka naruszająca zbiorowe interesy konsumentów | UOKiK nie prowadzi sprawy indywidualnej |
| Rzecznik Konsumentów (powiatowy/miejski) | konsument, spór z przedsiębiorcą | bezpłatny, realnie pomaga w mediacji |
| Rzecznik Finansowy | banki, ubezpieczenia | wniosek o interwencję |
| Polubowne rozwiązywanie sporów (ADR) | przedsiębiorca przystąpił do systemu | szybsze niż sąd |
| Pozew cywilny / EPU | chodzi o pieniądze albo o zaniechanie | tu zapada wiążące rozstrzygnięcie |
| Zawiadomienie o wykroczeniu / przestępstwie | czyn zabroniony | sprawdź, czy tryb wnioskowy |
| Zgłoszenie do usługodawcy pośredniczącego | hosting, domena, platforma | najszybszy efekt praktyczny |

**Zweryfikuj podstawy prawne w źródłach** (`eli.sh obowiazuje`) — właściwość organów i tryby
zmieniają się wraz z nowelizacjami. Nie powtarzaj układu z poprzedniej sprawy bez sprawdzenia.

## 3. Oceń uczciwie

Dla każdej ścieżki podaj, **czego nie osiągnie**. Skarga do organu nie zwróci pieniędzy. Kara
administracyjna trafia do budżetu państwa, nie do poszkodowanego. Postępowanie potrafi trwać
dwa lata. Użytkownik ma prawo wiedzieć, w co wchodzi, zanim wejdzie.

Powiedz też wprost, kiedy **nie warto** — gdy koszt i czas przewyższają stawkę, a jedyną korzyścią
jest satysfakcja. To jest uczciwa odpowiedź, nie porażka.

Nie jesteś prawnikiem i tego nie ukrywaj: przy sprawach o wysokiej stawce, skomplikowanym stanie
faktycznym albo krótkim terminie zawitym — powiedz, że warto skonsultować się z radcą prawnym
lub adwokatem, i wskaż konkretnie dlaczego akurat tutaj.

## 4. Ułóż kolejność

Rekomendacja to **jedna** ścieżka jako następny krok plus uzasadnienie, dlaczego ta pierwsza.
Zwykle: najpierw tanie i szybkie, równolegle to, co ma krótki termin na wniesienie, na końcu sąd.
Pilnuj terminów zawitych — one nie czekają na resztę planu.

## 5. Zapisz w teczce

Uzupełnij sekcję „6. Ścieżka eskalacji" w `index.md`, dopisz terminy do chronologii jako przyszłe
wiersze, dopisz zadania do TODO. Zaproponuj `/kruczek:pismo` dla pierwszego kroku.
