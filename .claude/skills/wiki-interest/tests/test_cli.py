"""Test CLI helpers, chart and PDF output (offline)."""

import json
from datetime import date, timedelta
from urllib.parse import unquote

import httpx
import pytest
from wiki_interest import cli
from wiki_interest.analyze import analyze
from wiki_interest.fetch import Client
from wiki_interest.i18n import period_label
from wiki_interest.plot import plot_trends
from wiki_interest.report import auto_problems, generate_report
from wiki_interest.resolve import Article


def test_period_covers_whole_months():
    assert cli._period(24, today=date(2026, 9, 26)) == (date(2024, 9, 1), date(2026, 8, 31))
    assert cli._period(1, today=date(2026, 1, 5)) == (date(2025, 12, 1), date(2025, 12, 31))
    assert cli._period(13, today=date(2026, 1, 5)) == (date(2024, 12, 1), date(2025, 12, 31))


def test_period_waits_until_last_month_is_published():
    """On Oct 2 the last days of September may be missing from the API: end with August."""
    assert cli._period(1, today=date(2026, 10, 2)) == (date(2026, 8, 1), date(2026, 8, 31))
    assert cli._period(1, today=date(2026, 10, 4)) == (date(2026, 9, 1), date(2026, 9, 30))


def test_data_start_skips_partial_first_month():
    def art(created):
        return Article("Q1", "uk", "A", created=created)

    start = date(2024, 9, 1)
    assert cli._data_start([art(date(2020, 5, 3))], start) == start
    assert cli._data_start([art(date(2025, 3, 15))], start) == date(2025, 4, 1)
    assert cli._data_start([art(date(2025, 12, 31))], start) == date(2026, 1, 1)
    assert cli._data_start([art(date(2025, 3, 1))], start) == date(2025, 3, 1)
    assert cli._data_start([art(None)], start) == start  # unknown: keep the whole period
    assert cli._data_start([art(date(2025, 3, 15)), art(date(2021, 1, 1))], start) == start


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


def _pdf_text(path) -> str:
    from pypdf import PdfReader

    return " ".join(page.extract_text() for page in PdfReader(str(path)).pages)


def test_report_shows_seasonality_only_with_two_years(tmp_path):
    months = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]
    daily = {}
    for i in range(36):
        y, m = 2023 + (8 + i) // 12, months[i % 12]
        for d in range(1, 29):
            daily[date(y, m, d)] = 300 if m == 11 else 60 if m == 6 else 100
    chart = tmp_path / "chart.png"
    plot_trends({"uk": analyze(daily)}, output=str(chart), lang="uk")

    pdf = tmp_path / "seasonal.pdf"
    generate_report("Дієта", {"uk": analyze(daily)}, str(chart), output_file=str(pdf), lang="uk")
    text = _pdf_text(pdf)
    assert "Сезонність" in text
    assert "Найвищий місяць щороку — листопад" in text
    assert "Найнижчий місяць щороку — червень" in text

    short = tmp_path / "short.pdf"
    generate_report("Тест", _sample_results(), str(chart), output_file=str(short), lang="uk")
    assert "Сезонність" not in _pdf_text(short)  # 12 months: no seasonal comparison


