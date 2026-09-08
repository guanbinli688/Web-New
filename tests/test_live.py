import json
from datetime import date
from pathlib import Path

from news_finance_v2.config import Settings
from news_finance_v2.live import (
    HttpCollector, OpenAIAnalyzer, SMTPMailer, parse_ics_events, rank_news_symbols,
    _dedicated_calendar_specs, _normalize_market_calendar_events,
    _parse_dedicated_calendar_events,
)
from news_finance_v2.market import SIGNALS
from news_finance_v2.sources import COMPANY_NAMES, COMPANY_UNIVERSE


class Response:
    def __init__(self, status_code=200, text="<main>Economic calendar and policy outlook with enough useful content for research.</main>"):
        self.status_code = status_code
        self.text = text
        self.url = "https://example.test/final"
        self.headers = {"Content-Type": "text/html"}


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.headers = {}
    def get(self, *args, **kwargs): return next(self.responses)


def test_http_collector_records_core_failure_and_market_coverage(tmp_path):
    settings = Settings.from_env(tmp_path)
    session = Session([Response(503)] + [Response() for _ in range(100)])
    collector = HttpCollector(
        settings, session=session,
        market_loader=lambda symbols: {symbol: 100.0 for symbol in symbols[:-1]},
    )

    result = collector.collect(full=False)

    assert "BLS" in result["core_failures"]
    assert result["market_coverage"] == (len(SIGNALS) - 1) / len(SIGNALS)
    assert result["sources"][0]["status"] == "HTTP_503"


def test_full_collection_adds_company_ir_sources(tmp_path):
    settings = Settings.from_env(tmp_path)
    session = Session([Response() for _ in range(100)])
    collector = HttpCollector(
        settings, session=session,
        market_loader=lambda symbols: {s: 1 for s in symbols},
        stock_loader=lambda symbols: {
            s: {"price": 1, "day_change_pct": -1, "volatility_20_pct": 1}
            for s in symbols
        },
    )
    regular = collector.collect(full=False)
    session.responses = iter([Response() for _ in range(100)])
    full = collector.collect(full=True)
    assert len(full["sources"]) > len(regular["sources"])
    assert any(item["kind"] == "company" for item in full["sources"])
    assert any(item["kind"] == "company_news" for item in full["sources"])
    assert len(full["stock_snapshot"]) == len(COMPANY_UNIVERSE)
    assert len(full["screened_symbols"]) == 50
    assert full["universe_size"] >= 100


def test_news_prefilter_uses_each_stocks_own_volatility():
    snapshot = {
        "A": {"day_change_pct": -1, "volatility_20_pct": 1},
        "B": {"day_change_pct": -2, "volatility_20_pct": 4},
        "C": {"day_change_pct": 1, "volatility_20_pct": 1},
    }

    assert rank_news_symbols(snapshot, limit=2) == ("A", "B")


def test_expanded_universe_has_one_canonical_chinese_name_per_symbol():
    assert set(COMPANY_NAMES) == set(COMPANY_UNIVERSE)
    assert COMPANY_NAMES["MRVL"] == "迈威尔科技"
    assert COMPANY_NAMES["MU"] == "美光科技"


def test_ics_events_are_limited_to_forward_window():
    text = "BEGIN:VEVENT\nDTSTART:20260820T123000Z\nSUMMARY:Initial Jobless Claims\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART:20260930T123000Z\nSUMMARY:Too Far\nEND:VEVENT"
    events = parse_ics_events(text, start=date(2026, 8, 19), days=14)
    assert events == [{"date": "2026-08-20", "title": "Initial Jobless Claims", "source": "BLS"}]


