---
name: python-hex-projekt
description: Zakłada nowy projekt w Pythonie według firmowego standardu (uv, architektura heksagonalna, structlog, pytest, ruff) i implementuje w nim aplikację opisaną w pliku specyfikacji. Użyj, gdy trzeba zbudować nowy projekt Pythona od zera na podstawie specyfikacji.
argument-hint: <plik specyfikacji, np. SPEC.md>
disable-model-invocation: true
allowed-tools: Bash(uv *), PowerShell(uv *)
---

# Nowy projekt Python według standardu

Specyfikacja: $ARGUMENTS. Przeczytaj ją w całości przed pierwszą zmianą.
Specyfikacja mówi, CO zbudować. Ten skill mówi, JAK. Przy konflikcie wygrywa specyfikacja.
Pracuj bez pytania o kolejne kroki, aż do końca kroku 7.

## 1. Szkielet przez uv
W bieżącym katalogu uruchom:
```
uv init --package --python 3.14 --name <nazwa ze specyfikacji>
uv add structlog "colorama; sys_platform == 'win32'"
uv add --dev pytest ruff
```
- Zależności dodawaj tylko przez `uv add`. Bez pip, requirements.txt i setup.py.
- `colorama` jest potrzebna tylko na Windows. Bez niej structlog nie pokazuje kolorów w konsoli.
- Ustaw entry point w `[project.scripts]` na `<pakiet>.main:main`. Funkcja `main(argv: list[str] | None = None) -> int` zwraca kod wyjścia. Usuń przykładową funkcję `main` z `__init__.py`.
- Dopisz do pyproject.toml:
```toml
[tool.pytest]
minversion = "9.0"
testpaths = ["tests"]
addopts = ["-ra", "--strict-markers", "--strict-config"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "PTH", "RUF"]
```

## 2. Struktura (architektura heksagonalna)
```
src/<pakiet>/
  domain/            modele i reguły biznesowe, czysty Python
  application/
    ports.py         porty jako typing.Protocol
    errors.py        wyjątki aplikacji, które zgłaszają adaptery
    <use_case>.py    przypadki użycia, zależą tylko od domain i portów
  adapters/
    inbound/cli.py   argparse, wywołanie use case'u, wynik na stdout, kod wyjścia
    outbound/        implementacje portów (pliki, baza, API)
  logging_config.py
  main.py            composition root
tests/
  conftest.py
  unit/              domena i use case'y z fałszywym adapterem w pamięci
  integration/       adaptery outbound na prawdziwych plikach (tmp_path)
  e2e/               cała aplikacja przez main(argv)
  test_architecture.py
```
Kierunek zależności: adapters -> application -> domain.
- `domain` nie importuje `application`, `adapters`, `main`, `structlog` ani modułów IO (`os`, `sys`, `io`, `pathlib`, `csv`, `json`, `logging`). Nie robi IO i nie loguje.
- `application` nie importuje `adapters` ani `main`.
- Tylko `main.py` zna konkretne klasy adapterów.

Podział odpowiedzialności:
- Adapter outbound parsuje format zewnętrzny i odrzuca błędne rekordy. Wyjątki infrastruktury (np. `FileNotFoundError`) zamienia na wyjątki z `application/errors.py`.
- Use case łączy port z regułami domeny i loguje zdarzenia biznesowe (liczniki).
- Adapter inbound zamienia wynik na tekst dla użytkownika, a wyjątki aplikacji na log i kod wyjścia. Formatowanie wyniku nie trafia do domeny.
- `main.py` parsuje argumenty przez `cli`, konfiguruje logi, tworzy adaptery i use case, potem oddaje sterowanie do `cli`. Nie zawiera logiki.

