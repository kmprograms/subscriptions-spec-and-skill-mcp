import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from subskrypcje.main import main

EXPECTED_REPORT = """\
Wykryte subskrypcje: 4
CITYFIT SP. Z O.O.     139,00 zł/mies.   1668,00 zł/rok
NETFLIX.COM             49,00 zł/mies.    588,00 zł/rok
SPOTIFY AB STOCKHOLM    26,99 zł/mies.    323,88 zł/rok   zmiana ceny: 23,99 -> 26,99
APPLE.COM/BILL           4,99 zł/mies.     59,88 zł/rok
Razem: 219,98 zł/mies., 2639,76 zł/rok
"""

LOG_FIELDS = {"event", "level", "timestamp", "run_id"}
EVENT_FIELDS = {"line", "reason", "rows_loaded", "rows_skipped", "count", "path"}


def run_json(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, list[dict[str, Any]]]:
    exit_code = main([*argv, "--log-format", "json"])
    captured = capsys.readouterr()
    return exit_code, captured.out, [json.loads(line) for line in captured.err.splitlines()]


def test_main_sample_statement_prints_exact_report_on_stdout(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main([str(sample_statement)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == EXPECTED_REPORT


def test_main_sample_statement_lists_four_subscriptions_in_order(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(sample_statement)])

    rows = capsys.readouterr().out.splitlines()[1:-1]
    assert [row.split("  ")[0] for row in rows] == [
        "CITYFIT SP. Z O.O.",
        "NETFLIX.COM",
        "SPOTIFY AB STOCKHOLM",
        "APPLE.COM/BILL",
    ]


def test_main_sample_statement_last_line_is_total(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(sample_statement)])

    last_line = capsys.readouterr().out.splitlines()[-1]
    assert last_line == "Razem: 219,98 zł/mies., 2639,76 zł/rok"


def test_main_sample_statement_only_spotify_has_price_change(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(sample_statement)])

    changes = [line for line in capsys.readouterr().out.splitlines() if "zmiana ceny" in line]
    assert len(changes) == 1
    assert changes[0].startswith("SPOTIFY AB STOCKHOLM ")
    assert changes[0].endswith("zmiana ceny: 23,99 -> 26,99")


@pytest.mark.parametrize(
    "name",
    [
        "ACME",
        "ORLEN STACJA NR",
        "BIEDRONKA KRAKOW",
        "ALLEGRO.PL",
        "MEDIA EXPERT",
        "TAURON SPRZEDAZ",
        "ZABKA",
    ],
)
def test_main_sample_statement_does_not_report_non_subscription(
    sample_statement: Path, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    main([str(sample_statement)])

    assert name not in capsys.readouterr().out


def test_main_sample_statement_logs_skipped_rows_and_counters_in_console_format(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(sample_statement)])

    lines = capsys.readouterr().err.splitlines()
    skipped = [line for line in lines if "row_skipped" in line]
    loaded = [line for line in lines if "statement_loaded" in line]
    assert len(skipped) == 2
    assert "line=14" in skipped[0]
    assert "reason=invalid_amount" in skipped[0]
    assert "line=30" in skipped[1]
    assert "reason=invalid_date" in skipped[1]
    assert len(loaded) == 1
    assert "rows_loaded=55" in loaded[0]
    assert "rows_skipped=2" in loaded[0]


def test_main_json_format_every_stderr_line_is_json_with_required_fields(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, _, events = run_json([str(sample_statement)], capsys)

    assert exit_code == 0
    assert [e["event"] for e in events] == [
        "row_skipped",
        "row_skipped",
        "statement_loaded",
        "subscriptions_detected",
    ]
    assert all(e.keys() >= LOG_FIELDS for e in events)
    assert len({e["run_id"] for e in events}) == 1
    assert len(events[0]["run_id"]) == 32


def test_main_json_format_events_carry_spec_values(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, events = run_json([str(sample_statement)], capsys)

    values = [
        {k: v for k, v in e.items() if k not in LOG_FIELDS} | {"level": e["level"]} for e in events
    ]
    assert values == [
        {"level": "warning", "line": 14, "reason": "invalid_amount"},
        {"level": "warning", "line": 30, "reason": "invalid_date"},
        {"level": "info", "rows_loaded": 55, "rows_skipped": 2},
        {"level": "info", "count": 4},
    ]


def test_main_logs_contain_only_counters_without_names_or_amounts(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, events = run_json([str(sample_statement)], capsys)

    assert {key for e in events for key in e} <= LOG_FIELDS | EVENT_FIELDS
    raw = json.dumps(events)
    for fragment in ("NETFLIX", "Netflix", "CITYFIT", "SPOTIFY", "ZABKA", "49,00", "abc"):
        assert fragment not in raw


def test_main_two_runs_have_different_run_ids(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, first = run_json([str(sample_statement)], capsys)
    _, _, second = run_json([str(sample_statement)], capsys)

    assert first[0]["run_id"] != second[0]["run_id"]


def test_main_logs_never_reach_stdout(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(sample_statement), "--log-level", "DEBUG"])

    captured = capsys.readouterr()
    assert captured.out == EXPECTED_REPORT
    assert "run_id" not in captured.out
    assert len(captured.err.splitlines()) == 4


def test_main_log_level_warning_hides_info_events(
    sample_statement: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, events = run_json([str(sample_statement), "--log-level", "WARNING"], capsys)

    assert [e["event"] for e in events] == ["row_skipped", "row_skipped"]


def test_main_missing_file_exits_1_with_single_error_line_and_empty_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "brak.csv"

    exit_code = main([str(path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
    assert "statement_not_found" in captured.err
    assert f"path={path}" in captured.err
    assert "Traceback" not in captured.err


def test_main_missing_file_json_log_has_error_level_and_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "brak.csv"

    exit_code, out, events = run_json([str(path)], capsys)

    assert (exit_code, out) == (1, "")
    assert len(events) == 1
    assert (events[0]["event"], events[0]["level"], events[0]["path"]) == (
        "statement_not_found",
        "error",
        str(path),
    )


def test_main_statement_without_subscriptions_prints_message(
    make_statement: Callable[..., Path], capsys: pytest.CaptureFixture[str]
) -> None:
    path = make_statement("2026-09-05;NETFLIX.COM;Płatność kartą;-49,00")

    exit_code = main([str(path)])

    assert exit_code == 0
    assert capsys.readouterr().out == "Nie wykryto subskrypcji.\n"


class ForwardingStream:
    """Mimics colorama's StreamWrapper, which forwards unknown attributes to the real stream."""

    def __init__(self, wrapped: io.TextIOWrapper) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)


@pytest.mark.parametrize("wrap", [False, True], ids=["plain", "colorama_wrapped"])
def test_main_stdout_in_ansi_code_page_is_written_as_utf8(
    sample_statement: Path, monkeypatch: pytest.MonkeyPatch, wrap: bool
) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1250", newline="")
    monkeypatch.setattr("sys.stdout", ForwardingStream(stream) if wrap else stream)

    main([str(sample_statement)])

    stream.flush()
    assert buffer.getvalue().decode("utf-8") == EXPECTED_REPORT
