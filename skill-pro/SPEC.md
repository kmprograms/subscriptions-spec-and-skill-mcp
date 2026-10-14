# Specyfikacja: subskrypcje

## Problem
Płatności cykliczne (streaming, siłownia, chmura) łatwo przeoczyć na wyciągu bankowym.
Program czyta wyciąg w CSV, wykrywa subskrypcje i pokazuje ich koszt miesięczny i roczny.

## Zakres
- Nazwa projektu i pakietu: `subskrypcje`.
- Aplikacja CLI z jednym poleceniem. Bez bazy danych i bez sieci.
- Poza zakresem: inne formaty plików, waluty inne niż PLN, kategorie wydatków, GUI.

## Uruchomienie
```
uv run subskrypcje <plik.csv> [--log-format console|json] [--log-level DEBUG|INFO|WARNING]
```
Domyślnie: `--log-format console`, `--log-level INFO`.

## Wejście: plik CSV
- Kodowanie UTF-8, separator `;`, pierwszy wiersz to nagłówek `data;kontrahent;tytul;kwota`.
- `data` w formacie RRRR-MM-DD.
- Wiersze są ułożone od najnowszych, jak w historii rachunku. Program nie zakłada żadnej kolejności wierszy.
- `kwota` z przecinkiem dziesiętnym, minus oznacza wydatek, np. `-49,99`. Spacje w kwocie ignoruj (`-1 299,00`).
- Wiersz z błędną datą lub kwotą: pomiń, zaloguj ostrzeżenie `row_skipped` z numerem linii pliku i przyczyną, przetwarzaj dalej. Nagłówek to linia 1.
  Przyczyna: `invalid_date` albo `invalid_amount`. Najpierw sprawdzaj datę, potem kwotę.
- Brak pliku: zaloguj błąd `statement_not_found` z polem `path`, zakończ z kodem wyjścia 1, bez tracebacka.
- Przykładowe dane: `data/wyciag-przyklad.csv`. Plik jest gotowy, nie zmieniaj go.

## Reguły wykrywania
- R1. Uwzględniaj tylko wydatki (kwota < 0).
- R2. Klucz kontrahenta: usuń cyfry, zamień ciągi białych znaków na jedną spację, obetnij spacje z brzegów, zamień na wielkie litery. Przykład: `"Netflix.com 4829"` -> `"NETFLIX.COM"`. Klucz jest też nazwą w raporcie.
- R3. Grupuj wydatki po kluczu kontrahenta.
- R4. Grupa jest subskrypcją, gdy spełnia wszystkie warunki:
  - a) ma co najmniej 3 płatności,
  - b) każdy odstęp między kolejnymi płatnościami (po sortowaniu po dacie) wynosi od 25 do 35 dni włącznie,
  - c) każda kwota (wartość bezwzględna) mieści się w przedziale ±20% od mediany kwot grupy, granice włącznie.
- R5. Koszt miesięczny to wartość bezwzględna najpóźniejszej płatności (według daty). Koszt roczny = koszt miesięczny × 12.
- R6. Gdy kwota najpóźniejszej płatności różni się od kwoty najwcześniejszej, raport pokazuje zmianę ceny: `najwcześniejsza -> najpóźniejsza`.
- R7. Kolejność: koszt roczny malejąco, przy remisie nazwa rosnąco.

## Wyjście (stdout)
Kwoty: dwa miejsca po przecinku, przecinek dziesiętny, bez separatora tysięcy. Szerokość kolumn dowolna.
```
Wykryte subskrypcje: 4
CITYFIT SP. Z O.O.       139,00 zł/mies.   1668,00 zł/rok
NETFLIX.COM               49,00 zł/mies.    588,00 zł/rok
SPOTIFY AB STOCKHOLM      26,99 zł/mies.    323,88 zł/rok   zmiana ceny: 23,99 -> 26,99
APPLE.COM/BILL             4,99 zł/mies.     59,88 zł/rok
Razem: 219,98 zł/mies., 2639,76 zł/rok
```
Gdy nie ma subskrypcji: `Nie wykryto subskrypcji.`

## Logi (stderr)
- `statement_loaded` (INFO): `rows_loaded`, `rows_skipped`.
- `row_skipped` (WARNING): `line`, `reason` (`invalid_date` albo `invalid_amount`).
- `subscriptions_detected` (INFO): `count`.
- `statement_not_found` (ERROR): `path`.
- Logi nie zawierają nazw kontrahentów, tytułów ani kwot.

## Kryteria akceptacji
- K1. `uv run subskrypcje data/wyciag-przyklad.csv` wypisuje dokładnie 4 subskrypcje w kolejności: CITYFIT SP. Z O.O., NETFLIX.COM, SPOTIFY AB STOCKHOLM, APPLE.COM/BILL.
- K2. Ostatnia linia raportu: `Razem: 219,98 zł/mies., 2639,76 zł/rok`.
- K3. Tylko SPOTIFY AB STOCKHOLM ma zmianę ceny `23,99 -> 26,99`.
- K4. Subskrypcjami nie są: wynagrodzenie (R1), ORLEN STACJA NR (R4c), BIEDRONKA KRAKOW (R4b i R4c), ALLEGRO.PL (R4a, R4b i R4c), MEDIA EXPERT (R4a), TAURON SPRZEDAZ (R4b).
- K5. Na stderr są 2 ostrzeżenia `row_skipped` (`line=14`, `reason=invalid_amount` oraz `line=30`, `reason=invalid_date`) oraz `statement_loaded` z `rows_loaded=55`, `rows_skipped=2`.
- K6. Z `--log-format json` każda linia stderr to poprawny JSON z polami `event`, `level`, `timestamp`, `run_id`.
- K7. Stdout zawiera tylko raport. Po przekierowaniu stderr do null nie widać żadnego logu.
- K8. `uv run pytest` przechodzi. `uv run ruff check .` nie zgłasza błędów.
- K9. Nieistniejący plik: kod wyjścia 1, pusty stdout, na stderr dokładnie jedna linia (`statement_not_found`), bez tracebacka.
