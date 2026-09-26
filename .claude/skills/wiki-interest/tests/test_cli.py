"""Test CLI helpers, chart and PDF output (offline)."""

import json
from datetime import date

import pytest
from wiki_interest import cli
from wiki_interest.analyze import analyze
from wiki_interest.i18n import period_label
from wiki_interest.plot import plot_trends
from wiki_interest.report import auto_problems, generate_report


def test_period_covers_whole_months():
    assert cli._period(24, today=date(2026, 9, 26)) == (date(2024, 9, 1), date(2026, 8, 31))
    assert cli._period(1, today=date(2026, 1, 5)) == (date(2025, 12, 1), date(2025, 12, 31))
    assert cli._period(13, today=date(2026, 1, 5)) == (date(2024, 12, 1), date(2025, 12, 31))


def test_period_label():
    assert period_label("2024-09-01", "2026-08-31", "uk") == "вер 2024 – сер 2026"
    assert period_label("2024-09-01", "2026-08-31", "en") == "Sep 2024 – Aug 2026"


def _sample_results():
    daily = {date(2025, m, d): 100 * m for m in range(1, 13) for d in range(1, 29)}
    return {"uk": analyze(daily), "pl": analyze({k: v * 2 for k, v in daily.items()})}


@pytest.mark.parametrize("lang", ["uk", "en"])
def test_plot_is_real_png(tmp_path, lang):
    out = tmp_path / "chart.png"
    plot_trends(_sample_results(), output=str(out), lang=lang)
    data = out.read_bytes()
    assert data.startswith(b"\x89PNG")
    assert len(data) > 10_000  # an actual chart, not an empty axes


def test_auto_problems_lists_missing_language_and_short_history():
    problems = auto_problems(_sample_results(), ["cs"], "uk")
    assert any("чеська" in p for p in problems)
    assert any("менше ніж за 2 роки" in p for p in problems)


def test_report_pdf_cyrillic_and_long_text_flows(tmp_path):
    chart = tmp_path / "chart.png"
    plot_trends(_sample_results(), output=str(chart), lang="uk")
    pdf = tmp_path / "report.pdf"
    generate_report(
        "Чи зростає інтерес до витинанки?", _sample_results(), str(chart),
        conclusion="Інтерес зростає. " * 400, output_file=str(pdf),
        recommendations=["Перевірити пошукові запити."], lang="uk",
    )
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF")
    assert data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") >= 2  # long text -> more pages


def test_report_command_reads_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "analysis.json").write_text(json.dumps(_sample_results()), encoding="utf-8")
    (run_dir / "meta.json").write_text(
        json.dumps({"topic": "Test", "period": ["2025-01-01", "2025-12-31"], "langs_missing": ["cs"]}),
        encoding="utf-8",
    )

    code = cli.main([
        "report", "--run", "run-1", "--lang", "uk", "--title", "Тест",
        "--conclusion", "ok", "--recommendation", "a", "--recommendation", "b",
    ])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert (run_dir / "report.pdf").exists()
    assert (run_dir / "chart_uk.png").exists()
    assert set(out["summary"]) == {"uk", "pl"}


def test_report_compares_topics_from_several_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    one_lang = {"en": _sample_results()["uk"]}
    for run_id, topic in (("run-a", "JavaScript"), ("run-b", "TypeScript")):
        run_dir = tmp_path / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "analysis.json").write_text(json.dumps(one_lang), encoding="utf-8")
        (run_dir / "meta.json").write_text(
            json.dumps({"topic": topic, "period": ["2025-01-01", "2025-12-31"]}), encoding="utf-8"
        )

    assert cli.main(["report", "--run", "run-a", "--run", "run-b", "--lang", "uk"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out["summary"]) == {"JavaScript", "TypeScript"}
    assert out["files"]["report"].endswith("report.pdf")


def test_missing_run_is_json_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    assert cli.main(["report", "--run", "nope"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "run_not_found"


def test_topic_or_qids_required():
    with pytest.raises(SystemExit):
        cli.main(["run", "--langs", "uk"])
