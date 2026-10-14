# subskrypcje

Program czyta wyciąg bankowy w CSV, wykrywa subskrypcje i pokazuje ich koszt miesięczny i roczny.

## Uruchomienie
```
uv run subskrypcje data/wyciag-przyklad.csv
uv run subskrypcje data/wyciag-przyklad.csv --log-format json --log-level WARNING
```
Raport trafia na stdout w UTF-8, logi na stderr.

## Testy i lint
```
uv run pytest
uv run ruff format .
uv run ruff check .
```