def _make_session(home, n_steps: int):
    """Session folder as `run` writes it: session.json + analysis-N.json per step."""
    run_dir = home / "runs" / "session-1"
    run_dir.mkdir(parents=True)
    steps = []
    for n in range(1, n_steps + 1):
        (run_dir / f"analysis-{n}.json").write_text(json.dumps(_sample_results()), encoding="utf-8")
        steps.append({
            "step": n, "question": None if n == 1 else f"Уточнення {n}", "topic": "Test",
            "qids": ["Q1"], "langs": ["uk", "pl", "cs"], "months": 12,
            "period": ["2025-01-01", "2025-12-31"], "langs_missing": ["cs"],
        })
    (run_dir / "session.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    return run_dir


def test_report_command_reads_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    run_dir = _make_session(tmp_path, 1)

    code = cli.main([
        "report", "--session", "session-1", "--lang", "uk", "--title", "Тест",
        "--conclusion", "ok", "--recommendation", "a", "--recommendation", "b",
    ])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert (run_dir / "report.pdf").exists()
    assert (run_dir / "chart-1.png").exists()
    assert set(out["summary"]) == {"uk", "pl"}


def test_report_includes_followups_in_one_pdf(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    run_dir = _make_session(tmp_path, 3)

    code = cli.main([
        "report", "--session", "session-1", "--lang", "uk", "--conclusion", "головна відповідь",
        "--followup", "Чому надійність низька?", "Мало переглядів.",
        "--followup", "2", "Коротка відповідь на крок 2.",
    ])  # step 3 is not mentioned but still goes into the report
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert [p.rsplit("-", 1)[-1] for p in out["files"]["charts"]] == ["1.png", "2.png", "3.png"]
    assert all((run_dir / f"chart-{n}.png").exists() for n in (1, 2, 3))
    assert list(run_dir.glob("*.pdf")) == [run_dir / "report.pdf"]


def test_report_lists_data_problems_of_followup_steps(tmp_path, monkeypatch, capsys):
    """Each data step's missing languages go into the PDF, not only the main step's."""
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    run_dir = _make_session(tmp_path, 3)  # every step has "cs" missing
    assert cli.main(["report", "--session", "session-1", "--lang", "uk", "--followup", "2", "ok"]) == 0
    capsys.readouterr()
    assert _pdf_text(run_dir / "report.pdf").count("статті немає") == 3


def _fake_wikimedia(pl_created: date):
    """Wikidata + Wikipedia + pageviews: uk article since 2010, pl article created
    `pl_created`, de article without any views, no cs article."""
    titles = {"uk": "Астрономія", "pl": "Astronomia", "de": "Astronomie"}
    created = {"uk": "2010-01-01", "pl": pl_created.isoformat(), "de": "2012-01-01"}

    def days(path: str, since: date | None = None):
        s, e = path.rstrip("/").split("/")[-2:]
        d, end = date(int(s[:4]), int(s[4:6]), int(s[6:])), date(int(e[:4]), int(e[4:6]), int(e[6:]))
        d = max(d, since) if since else d
        items = []
        while d <= end:
            items.append({"timestamp": d.strftime("%Y%m%d00"), "views": 500})
            d += timedelta(days=1)
        return {"items": items}

    def handler(request: httpx.Request) -> httpx.Response:
        url, params = request.url, dict(request.url.params)
        if url.host == "www.wikidata.org":
            return httpx.Response(200, json={"entities": {"Q1": {
                "labels": {"en": {"value": "Astronomy"}},
                "sitelinks": {f"{lang}wiki": {"title": t} for lang, t in titles.items()},
            }}})
        if url.host.endswith("wikipedia.org"):
            lang = url.host.split(".")[0]
            if params.get("prop") == "revisions":
                page = {"title": titles[lang], "revisions": [{"timestamp": created[lang] + "T10:00:00Z"}]}
            else:
                page = {"title": titles[lang]}
            return httpx.Response(200, json={"query": {"pages": [page]}})
        path = unquote(url.path)
        if "/aggregate/" in path:
            return httpx.Response(200, json=days(path))
        if "/de.wikipedia/" in path:
            return httpx.Response(404)
        return httpx.Response(200, json=days(path, since=pl_created if "/pl.wikipedia/" in path else None))

    return lambda: Client(transport=httpx.MockTransport(handler))


def test_run_new_article_and_no_views_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    start, end = cli._period(24)
    pl_created = (end - timedelta(days=400)).replace(day=15)
    monkeypatch.setattr(cli, "Client", _fake_wikimedia(pl_created))

    assert cli.main(["run", "--qids", "Q1", "--langs", "uk,pl,de,cs", "--months", "24"]) == 0
    out = json.loads(capsys.readouterr().out)

    assert out["langs_missing"] == ["cs"]  # no article
    assert out["langs_no_views"] == ["de"]  # article exists, no views: not "no article"
    uk, pl = out["results"]["uk"], out["results"]["pl"]
    assert uk["first_month"] == start.strftime("%Y-%m")
    # pl: the partial creation month is skipped, so constant 500/day is flat, not "growth".
    assert pl["first_month"] == (pl_created.replace(day=28) + timedelta(days=4)).strftime("%Y-%m")
    assert abs(pl["trend_pct_per_year"]) < 5
    assert "short_history" in pl["caveats"]


def test_report_rejects_unknown_step(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    _make_session(tmp_path, 1)
    assert cli.main(["report", "--session", "session-1", "--followup", "2", "x"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "unknown_step"


def test_missing_session_is_json_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    assert cli.main(["report", "--session", "nope"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "session_not_found"
    assert cli.main(["run", "--session", "nope"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "session_not_found"


def test_months_zero_is_rejected():
    with pytest.raises(SystemExit):
        cli.main(["run", "Astronomy", "--langs", "uk", "--months", "0"])


def test_year_as_followup_question(tmp_path, monkeypatch, capsys):
    """"2025" is a text question (a year), not step 2025."""
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    run_dir = _make_session(tmp_path, 1)
    assert cli.main(["report", "--session", "session-1", "--lang", "uk", "--followup", "2025", "Рік пандемії."]) == 0
    capsys.readouterr()
    assert "Уточнення: 2025" in _pdf_text(run_dir / "report.pdf")


def test_internal_error_has_hint(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise RuntimeError("network down")

    monkeypatch.setattr(cli, "resolve", boom)
    assert cli.main(["resolve", "Astronomy", "--langs", "uk"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["error"] == "internal_error" and out["hint"] and "network down" in out["message"]


def test_sessions_started_in_same_second_differ(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_INTEREST_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "Client", _fake_wikimedia(date(2001, 1, 1)))
    monkeypatch.setattr(cli.time, "time", lambda: 1_790_000_000)
    ids = []
    for _ in range(2):
        cli.main(["run", "--qids", "Q1", "--langs", "uk", "--months", "1"])
        ids.append(json.loads(capsys.readouterr().out)["session_id"])
    assert ids[0] != ids[1]


def test_topic_or_qids_required():
    with pytest.raises(SystemExit):
        cli.main(["run", "--langs", "uk"])
    with pytest.raises(SystemExit):
        cli.main(["run", "Astronomy"])  # --langs needed for a new session