## 3. Zasady kodu
- Pełne type hints. Modele domeny: `@dataclass(frozen=True, slots=True)`.
- Pieniądze: `decimal.Decimal`, nigdy `float`. Daty: `datetime.date`.
- Pliki tekstowe zawsze z jawnym `encoding="utf-8"` (`open`, `Path.open`, `Path.read_text`, `Path.write_text`). Plik dla modułu `csv` otwieraj z `newline=""`.
- Identyfikatory w kodzie (klasy, funkcje, zmienne, moduły) po angielsku. Wyjątek: nazwa pakietu ze specyfikacji. Teksty dla użytkownika w języku specyfikacji.
- CLI na `argparse`. Bez bibliotek, których nie wymaga specyfikacja lub ten skill.
- Bez kodu na zapas. Tylko to, co jest w specyfikacji.

## 4. Logowanie (structlog)
- `logging_config.py` zawiera `configure_logging(level: str, fmt: Literal["console", "json"]) -> None`.
  Procesory: `merge_contextvars`, `add_log_level`, `TimeStamper(fmt="iso", utc=True)`, na końcu `ConsoleRenderer(colors=sys.stderr.isatty())` albo `JSONRenderer()`.
  `wrapper_class=structlog.make_filtering_bound_logger(level)`, `logger_factory=structlog.PrintLoggerFactory(file=sys.stderr)`, `cache_logger_on_first_use=False`.
- `configure_logging` wywołuje tylko `main.py`. Nigdy przy imporcie modułu.
- Logi idą na stderr. Wynik programu idzie na stdout. `print` tylko w adapterze inbound, tylko dla wyniku.
- Na starcie `main.py` wywołuje `structlog.contextvars.clear_contextvars()`, potem `bind_contextvars(run_id=uuid.uuid4().hex)`.
- W modułach: `log = structlog.get_logger()`. Nazwy zdarzeń w snake_case, dane jako pola: `log.info("rows_loaded", count=12)`. Bez f-stringów w treści zdarzenia.
- Nie loguj danych osobowych ani finansowych (nazwy, kwoty, numery kont, treść wierszy). Loguj liczniki i numery linii.

## 5. Testy (pytest)
- Każda reguła i każde kryterium akceptacji ze specyfikacji ma co najmniej jeden test.
- Nazwa testu opisuje regułę: `test_<co>_<warunek>_<wynik>`.
- Unit testy use case'ów używają fałszywego adaptera, czyli prostej klasy spełniającej port. Bez `mock.patch` na modułach.
- Logi sprawdzaj przez `structlog.testing.capture_logs()`.
- `tests/conftest.py` ma fixture `autouse`, który po każdym teście wywołuje `structlog.reset_defaults()` i `structlog.contextvars.clear_contextvars()`. Kolejność testów nie zmienia wyniku.
- Test e2e wywołuje `main([...])` w procesie i sprawdza kod wyjścia, stdout i stderr (`capsys`).
- `test_architecture.py` parsuje importy (`ast`) wszystkich plików w `domain` i `application`, także importy względne (`ImportFrom.level > 0`), i sprawdza reguły z kroku 2.
- Każdy test sprawdza konkretną wartość. Zakaz testów bez asercji i asercji typu `assert result`.

## 6. Weryfikacja
Uruchamiaj i poprawiaj, aż wszystko przejdzie:
```
uv run ruff format .
uv run ruff check --fix .
uv run pytest
```
- Poprawiaj kod, a nie testy. Nie osłabiaj asercji. Bez `pytest.skip`, `xfail`, `# noqa` i `# type: ignore`.
- Potem uruchom aplikację przez `uv run` i sprawdź każde kryterium akceptacji ze specyfikacji.

## 7. Zakończenie
- `README.md`: jedno zdanie opisu, komendy uruchomienia aplikacji i testów. Maksymalnie 20 linii.
- `CLAUDE.md`: maksymalnie 15 linii. Komendy (run, test, lint) i skrót zasad z kroków 2-5.
- Na koniec wypisz: drzewo plików `src/` i `tests/`, wynik pytest, listę kryteriów akceptacji z oznaczeniem spełnione lub niespełnione.
