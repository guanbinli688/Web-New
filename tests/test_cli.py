from news_finance_v2.cli import main


def test_self_test_command_returns_zero(capsys):
    assert main(["--self-test"]) == 0
    assert "self-test passed" in capsys.readouterr().out


def test_offline_preview_creates_v2_html(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_FINANCE_OFFLINE", "1")
    assert main(["--preview", "--base-dir", str(tmp_path)]) == 0
    report = tmp_path / "html" / "news_finance_v2_preview.html"
    assert report.exists()
    assert "不构成投资建议" in report.read_text(encoding="utf-8")


def test_online_preview_without_ai_config_returns_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("NEWS_FINANCE_OFFLINE", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert main(["--preview", "--base-dir", str(tmp_path)]) == 2
    assert "AI_MODEL" in capsys.readouterr().err


def test_full_run_requires_real_sec_contact(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("NEWS_FINANCE_OFFLINE", raising=False)
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SEC_USER_AGENT", "Your Name your-real-email@example.org")

    assert main(["--preview", "--full", "--base-dir", str(tmp_path)]) == 2
    assert "SEC_USER_AGENT" in capsys.readouterr().err


def test_check_trading_day_prints_machine_readable_result(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REPORT_DATE_OVERRIDE", "2026-09-07")

    assert main(["--check-trading-day", "--base-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "false"