def test_collector_parses_calendar_from_untruncated_ics(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_DATE_OVERRIDE", "2026-08-19")
    settings = Settings.from_env(tmp_path)
    ics = "X" * 13000 + "\nBEGIN:VEVENT\nDTSTART:20260820T123000Z\nSUMMARY:Initial Jobless Claims\nEND:VEVENT"
    session = Session([Response(text=ics)] + [Response() for _ in range(100)])
    collector = HttpCollector(settings, session=session, market_loader=lambda symbols: {s: 1 for s in symbols})

    result = collector.collect(full=False)

    assert result["events"] == [{
        "date": "2026-08-20", "title": "Initial Jobless Claims", "source": "BLS",
        "url": "https://example.test/final",
    }]


def test_calendar_keeps_recurring_official_events_and_names_companies():
    raw = [
        {"date": "2026-09-09", "title": "EIA原油库存周报", "source": "EIA"},
        {"date": "2026-09-16", "title": "EIA原油库存周报", "source": "EIA"},
        {"date": "2026-09-11", "title": "大型科技公司投资者活动", "source": "NVIDIA IR"},
        {"date": "2026-09-16", "title": "美联储FOMC利率决议", "source": "Federal Reserve"},
    ]

    events = _normalize_market_calendar_events([], raw, start=date(2026, 9, 7))

    assert len(events) == 4
    assert sum(item["title"] == "EIA原油库存周报" for item in events) == 2
    assert any(item["title"] == "英伟达投资者活动" for item in events)
    assert any(item["source"] == "Federal Reserve" for item in events)
    assert not any("大型科技公司" in item["title"] for item in events)


def test_fomc_calendar_parser_uses_policy_decision_day():
    html = """
    <main><h4>2026 FOMC Meetings</h4>
    <div>September</div><div>15-16*</div>
    <div>October</div><div>27-28</div>
    <h4>2025 FOMC Meetings</h4></main>
    """

    events = _parse_dedicated_calendar_events(
        "FOMC Calendar", html, start=date(2026, 9, 7), days=14,
    )

    assert events == [{
        "date": "2026-09-16",
        "title": "美联储FOMC利率决议",
        "source": "Federal Reserve",
    }]


def test_new_york_fed_calendar_fills_major_weekday_releases():
    html = """
    <main><h1>September 2026</h1><table><tr>
      <td>15 <a>Empire State Manufacturing Survey</a></td>
      <td>16 <a>Business Leaders Survey</a></td>
      <td>17 <a>Initial Claims</a><a>Philadelphia Fed Manufacturing Survey</a></td>
    </tr></table></main>
    """

    events = _parse_dedicated_calendar_events(
        "New York Fed Indicators", html, start=date(2026, 9, 7), days=14,
    )

    assert {(item["date"], item["title"]) for item in events} == {
        ("2026-09-15", "纽约联储制造业指数"),
        ("2026-09-16", "纽约联储服务业活动调查"),
        ("2026-09-17", "美国首次申请失业救济"),
        ("2026-09-17", "费城联储制造业指数"),
    }


def test_census_calendar_keeps_quarterly_services_and_wholesale_trade():
    html = """
    <table>
      <tr><td>Quarterly Services Survey</td><td>September 9, 2026</td></tr>
      <tr><td>Monthly Wholesale Trade</td><td>September 10, 2026</td></tr>
    </table>
    """

    events = _parse_dedicated_calendar_events(
        "US Census Calendar", html, start=date(2026, 9, 7), days=14,
    )

    assert [item["title"] for item in events] == [
        "美国季度服务业调查", "美国批发销售与库存",
    ]


def test_nyse_calendar_marks_market_holidays_instead_of_empty_days():
    html = """
    <table>
      <tr><th>Holiday</th><th>2026</th></tr>
      <tr><td>Labor Day</td><td>September 7</td></tr>
    </table>
    """

    events = _parse_dedicated_calendar_events(
        "NYSE Holidays", html, start=date(2026, 9, 7), days=14,
    )

    assert events == [{
        "date": "2026-09-07",
        "title": "美国劳动节休市",
        "source": "NYSE Holidays",
    }]


def test_dedicated_calendar_sources_cover_government_and_major_companies():
    names = {item[0] for item in _dedicated_calendar_specs(date(2026, 9, 7))}

    assert {"BEA", "FOMC Calendar", "Treasury Auctions Calendar", "US Census Calendar"} <= names
    assert {"NVIDIA IR", "Microsoft IR", "Apple IR", "Amazon IR", "JPM IR", "Walmart IR"} <= names
    assert {"New York Fed Indicators", "NYSE Holidays", "HubSpot IR", "Lennar IR"} <= names


class Output:
    output_text = json.dumps({
        "direction": {"title": "风险偏好改善", "brief": "信用和广度确认"},
        "predictions": [{
            "horizon_days": 5, "target": "SPY", "direction": "UP",
            "probability": .61, "thesis": "信用改善", "invalidation": "利差扩大",
            "sensors": ["credit"], "evidence_ids": ["MKT-SPY", "OFF-BLS"],
        }],
    }, ensure_ascii=False)


class Responses:
    def __init__(self): self.calls = 0
    def create(self, **kwargs):
        self.calls += 1
        assert kwargs["model"] == "test-model"
        assert "市场快照" in kwargs["input"]
        if "跨资产预测" not in kwargs["input"]:
            assert "horizons" in kwargs["input"]
            assert "actions" in kwargs["input"]
            assert "flows" in kwargs["input"]
            assert "logic" in kwargs["input"]
            assert "media_themes" in kwargs["input"]
        return Output()


class Client:
    def __init__(self): self.responses = Responses()


def test_openai_analyzer_parses_structured_prediction(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_MODEL", "test-model")
    client = Client()
    analyzer = OpenAIAnalyzer(Settings.from_env(tmp_path), client=client)
    result = analyzer.analyze({"market": {"SPY": 100}, "sources": [], "events": []})
    analyzer.analyze({"market": {"SPY": 100}, "sources": [], "events": []})
    assert result["predictions"][0]["target"] == "SPY"
    assert client.responses.calls == 2


def test_openai_analyzer_runs_dedicated_company_decision_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_MODEL", "test-model")

    class CompanyResponses:
        def __init__(self): self.calls = 0
        def create(self, **kwargs):
            self.calls += 1
            if "公司一手材料" in kwargs["input"]:
                assert "个股市场状态" in kwargs["input"]
                return type("Result", (), {"output_text": json.dumps({"company_signals": [{
                    "company": "英伟达", "ticker": "NVDA", "stance": "等待",
                    "brief": "新品需求仍强，但估值偏高，等待业绩确认后再行动。",
                    "trigger": "收入指引继续上调", "risk": "云厂商资本开支放缓", "source": "NVIDIA IR",
                }]}, ensure_ascii=False)})()
            return Output()

    client = type("CompanyClient", (), {"responses": CompanyResponses()})()
    analyzer = OpenAIAnalyzer(Settings.from_env(tmp_path), client=client)
    result = analyzer.analyze({
        "market": {"NVDA": 100},
        "stock_snapshot": {"NVDA": {"price": 100, "volatility_20_pct": 2}},
        "sources": [{"name": "NVIDIA IR", "kind": "company", "status": "SUCCESS", "text": "Q2 earnings and guidance"}],
    })

    assert client.responses.calls == 3
    assert result["company_signals"][0]["ticker"] == "NVDA"
    assert result["company_signals"][0]["stance"] == "等待"


def test_company_signal_guard_caps_focus_and_rejects_unknown_tickers():
    signals = [
        {"ticker": ticker, "stance": "关注", "brief": "中文结论"}
        for ticker in ("NVDA", "MSFT", "JPM", "XOM", "AAPL", "FAKE")
    ]
    snapshot = {
        ticker: {"price": 100, "day_change_pct": -2, "volatility_20_pct": 2}
        for ticker in ("NVDA", "MSFT", "JPM", "XOM", "AAPL")
    }

    selected = OpenAIAnalyzer._limit_company_signals(signals, snapshot)

    assert len(selected) == 5
    assert sum(item["stance"] == "关注" for item in selected) == 4
    assert selected[-1]["stance"] == "等待"


def test_company_signal_guard_requires_stock_specific_pullback():
    signals = [{"ticker": "MSFT", "stance": "关注", "brief": "中文结论"}]
    snapshot = {"MSFT": {"price": 100, "day_change_pct": -0.4, "volatility_20_pct": 2}}

    selected = OpenAIAnalyzer._limit_company_signals(signals, snapshot)

    assert selected[0]["stance"] == "等待"


def test_company_signal_guard_fills_eight_neutral_watch_slots_from_real_market_data():
    tickers = ("NVDA", "MSFT", "JPM", "XOM", "AAPL", "WMT", "AMZN", "LLY")
    snapshot = {
        ticker: {
            "price": 100 + index, "day_change_pct": -index / 10,
            "change_5d_pct": index / 5, "above_ma20": index % 2 == 0,
        }
        for index, ticker in enumerate(tickers, 1)
    }

    selected = OpenAIAnalyzer._limit_company_signals(
        [{"ticker": "NVDA", "stance": "等待", "brief": "等待公司新增信息确认。"}],
        snapshot,
        allowed_tickers=tickers,
    )

    assert len(selected) == 8
    assert len({item["ticker"] for item in selected}) == 8
    assert all(item["stance"] in {"关注", "等待", "回避"} for item in selected)
    assert "公司级增量信息不足" in selected[-1]["brief"]
    risks = [item["risk"] for item in selected if item.get("risk")]
    assert len(risks) == len(set(risks))
    triggers = [item["trigger"] for item in selected if item.get("trigger")]
    assert len(triggers) == len(set(triggers))
    assert all(len(item.get("brief", "")) <= 36 for item in selected)
    assert all(len(item.get("trigger", "")) <= 28 for item in selected)
    assert all(len(item.get("risk", "")) <= 26 for item in selected)


def test_mailer_uses_dated_url_and_authenticated_sender(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_DATE_OVERRIDE", "2026-08-21")
    monkeypatch.setenv("PUBLIC_REPORT_URL", "https://example.test/reports/")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_USERNAME", "original-sender@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("EMAIL_TO", "original-recipient@example.test")
    sent = []

    class SMTP:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def login(self, username, password):
            assert username == "original-sender@example.test"
            assert password == "secret"
        def send_message(self, message): sent.append(message)

    monkeypatch.setattr("news_finance_v2.live.smtplib.SMTP_SSL", lambda *args, **kwargs: SMTP())
    SMTPMailer(Settings.from_env(tmp_path)).send("<html><body>report</body></html>")

    message = sent[0]
    body = message.get_payload(decode=True).decode("utf-8")
    assert message["Subject"] == "NEWS FINANCE｜2026-08-21"
    assert message["From"] == "original-sender@example.test"
    assert message["To"] == "original-recipient@example.test"
    assert "https://example.test/reports/0821.html" in body
    assert ">8月21日最新版</a>" in body
    assert "公网最新版：" not in body
