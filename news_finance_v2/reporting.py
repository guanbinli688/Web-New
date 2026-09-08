from __future__ import annotations

import base64
import html
import json
import re
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlsplit

from .sources import COMPANY_NAMES, COMPANY_SYMBOLS


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


BLS_EVENT_TRANSLATIONS = {
    "Summer Youth Labor Force": "暑期青年劳动力",
    "State Employment and Unemployment (Monthly)": "各州就业与失业（月度）",
    "Access to and Use of Leave": "休假获取与使用情况",
    "Employment Projections and Occupational Outlook Handbook": "就业预测与《职业展望手册》",
    "Worker Displacement": "工人失业与岗位流失",
    "County Employment and Wages": "县级就业与工资",
    "Current Employment Statistics Preliminary Benchmark (National)": "当前就业统计初步基准（全国）",
    "Current Employment Statistics Preliminary Benchmark (State and Area)": "当前就业统计初步基准（州和地区）",
    "Job Openings and Labor Turnover Survey": "职位空缺与劳动力流动调查",
    "The Employment Situation": "就业形势报告",
    "Consumer Price Index": "消费者价格指数",
    "Producer Price Index": "生产者价格指数",
    "U.S. Import and Export Price Indexes": "美国进出口价格指数",
    "Real Earnings": "实际收入",
    "Employment Cost Index": "就业成本指数",
    "Productivity and Costs": "生产率与成本",
    "Employer Costs for Employee Compensation": "雇主员工薪酬成本",
    "Metropolitan Area Employment and Unemployment": "大都会地区就业与失业",
    "Metropolitan Area Employment and Unemployment (Monthly)": "大都会地区就业与失业（月度）",
    "Occupational Employment and Wage Statistics": "职业就业与工资统计",
    "Business Employment Dynamics": "企业就业动态",
}

SOURCE_LABELS = {
    "BLS": "美国劳工统计局", "BEA": "美国经济分析局",
    "Federal Reserve": "美联储", "Treasury Auctions": "美国财政部",
    "White House": "美国白宫", "US Census": "美国人口普查局",
    "EIA": "美国能源信息署", "Treasury Press": "美国财政部新闻",
    "USTR": "美国贸易代表办公室", "State Department": "美国国务院",
    "Federal Register": "美国联邦公报",
    "AP Business": "美联社商业", "CNBC Markets": "CNBC市场",
    "Financial Times": "英国金融时报", "Reuters Markets": "路透市场",
    "MarketWatch": "市场观察", "Yahoo Finance": "雅虎财经",
    "JPM IR": "摩根大通公告",
    "Walmart IR": "沃尔玛公告", "Microsoft IR": "微软公告",
    "Amazon IR": "亚马逊公告", "NVIDIA IR": "英伟达公告",
    "Meta IR": "Meta公告", "Salesforce IR": "Salesforce公告",
    "Oracle IR": "甲骨文公告", "Adobe IR": "奥多比公告",
    "CrowdStrike IR": "CrowdStrike公告", "Okta IR": "Okta公告",
    "Marvell IR": "迈威尔科技公告", "Dell IR": "戴尔公告",
    "Snowflake IR": "Snowflake公告", "Palo Alto Networks IR": "Palo Alto Networks公告",
    "Zscaler IR": "Zscaler公告", "lululemon IR": "lululemon公告",
    "Alphabet IR": "谷歌母公司公告", "Apple IR": "苹果公告",
    "Costco IR": "开市客公告", "ExxonMobil IR": "埃克森美孚公告",
    "TSMC IR": "台积电公告", "Broadcom IR": "博通公告",
    "Alibaba IR": "阿里巴巴公告", "Tencent IR": "腾讯公告",
    "Micron IR": "美光科技公告", "Tesla IR": "特斯拉公告",
    "Eli Lilly IR": "礼来公告", "UnitedHealth IR": "联合健康公告",
    "Caterpillar IR": "卡特彼勒公告", "Goldman Sachs IR": "高盛公告",
    "Visa IR": "维萨公告",
    "Michigan Surveys of Consumers": "密歇根大学消费者调查",
    "ISM": "美国供应管理协会",
    "ISM PMI Calendar": "美国供应管理协会",
    "Federal Reserve Next Month": "美联储",
    "New York Fed Indicators": "纽约联储日历",
    "New York Fed Indicators Next Month": "纽约联储日历",
    "NYSE Holidays": "纽约证券交易所",
    "HubSpot IR": "HubSpot公告",
    "Lennar IR": "Lennar公告",
}

COMPANY_LABELS = {
    "JPM": "摩根大通", "JPMORGAN": "摩根大通", "WMT": "沃尔玛",
    "WALMART": "沃尔玛", "MSFT": "微软", "MICROSOFT": "微软",
    "AMZN": "亚马逊", "AMAZON": "亚马逊", "NVDA": "英伟达",
    "NVIDIA": "英伟达", "TSM": "台积电", "TSMC": "台积电",
    "AVGO": "博通", "BROADCOM": "博通", "MU": "美光科技", "MICRON": "美光科技",
    "GOOGL": "谷歌", "ALPHABET": "谷歌", "AAPL": "苹果", "APPLE": "苹果",
    "COST": "开市客", "COSTCO": "开市客", "XOM": "埃克森美孚",
    "EXXONMOBIL": "埃克森美孚", "BABA": "阿里巴巴", "ALIBABA": "阿里巴巴",
    "TCEHY": "腾讯", "TENCENT": "腾讯", "TSLA": "特斯拉", "TESLA": "特斯拉",
    "LLY": "礼来", "UNH": "联合健康", "CAT": "卡特彼勒",
    "GS": "高盛", "V": "维萨", "VISA": "维萨",
}

DIRECTION_LABELS = {
    "UP": "看涨", "DOWN": "看跌", "NEUTRAL": "中性",
    "OUTPERFORM": "有望跑赢", "UNDERPERFORM": "可能跑输",
}


LANG_CODES = ("zh_tw", "en", "bg", "ru", "ja", "ko", "fr", "de", "es", "th")

LANG_OPTIONS = (
    ("zh", "中文简体"),
    ("zh_tw", "中文繁體"),
    ("en", "English"),
    ("bg", "Български"),
    ("ru", "Русский"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("es", "Español"),
    ("th", "ไทย"),
)

DIRECTION_LABELS_MULTI = {
    "UP": {
        "zh_tw": "看漲", "en": "Bullish", "bg": "Бичи", "ru": "Бычий",
        "ja": "強気", "ko": "강세", "fr": "Haussier", "de": "Bullisch",
        "es": "Alcista", "th": "ขาขึ้น",
    },
    "DOWN": {
        "zh_tw": "看跌", "en": "Bearish", "bg": "Мечи", "ru": "Медвежий",
        "ja": "弱気", "ko": "약세", "fr": "Baissier", "de": "Bärisch",
        "es": "Bajista", "th": "ขาลง",
    },
    "NEUTRAL": {
        "zh_tw": "中性", "en": "Neutral", "bg": "Неутрално", "ru": "Нейтрально",
        "ja": "中立", "ko": "중립", "fr": "Neutre", "de": "Neutral",
        "es": "Neutral", "th": "เป็นกลาง",
    },
    "OUTPERFORM": {
        "zh_tw": "有望跑贏", "en": "Outperform", "bg": "По-добро представяне", "ru": "Опережать",
        "ja": "アウトパフォーム", "ko": "시장수익률 상회", "fr": "Surperformance", "de": "Outperform",
        "es": "Superar al mercado", "th": "ดีกว่าตลาด",
    },
    "UNDERPERFORM": {
        "zh_tw": "可能跑輸", "en": "Underperform", "bg": "По-слабо представяне", "ru": "Отставать",
        "ja": "アンダーパフォーム", "ko": "시장수익률 하회", "fr": "Sous-performance", "de": "Underperform",
        "es": "Rendir por debajo", "th": "ต่ำกว่าตลาด",
    },
}

UI_I18N = {
    "mast_subtitle": {
        "zh_tw": "全球宏觀事件驅動投資分析 · Daily Investment Briefing",
        "en": "Global Event-Driven Investment Research · Daily Investment Briefing",
        "bg": "Глобален инвестиционен анализ, движен от събития · Daily Investment Briefing",
        "ru": "Глобальный событийный инвестиционный анализ · Daily Investment Briefing",
        "ja": "グローバル・イベントドリブン投資分析 · Daily Investment Briefing",
        "ko": "글로벌 이벤트 드리븐 투자 분석 · Daily Investment Briefing",
        "fr": "Analyse d’investissement mondiale axée sur les événements · Daily Investment Briefing",
        "de": "Globale ereignisgetriebene Investmentanalyse · Daily Investment Briefing",
        "es": "Análisis global de inversión impulsado por eventos · Daily Investment Briefing",
        "th": "การวิเคราะห์การลงทุนทั่วโลกแบบขับเคลื่อนด้วยเหตุการณ์ · Daily Investment Briefing",
    },
    "section_direction": {
        "zh_tw": "一｜市場定調", "en": "1 | Market Tone", "bg": "1 | Пазарна посока",
        "ru": "1 | Направление рынка", "ja": "1｜本日の投資方針", "ko": "1 | 오늘의 투자 방향",
        "fr": "1 | Orientation du marché", "de": "1 | Marktrichtung",
        "es": "1 | Dirección del mercado", "th": "1 | ทิศทางตลาดวันนี้",
    },
    "section_action": {
        "zh_tw": "二｜策略動作", "en": "2 | Strategy Actions", "bg": "2 | План за действия",
        "ru": "2 | План действий", "ja": "2｜具体的な対応", "ko": "2 | 구체적 대응",
        "fr": "2 | Plan d’action", "de": "2 | Handlungsplan",
        "es": "2 | Plan de acción", "th": "2 | แผนการดำเนินการ",
    },
    "section_calendar": {
        "zh_tw": "三｜關鍵日曆", "en": "3 | Key Calendar", "bg": "3 | Календар за 14 дни",
        "ru": "3 | Календарь на 14 дней", "ja": "3｜今後14日間の重要日程", "ko": "3 | 향후 14일 주요 일정",
        "fr": "3 | Calendrier des 14 prochains jours", "de": "3 | 14-Tage-Kalender",
        "es": "3 | Calendario de 14 días", "th": "3 | ปฏิทินสำคัญ 14 วัน",
    },
    "section_flow": {
        "zh_tw": "四｜資金路徑", "en": "4 | Capital Path", "bg": "4 | Капиталови потоци и логика",
        "ru": "4 | Потоки капитала и логика", "ja": "4｜資金フローと投資ロジック", "ko": "4 | 자금 흐름과 투자 논리",
        "fr": "4 | Flux de capitaux et logique", "de": "4 | Kapitalflüsse und Logik",
        "es": "4 | Flujos de capital y lógica", "th": "4 | กระแสเงินทุนและตรรกะการลงทุน",
    },
    "section_equity": {
        "zh_tw": "五｜個股雷達", "en": "5 | Equity Radar", "bg": "5 | Компании на фокус",
        "ru": "5 | Компании в фокусе", "ja": "5｜注目企業", "ko": "5 | 주요 기업 전망",
        "fr": "5 | Sociétés à surveiller", "de": "5 | Aktien-Watchlist",
        "es": "5 | Empresas a seguir", "th": "5 | บริษัทที่ต้องจับตา",
    },
    "section_market": {
        "zh_tw": "六｜事件焦點", "en": "6 | Event Focus", "bg": "6 | Какво търгува пазарът",
        "ru": "6 | Что торгует рынок", "ja": "6｜市場が織り込むテーマ", "ko": "6 | 시장이 거래하는 테마",
        "fr": "6 | Ce que traite le marché", "de": "6 | Was der Markt handelt",
        "es": "6 | Qué está negociando el mercado", "th": "6 | สิ่งที่ตลาดกำลังซื้อขาย",
    },
    "section_forecast": {
        "zh_tw": "七｜預測驗證", "en": "7 | Forecast Validation", "bg": "7 | Прогноза и проверка",
        "ru": "7 | Прогноз и проверка", "ja": "7｜予測と検証", "ko": "7 | 전망과 검증",
        "fr": "7 | Prévisions et validation", "de": "7 | Prognose und Überprüfung",
        "es": "7 | Pronóstico y validación", "th": "7 | การคาดการณ์และการตรวจสอบ",
    },
    "watch": {
        "zh_tw": "觀察", "en": "Watch", "bg": "Наблюдение", "ru": "Наблюдать",
        "ja": "監視", "ko": "관찰", "fr": "Surveiller", "de": "Beobachten",
        "es": "Vigilar", "th": "เฝ้าดู",
    },
    "prepare": {
        "zh_tw": "準備", "en": "Prepare", "bg": "Подготовка", "ru": "Подготовить",
        "ja": "準備", "ko": "준비", "fr": "Préparer", "de": "Vorbereiten",
        "es": "Preparar", "th": "เตรียม",
    },
    "avoid": {
        "zh_tw": "規避", "en": "Avoid", "bg": "Избягване / Намаляване на риска",
        "ru": "Избегать / Снизить риск", "ja": "回避 / リスク低減", "ko": "회피 / 위험 축소",
        "fr": "Éviter / Réduire le risque", "de": "Meiden / Risiko reduzieren",
        "es": "Evitar / Reducir riesgo", "th": "หลีกเลี่ยง / ลดความเสี่ยง",
    },
    "driver": {
        "zh_tw": "驅動", "en": "Driver", "bg": "Двигател", "ru": "Драйвер",
        "ja": "起点", "ko": "출발점", "fr": "Moteur", "de": "Treiber",
        "es": "Impulsor", "th": "ปัจจัยขับเคลื่อน",
    },
    "transmission": {
        "zh_tw": "路徑", "en": "Path", "bg": "Предаване", "ru": "Передача",
        "ja": "波及", "ko": "전이", "fr": "Transmission", "de": "Übertragung",
        "es": "Transmisión", "th": "การส่งผ่าน",
    },
    "outcome": {
        "zh_tw": "落點", "en": "Outcome", "bg": "Резултат", "ru": "Результат",
        "ja": "結果", "ko": "결과", "fr": "Résultat", "de": "Ergebnis",
        "es": "Resultado", "th": "ผลลัพธ์",
    },
    "investment_action": {
        "zh_tw": "動作", "en": "Action", "bg": "Действие", "ru": "Действие",
        "ja": "投資対応", "ko": "투자 대응", "fr": "Action", "de": "Maßnahme",
        "es": "Acción", "th": "การดำเนินการ",
    },
    "prediction_note": {
        "zh_tw": "判斷生成後即凍結，後續僅以真實市場結果檢驗；不因結果倒推或修改原始結論。",
        "en": "Forecasts are frozen at generation and evaluated only against realized market outcomes; conclusions are not revised retroactively.",
        "bg": "Прогнозите се фиксират при създаване и се оценяват само спрямо реалните пазарни резултати; не се променят със задна дата.",
        "ru": "Прогнозы фиксируются при создании и проверяются только по фактическому рынку; задним числом выводы не меняются.",
        "ja": "予測は生成時点で固定し、その後は実際の市場結果だけで検証する。結果に合わせて過去の判断は変更しない。",
        "ko": "전망은 생성 시점에 고정하며 실제 시장 결과로만 검증한다. 결과에 맞춰 기존 판단을 소급 수정하지 않는다.",
        "fr": "Les prévisions sont figées à leur création et évaluées uniquement sur les résultats réels du marché, sans révision a posteriori.",
        "de": "Prognosen werden bei Erstellung eingefroren und nur anhand realer Marktergebnisse geprüft; rückwirkende Änderungen sind ausgeschlossen.",
        "es": "Las previsiones se congelan al generarse y se evalúan solo con resultados reales del mercado; no se revisan retrospectivamente.",
        "th": "การคาดการณ์จะถูกตรึงเมื่อสร้างและตรวจสอบด้วยผลตลาดจริงเท่านั้น โดยไม่แก้ข้อสรุปย้อนหลังตามผลลัพธ์",
    },
    "data_integrity": {
        "zh_tw": "資料完整性", "en": "Data Integrity", "bg": "Цялост на данните", "ru": "Целостность данных",
        "ja": "データ完全性", "ko": "데이터 무결성", "fr": "Intégrité des données",
        "de": "Datenintegrität", "es": "Integridad de datos", "th": "ความสมบูรณ์ของข้อมูล",
    },
    "coverage": {
        "zh_tw": "覆蓋率", "en": "Coverage", "bg": "Покритие", "ru": "Охват", "ja": "カバレッジ",
        "ko": "커버리지", "fr": "Couverture", "de": "Abdeckung", "es": "Cobertura", "th": "ความครอบคลุม",
    },
    "frozen": {
        "zh_tw": "凍結", "en": "Frozen", "bg": "Фиксирани", "ru": "Зафиксировано", "ja": "固定",
        "ko": "고정", "fr": "Figées", "de": "Eingefroren", "es": "Congeladas", "th": "ตรึง",
    },
    "sources": {
        "zh_tw": "來源", "en": "Sources", "bg": "Източници", "ru": "Источники", "ja": "情報源",
        "ko": "출처", "fr": "Sources", "de": "Quellen", "es": "Fuentes", "th": "แหล่งข้อมูล",
    },
    "table_horizon": {
        "zh_tw": "週期", "en": "Horizon", "bg": "Хоризонт", "ru": "Горизонт", "ja": "期間",
        "ko": "기간", "fr": "Horizon", "de": "Horizont", "es": "Horizonte", "th": "กรอบเวลา",
    },
    "table_target": {
        "zh_tw": "標的", "en": "Target", "bg": "Обект", "ru": "Объект", "ja": "対象",
        "ko": "대상", "fr": "Cible", "de": "Ziel", "es": "Objetivo", "th": "เป้าหมาย",
    },
    "table_view": {
        "zh_tw": "方向", "en": "Direction", "bg": "Оценка", "ru": "Оценка", "ja": "判断",
        "ko": "판단", "fr": "Vue", "de": "Einschätzung", "es": "Visión", "th": "มุมมอง",
    },
    "table_probability": {
        "zh_tw": "機率", "en": "Probability", "bg": "Вероятност", "ru": "Вероятность", "ja": "確率",
        "ko": "확률", "fr": "Probabilité", "de": "Wahrscheinlichkeit", "es": "Probabilidad", "th": "ความน่าจะเป็น",
    },
    "table_thesis": {
        "zh_tw": "邏輯", "en": "Thesis", "bg": "Теза", "ru": "Тезис", "ja": "ロジック",
        "ko": "논리", "fr": "Thèse", "de": "These", "es": "Tesis", "th": "เหตุผล",
    },
    "table_invalidation": {
        "zh_tw": "失效", "en": "Invalidation", "bg": "Условие за невалидност", "ru": "Условие отмены",
        "ja": "無効化条件", "ko": "무효 조건", "fr": "Invalidation", "de": "Ungültigkeitsbedingung",
        "es": "Invalidación", "th": "เงื่อนไขยกเลิก",
    },
    "footer_framework": {
        "zh_tw": "官方資料 · 公司公告 · 跨資產驗證 · 事件推演 · 歷史參照 · 事後復盤",
        "en": "Official Data · Company Filings · Cross-Asset Validation · Event Analysis · Historical Context · Review",
        "bg": "Официални данни · Корпоративни отчети · Междупазарна проверка · Анализ на събития · Исторически контекст · Преглед",
        "ru": "Официальные данные · Отчётность компаний · Межрыночная проверка · Анализ событий · Исторический контекст · Разбор",
        "ja": "公式データ · 企業開示 · クロスアセット検証 · イベント分析 · 過去比較 · 事後検証",
        "ko": "공식 데이터 · 기업 공시 · 크로스애셋 검증 · 이벤트 분석 · 역사 비교 · 사후 검토",
        "fr": "Données officielles · Publications d’entreprises · Validation multi-actifs · Analyse d’événements · Contexte historique · Revue",
        "de": "Offizielle Daten · Unternehmensmeldungen · Cross-Asset-Prüfung · Ereignisanalyse · Historischer Kontext · Review",
        "es": "Datos oficiales · Comunicados corporativos · Validación multiactivo · Análisis de eventos · Contexto histórico · Revisión",
        "th": "ข้อมูลทางการ · การเปิดเผยข้อมูลบริษัท · การตรวจสอบข้ามสินทรัพย์ · วิเคราะห์เหตุการณ์ · บริบทในอดีต · ทบทวน",
    },
    "disclosure": {
        "zh_tw": "獨立投資研究，非美國政府網站。本報告僅用於研究與學習，不構成投資建議、收益保證或證券買賣承諾。",
        "en": "Independent investment research; not a U.S. government website. For research and educational use only; not investment advice, a return guarantee, or an offer to buy or sell securities.",
        "bg": "Независимо инвестиционно изследване; не е сайт на правителството на САЩ. Само за изследователски и образователни цели; не е инвестиционен съвет или гаранция за доходност.",
        "ru": "Независимое инвестиционное исследование; это не сайт правительства США. Материал предназначен только для исследования и обучения и не является инвестиционной рекомендацией или гарантией доходности.",
        "ja": "独立した投資調査であり、米国政府サイトではありません。研究・学習目的のみで、投資助言、収益保証、証券売買の勧誘ではありません。",
        "ko": "독립 투자 리서치이며 미국 정부 웹사이트가 아닙니다. 연구·학습 목적이며 투자 자문, 수익 보장 또는 증권 매매 권유가 아닙니다.",
        "fr": "Recherche d’investissement indépendante, non affiliée au gouvernement américain. À des fins de recherche et d’apprentissage uniquement; ne constitue ni un conseil en investissement ni une garantie de rendement.",
        "de": "Unabhängige Investmentanalyse, keine Website der US-Regierung. Nur zu Forschungs- und Lernzwecken; keine Anlageberatung, Renditegarantie oder Aufforderung zum Wertpapierhandel.",
        "es": "Investigación de inversión independiente; no es un sitio del Gobierno de EE. UU. Solo para investigación y aprendizaje; no constituye asesoramiento de inversión ni garantía de rentabilidad.",
        "th": "งานวิจัยการลงทุนอิสระ ไม่ใช่เว็บไซต์ของรัฐบาลสหรัฐฯ จัดทำเพื่อการศึกษาและการเรียนรู้เท่านั้น ไม่ใช่คำแนะนำการลงทุนหรือการรับประกันผลตอบแทน",
    },
}

WEEKDAYS_MULTI = {
    "zh_tw": ("一", "二", "三", "四", "五", "六", "日"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "bg": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"),
    "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
    "ja": ("月", "火", "水", "木", "金", "土", "日"),
    "ko": ("월", "화", "수", "목", "금", "토", "일"),
    "fr": ("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"),
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "es": ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"),
    "th": ("จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."),
}

MONTHS_EN = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _encode_i18n(values: dict) -> str:
    clean = {code: str(value) for code, value in (values or {}).items() if str(value or "").strip()}
    if not clean:
        return ""
    raw = json.dumps(clean, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _i18n_attr(values: dict) -> str:
    encoded = _encode_i18n(values)
    return f" data-i18n='{encoded}'" if encoded else ""


def _i18n_label_attr(values: dict) -> str:
    encoded = _encode_i18n(values)
    return f" data-i18n-label='{encoded}'" if encoded else ""


def _field_i18n(item: dict, key: str) -> dict:
    item = item or {}
    values = {}
    base = item.get(key)
    for code in LANG_CODES:
        value = item.get(f"{key}_{code}")
        if value is None and code == "en":
            value = item.get(f"{key}_en")
        if value is None:
            continue
        values[code] = value
    # English is the best fallback for international readers when a newly
    # generated report predates the full multilingual prompt.
    if "en" not in values and base is not None:
        values["en"] = base
    return values


def _static_i18n(key: str) -> dict:
    return dict(UI_I18N.get(key, {}))


def _source_label_en(source_name: str) -> str:
    source_name = str(source_name or "").strip()
    if source_name.endswith(" 新闻"):
        return f"{source_name[:-3]} News"
    if source_name.endswith(" 行情"):
        return f"{source_name[:-3]} Market Data"
    aliases = {
        "BLS": "U.S. Bureau of Labor Statistics",
        "BEA": "U.S. Bureau of Economic Analysis",
        "Federal Reserve": "Federal Reserve",
        "Treasury Auctions": "U.S. Treasury",
        "White House": "White House",
        "US Census": "U.S. Census Bureau",
        "EIA": "U.S. Energy Information Administration",
        "Treasury Press": "U.S. Treasury",
        "USTR": "U.S. Trade Representative",
        "State Department": "U.S. Department of State",
        "Federal Register": "Federal Register",
        "AP Business": "AP Business",
        "CNBC Markets": "CNBC Markets",
        "Financial Times": "Financial Times",
        "Reuters Markets": "Reuters Markets",
        "MarketWatch": "MarketWatch",
        "Yahoo Finance": "Yahoo Finance",
    }
    return aliases.get(source_name, source_name)


def _source_i18n(source_name: str) -> dict:
    # Proper source names remain in their common English form for all non-Chinese locales.
    common = _source_label_en(source_name)
    return {code: common for code in LANG_CODES}


def _event_title_i18n(raw_title) -> dict:
    normalized = " ".join(str(raw_title or "").split())
    common = normalized if normalized else "Official Data Release"
    return {code: common for code in LANG_CODES}

def _human_source_url(source_name: str, source_url: str | None, ticker: str = "") -> str | None:
    """Expose reader-facing pages, not RSS/XML/JSON/API endpoints."""
    name = str(source_name or "").strip()
    url = str(source_url or "").strip()
    symbol = str(ticker or "").strip().upper()

    if name.endswith(" 新闻") and symbol:
        return f"https://finance.yahoo.com/quote/{symbol}/news/"
    if name.endswith(" 行情") and symbol:
        return f"https://finance.yahoo.com/quote/{symbol}/"

    if not re.match(r"^https?://", url, flags=re.I):
        return None

    sec_cik = re.search(r"/CIK0*(\d+)\.json(?:[?#]|$)", url, flags=re.I)
    if sec_cik and "sec.gov" in url.lower():
        cik = sec_cik.group(1)
        return f"https://www.sec.gov/edgar/browse/?CIK={cik}&owner=exclude&action=getcompany"

    try:
        parsed = urlsplit(url)
    except ValueError:
        return None

    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    machine_path = bool(
        re.search(r"\.(?:json|xml|rss|atom)(?:$|/)", path)
        or re.search(r"/(?:rss|feed|feeds|atom|api)(?:/|$)", path)
        or "rss/2.0/headline" in url.lower()
    )
    machine_host = host.startswith(("api.", "data.", "feeds."))

    # Company/website feeds are safe to redirect to the site's human-facing root.
    if machine_path and not machine_host and parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"

    # Raw data/API endpoints stay as a visible source label but are not clickable.
    if machine_host or machine_path:
        return None

    return url


def _has_chinese(value) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))


def translate_event_title(title) -> str:
    normalized = " ".join(str(title or "").split())
    if normalized in BLS_EVENT_TRANSLATIONS:
        return BLS_EVENT_TRANSLATIONS[normalized]
    return normalized if _has_chinese(normalized) else "美国劳工统计局数据发布"


def _specific_calendar_title(raw_title, raw_source: str) -> str:
    """Render company calendar items with an explicit company name."""
    normalized = " ".join(str(raw_title or "").split()).strip()
    source_name = str(raw_source or "").strip()
    ticker = COMPANY_SYMBOLS.get(source_name)
    vague_markers = ("大型科技公司", "大型公司", "重点公司", "某公司")

    if not ticker:
        if any(marker in normalized for marker in vague_markers):
            return ""
        return translate_event_title(normalized)

    company = COMPANY_NAMES.get(ticker) or COMPANY_LABELS.get(ticker) or ticker
    lowered = normalized.lower()
    is_named = (
        company in normalized
        or ticker.lower() in lowered
        or source_name.removesuffix(" IR").lower() in lowered
    )
    if _has_chinese(normalized) and is_named and not any(marker in normalized for marker in vague_markers):
        return normalized
    if any(word in lowered for word in ("earnings", "financial results", "quarterly results", "财报", "业绩")):
        return f"{company}财报"
    if "investor" in lowered or "投资者" in normalized:
        return f"{company}投资者活动"
    if "guidance" in lowered or "指引" in normalized:
        return f"{company}业绩指引更新"
    if normalized and _has_chinese(normalized) and not any(marker in normalized for marker in vague_markers):
        return f"{company}{normalized}"
    return f"{company}公司活动"


def _seal_data_uri() -> str:
    seal_path = Path(__file__).with_name("assets") / "department-state-seal.png"
    encoded = base64.b64encode(seal_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _logo() -> str:
    return '<span class="logo" role="img" aria-label="美国鹰正式徽标"></span>'


def _list(context, group: str, empty="等待确认"):
    base_actions = context.get("actions", {})
    zh_items = list(base_actions.get(group) or [])
    translated = {
        code: list((context.get(f"actions_{code}") or {}).get(group) or [])
        for code in LANG_CODES
    }
    values = []
    for index, item in enumerate(zh_items):
        i18n = {}
        for code in LANG_CODES:
            items = translated.get(code, [])
            if index < len(items):
                i18n[code] = items[index]
        values.append(f"<li{_i18n_attr(i18n)}>{esc(item)}</li>")
    return f"<ul>{''.join(values)}</ul>" if values else f"<p class='muted'>{esc(empty)}</p>"


def _horizons(context):
    items = context.get("horizons", [])[:3]
    defaults = ("3-5", "5-10", "10-15")
    cards = []
    for index, days in enumerate(defaults):
        item = items[index] if index < len(items) else {
            "days": days, "direction": "等待确认", "focus": [],
            "brief": "证据尚不足。", "risk": "等待新增数据",
        }
        display_days = str(item.get("days", days))
        display_days_compact = display_days.replace("-", "–")
        focus = " · ".join(str(x) for x in item.get("focus", [])[:5])

        time_i18n = {
            "zh_tw": f"{display_days_compact}日",
            "en": f"{display_days_compact}D",
            "bg": f"Следващи {display_days} дни",
            "ru": f"Следующие {display_days} дней",
            "ja": f"今後 {display_days} 日",
            "ko": f"향후 {display_days}일",
            "fr": f"Prochains {display_days} jours",
            "de": f"Nächste {display_days} Tage",
            "es": f"Próximos {display_days} días",
            "th": f"{display_days} วันข้างหน้า",
        }

        risk_i18n = {}
        prefixes = {
            "zh_tw": "失效條件：", "en": "Invalidation: ", "bg": "Условие за невалидност: ", "ru": "Условие отмены: ",
            "ja": "無効化条件：", "ko": "무효 조건: ", "fr": "Invalidation : ", "de": "Ungültig bei: ",
            "es": "Invalidación: ", "th": "เงื่อนไขยกเลิก: ",
        }
        risk_fields = _field_i18n(item, "risk")
        for code in LANG_CODES:
            if risk_fields.get(code):
                risk_i18n[code] = prefixes[code] + str(risk_fields[code])

        cards.append(
            f"""<div class="horizon">"""
            f"""<div class="horizon-time"{_i18n_attr(time_i18n)}>{esc(display_days_compact)}日</div>"""
            f"""<div class="horizon-direction"{_i18n_attr(_field_i18n(item, "direction"))}>{esc(item.get("direction", "等待确认"))}</div>"""
            f"""<div class="focus">{esc(focus)}</div>"""
            f"""<p{_i18n_attr(_field_i18n(item, "brief"))}>{esc(item.get("brief"))}</p>"""
            f"""<div class="risk"{_i18n_attr(risk_i18n)}>失效条件：{esc(item.get("risk", "等待确认"))}</div>"""
            f"""</div>"""
        )
    return "".join(cards)


def _calendar(context):
    by_date = {}
    ordered_events = sorted(
        (event for event in context.get("events", []) if isinstance(event, dict)),
        key=lambda event: (
            str(event.get("date", ""))[:10],
            str(event.get("title", "")),
        ),
    )
    for event in ordered_events:
        by_date.setdefault(str(event.get("date", ""))[:10], []).append(event)
    source_urls = {
        str(record.get("name") or ""): record.get("final_url") or record.get("url")
        for record in context.get("sources", [])
    }
    weekdays = "一二三四五六日"
    try:
        start = date.fromisoformat(str(context.get("report_date", ""))[:10])
    except ValueError:
        start = date.today()
    cells = []
    event_sequence = 0
    for offset in range(14):
        current = start + timedelta(days=offset)
        current_text = current.isoformat()
        body = []
        for event in by_date.get(current_text, []):
            raw_title = event.get("title")
            raw_source = str(event.get("source", "")).strip()
            title = _specific_calendar_title(raw_title, raw_source)
            if not title:
                continue
            event_sequence += 1
            source = SOURCE_LABELS.get(raw_source) or raw_source
            raw_url = event.get("url") or source_urls.get(raw_source)
            source_url = _human_source_url(raw_source, raw_url)
            if source and source_url:
                source_html = (
                    f"<small><a href='{esc(source_url)}' target='_blank' rel='noopener noreferrer'"
                    f"{_i18n_label_attr(_source_i18n(raw_source))}>{esc(source)}"
                    f"<span aria-hidden='true'>↗</span></a></small>"
                )
            elif source:
                source_html = f"<small{_i18n_attr(_source_i18n(raw_source))}>{esc(source)}</small>"
            else:
                source_html = ""
            category = str(event.get("category") or "").strip()
            event_class = " event-company" if category == "财报" or "IR" in raw_source else ""
            body.append(
                f"<div class='event{event_class}'><span>{event_sequence:02d}</span>"
                f"<strong{_i18n_attr(_event_title_i18n(title))}>{esc(title)}</strong>"
                f"{source_html}</div>"
            )
        if not body:
            if current.weekday() >= 5:
                empty_text = "周末｜无重大日程"
                empty_i18n = {
                    "zh_tw": "週末｜無重大日程", "en": "Weekend | No major events",
                    "bg": "Уикенд | Няма важни събития", "ru": "Выходной | Нет важных событий",
                    "ja": "週末｜重要日程なし", "ko": "주말 | 주요 일정 없음",
                    "fr": "Week-end | Aucun événement majeur", "de": "Wochenende | Keine wichtigen Termine",
                    "es": "Fin de semana | Sin eventos importantes", "th": "สุดสัปดาห์ | ไม่มีกำหนดการสำคัญ",
                }
            else:
                empty_text = "暂无重大市场日程"
                empty_i18n = {
                    "zh_tw": "暫無重大市場日程", "en": "No major market events",
                    "bg": "Няма важни пазарни събития", "ru": "Нет важных рыночных событий",
                    "ja": "重要な市場日程なし", "ko": "주요 시장 일정 없음",
                    "fr": "Aucun événement de marché majeur", "de": "Keine wichtigen Markttermine",
                    "es": "Sin eventos importantes de mercado", "th": "ไม่มีกำหนดการตลาดสำคัญ",
                }
            body.append(f"<div class='event-empty'{_i18n_attr(empty_i18n)}>{empty_text}</div>")

        date_i18n = {
            "zh_tw": f"{current.month}月{current.day}日",
            "en": f"{MONTHS_EN[current.month]} {current.day}",
            "bg": f"{current.day}.{current.month}",
            "ru": f"{current.day}.{current.month}",
            "ja": f"{current.month}月{current.day}日",
            "ko": f"{current.month}월 {current.day}일",
            "fr": f"{current.day}/{current.month}",
            "de": f"{current.day}.{current.month}.",
            "es": f"{current.day}/{current.month}",
            "th": f"{current.day}/{current.month}",
        }
        weekday_i18n = {
            code: WEEKDAYS_MULTI[code][current.weekday()]
            for code in LANG_CODES
        }
        cells.append(
            f"<div class='day'><div class='day-head'>"
            f"<h3{_i18n_attr(date_i18n)}>{current.month}月{current.day}日</h3>"
            f"<div class='weekday'{_i18n_attr(weekday_i18n)}>周{weekdays[current.weekday()]}</div>"
            f"</div>{''.join(body)}</div>"
        )
    return "".join(cells)


def _logic(context):
    flow_html = "".join(
        f"<div class='capital-route'><span class='flow-index'>{index:02d}</span>"
        f"<div class='route-pair'><strong>{esc(x.get('from'))}</strong><i>→</i><strong>{esc(x.get('to'))}</strong></div>"
        f"<p{_i18n_attr(_field_i18n(x, 'brief'))}>{esc(x.get('brief'))}</p></div>"
        for index, x in enumerate(context.get("flows", [])[:4], 1)
    ) or "<p class='muted'>本轮没有形成明确资金迁移方向。</p>"

    chain_html = "".join(
        f"<div class='transmission-row'><span class='transmission-index'>{index:02d}</span>"
        f"<div class='logic-step'><small{_i18n_attr(_static_i18n('driver'))}>驱动</small>"
        f"<strong{_i18n_attr(_field_i18n(x, 'cause'))}>{esc(x.get('cause'))}</strong></div>"
        f"<div class='logic-arrow'>→</div>"
        f"<div class='logic-step'><small{_i18n_attr(_static_i18n('transmission'))}>传导</small>"
        f"<span{_i18n_attr(_field_i18n(x, 'middle'))}>{esc(x.get('middle'))}</span></div>"
        f"<div class='logic-arrow'>→</div>"
        f"<div class='logic-step'><small{_i18n_attr(_static_i18n('outcome'))}>影响</small>"
        f"<span{_i18n_attr(_field_i18n(x, 'result'))}>{esc(x.get('result'))}</span></div>"
        f"<div class='logic-action'><small{_i18n_attr(_static_i18n('investment_action'))}>动作</small>"
        f"<span{_i18n_attr(_field_i18n(x, 'action'))}>{esc(x.get('action'))}</span></div>"
        f"</div>"
        for index, x in enumerate(context.get("logic", [])[:6], 1)
    ) or "<p class='muted'>等待更多交叉资产证据。</p>"
    return (
        "<div class='capital-map'>"
        "<div class='capital-column capital-routes'><div class='capital-subhead'>"
        "<span>配置迁移</span><small>ALLOCATION SHIFT</small></div>"
        f"<div class='capital-route-list'>{flow_html}</div></div>"
        "<div class='capital-column capital-transmission'><div class='capital-subhead'>"
        "<span>传导与动作</span><small>TRANSMISSION &amp; ACTION</small></div>"
        f"<div class='transmission-list'>{chain_html}</div></div></div>"
    )


def _source_cards(context, kind):
    source_records = context.get("sources", [])
    source_urls = {str(x.get("name")): x.get("url", "#") for x in source_records}
    curated = context.get("company_signals" if kind == "company" else "media_themes", [])
    curated_cards = []
    focus_count = 0
    limit = 8 if kind == "company" else 3

    for item in curated[:limit]:
        ticker = ""
        if kind == "company":
            brief = str(item.get("brief") or "").strip()
            if not _has_chinese(brief):
                continue
            ticker = str(item.get("ticker") or "").strip().upper()
            raw_company = str(item.get("company") or "").strip()
            raw_company_en = str(item.get("company_en") or "").strip()

            company = (
                COMPANY_NAMES.get(ticker)
                or COMPANY_LABELS.get(ticker)
                or (COMPANY_LABELS.get(raw_company.upper()) if raw_company else "")
                or raw_company
                or raw_company_en
                or ticker
            )
            title = f"{company}（{ticker}）" if ticker and company != ticker else company

            title_i18n = {}
            for code in LANG_CODES:
                translated_company = item.get(f"company_{code}")
                if not translated_company and code == "en":
                    translated_company = item.get("company_en")
                if translated_company:
                    tc = str(translated_company)
                    title_i18n[code] = f"{tc} ({ticker})" if ticker and ticker.upper() not in tc.upper() else tc

            label = str(item.get("stance") or item.get("signal") or "等待").strip()
            if label not in {"关注", "等待", "回避"}:
                label = "等待"
            if label == "关注" and focus_count >= 4:
                label = "等待"
            if label == "关注":
                focus_count += 1

            label_i18n = _field_i18n(item, "stance")
            if label == "等待":
                label_i18n["en"] = "WAIT"
            elif label == "回避":
                label_i18n["en"] = "AVOID"
            elif label == "关注":
                label_i18n["en"] = "WATCH"

            trigger = str(item.get("trigger") or "").strip()
            risk = str(item.get("risk") or "").strip()

            source_names = []
            for record in source_records:
                record_name = str(record.get("name", ""))
                if record.get("symbol") == ticker or COMPANY_SYMBOLS.get(record_name) == ticker:
                    source_names.append(record_name)
            source_names = list(dict.fromkeys(source_names))[:2]
            if not source_names and ticker:
                market_source = f"{ticker} 行情"
                source_names = [market_source]
                source_urls[market_source] = f"https://finance.yahoo.com/quote/{ticker}/"
        else:
            title = str(item.get("title") or "").strip()
            title_i18n = _field_i18n(item, "title")
            label = item.get("tone") or "中性"
            label_i18n = _field_i18n(item, "tone")
            brief = str(item.get("brief") or "").strip()
            if not title or not brief or not _has_chinese(brief):
                continue
            impact = str(item.get("impact") or "").strip()
            source_names = [str(x) for x in item.get("sources", [])]

        source_links = []
        for source_name in [x for x in source_names if x]:
            source_label = SOURCE_LABELS.get(
                source_name,
                f"{source_name[:-3]}动态新闻" if source_name.endswith(" 新闻")
                else (f"{source_name[:-3]}行情" if source_name.endswith(" 行情") else source_name),
            )
            raw_url = source_urls.get(source_name)
            source_url = _human_source_url(source_name, raw_url, ticker)
            label_attr = _i18n_label_attr(_source_i18n(source_name))

            if source_url:
                # Preserve legacy test shape: >CNBC市场<span...
                source_links.append(
                    f"<a href='{esc(source_url)}' target='_blank' rel='noopener noreferrer'{label_attr}>"
                    f"{esc(source_label)}<span aria-hidden='true'>↗</span></a>"
                )
            else:
                source_links.append(
                    f"<span class='source-static'{label_attr}>{esc(source_label)}</span>"
                )

        links_html = "".join(source_links)
        source_links_html = (
            f"<div class='source-links'>{links_html}</div>"
            if links_html else ""
        )
        details = ""

        if kind == "company":
            snapshot = context.get("stock_snapshot", {}).get(ticker, {})
            if snapshot:
                price_text = f"{float(snapshot.get('price', 0)):.2f}"
                day_text = f"{float(snapshot.get('day_change_pct', 0)):+.2f}%"
                volatility_text = f"{float(snapshot.get('volatility_20_pct', 0)):.2f}%"
                meta_i18n = {
                    "zh_tw": f"現價 ${price_text}　當日 {day_text}　20日波動 {volatility_text}",
                    "en": f"Price ${price_text}　Day {day_text}　20D Vol {volatility_text}",
                    "bg": f"Цена ${price_text}　Ден {day_text}　20Д вол. {volatility_text}",
                    "ru": f"Цена ${price_text}　День {day_text}　20Д вол. {volatility_text}",
                    "ja": f"価格 ${price_text}　当日 {day_text}　20日ボラ {volatility_text}",
                    "ko": f"현재가 ${price_text}　당일 {day_text}　20일 변동성 {volatility_text}",
                    "fr": f"Cours ${price_text}　Jour {day_text}　Vol. 20j {volatility_text}",
                    "de": f"Kurs ${price_text}　Tag {day_text}　20T-Vol. {volatility_text}",
                    "es": f"Precio ${price_text}　Día {day_text}　Vol. 20d {volatility_text}",
                    "th": f"ราคา ${price_text}　วันนี้ {day_text}　ความผันผวน 20วัน {volatility_text}",
                }
                details += f"<div class='stock-meta'{_i18n_attr(meta_i18n)}>现价 ${price_text}　当日 {day_text}　20日波动 {volatility_text}</div>"

            if _has_chinese(trigger):
                prefixes = {
                    "zh_tw": "觸發：", "en": "Trigger: ", "bg": "Условие за вход: ", "ru": "Условие входа: ",
                    "ja": "発動条件：", "ko": "트리거 조건: ", "fr": "Déclencheur : ", "de": "Trigger: ",
                    "es": "Activador: ", "th": "เงื่อนไขกระตุ้น: ",
                }
                vals = _field_i18n(item, "trigger")
                full = {code: prefixes[code] + str(vals[code]) for code in LANG_CODES if vals.get(code)}
                details += f"<div class='card-note'{_i18n_attr(full)}>触发：{esc(trigger)}</div>"

            if _has_chinese(risk):
                prefixes = {
                    "zh_tw": "失效：", "en": "Invalidation: ", "bg": "Риск за тезата: ", "ru": "Риск отмены тезиса: ",
                    "ja": "失効リスク：", "ko": "무효화 위험: ", "fr": "Risque d’invalidation : ", "de": "Invalidierungsrisiko: ",
                    "es": "Riesgo de invalidación: ", "th": "ความเสี่ยงต่อการยกเลิกมุมมอง: ",
                }
                vals = _field_i18n(item, "risk")
                full = {code: prefixes[code] + str(vals[code]) for code in LANG_CODES if vals.get(code)}
                details += f"<div class='card-risk'{_i18n_attr(full)}>失效：{esc(risk)}</div>"
        elif _has_chinese(impact):
            prefixes = {
                "zh_tw": "資產影響：", "en": "Asset Impact: ", "bg": "Ефект върху активите: ", "ru": "Влияние на активы: ",
                "ja": "資産影響：", "ko": "자산 영향: ", "fr": "Impact sur les actifs : ", "de": "Asset-Wirkung: ",
                "es": "Impacto en activos: ", "th": "ผลกระทบต่อสินทรัพย์: ",
            }
            vals = _field_i18n(item, "impact")
            full = {code: prefixes[code] + str(vals[code]) for code in LANG_CODES if vals.get(code)}
            details = f"<div class='card-note'{_i18n_attr(full)}>资产影响：{esc(impact)}</div>"

        if kind == "company":
            signal_class = "focus" if label == "关注" else "avoid" if label == "回避" else "wait"
            card_class = f"signal-{signal_class}"
        else:
            tone_class = {
                "积极": "tone-positive",
                "谨慎": "tone-cautious",
                "中性": "tone-neutral",
            }.get(str(label), "tone-neutral")
            card_class = tone_class

        curated_cards.append(
            f"<div class='source-card {card_class}'>"
            f"<div class='card-label'{_i18n_attr(label_i18n)}>{esc(label)}</div>"
            f"<h3{_i18n_attr(title_i18n)}>{esc(title)}</h3>"
            f"<p{_i18n_attr(_field_i18n(item, 'brief'))}>{esc(brief)}</p>"
            f"{details}{source_links_html}</div>"
        )

    if curated_cards:
        return "".join(curated_cards)
    empty = "本轮未形成可执行的公司信号，原始材料不直接展示。" if kind == "company" else "本轮未形成值得交易的市场主题。"
    return f"<p class='muted'>{empty}</p>"


def _predictions(context):
    cards = []
    for item in context.get("display_predictions", context.get("predictions", [])):
        try:
            probability = f"{float(item.get('probability', 0)):.0%}"
        except (TypeError, ValueError):
            probability = "—"

        raw_direction = str(item.get("direction", "")).upper()
        direction = DIRECTION_LABELS.get(raw_direction, item.get("direction"))
        direction_i18n = DIRECTION_LABELS_MULTI.get(raw_direction, {})
        direction_text = str(direction or "")

        if raw_direction in {"UP", "OUTPERFORM"} or "看涨" in direction_text or "跑赢" in direction_text:
            direction_class = "direction-up"
        elif raw_direction in {"DOWN", "UNDERPERFORM"} or "看跌" in direction_text or "跑输" in direction_text:
            direction_class = "direction-down"
        else:
            direction_class = "direction-neutral"

        horizon = str(item.get("horizon_days") or "")
        horizon_i18n = {code: f"{horizon}D" for code in LANG_CODES}
        cards.append(
            f"<article class='forecast-card {direction_class}'>"
            f"<div class='forecast-card-top'><span class='forecast-horizon'{_i18n_attr(horizon_i18n)}>{esc(horizon)}日</span>"
            f"<strong class='forecast-target'>{esc(item.get('target'))}</strong>"
            f"<span class='direction-pill {direction_class}'{_i18n_attr(direction_i18n)}>{esc(direction)}</span></div>"
            f"<div class='forecast-probability'><strong>{probability}</strong><small>判断概率</small></div>"
            f"<div class='forecast-reason'><small>核心逻辑</small>"
            f"<p{_i18n_attr(_field_i18n(item, 'thesis'))}>{esc(item.get('thesis'))}</p></div>"
            f"<div class='forecast-invalidation'><small>失效条件</small>"
            f"<p{_i18n_attr(_field_i18n(item, 'invalidation'))}>{esc(item.get('invalidation'))}</p></div>"
            f"</article>"
        )
    current_html = (
        "<div class='forecast-cards'>" + "".join(cards) + "</div>"
    ) if cards else "<p class='muted'>当前证据不足，暂不形成方向性预测。</p>"

    history = list(context.get("prediction_history") or [])[:12]
    verified = [item for item in history if item.get("correct") is not None]
    correct = sum(bool(item.get("correct")) for item in verified)
    hit_rate = f"{correct / len(verified):.0%}" if verified else "—"
    brier_values = []
    for item in verified:
        try:
            brier_values.append(float(item.get("brier")))
        except (TypeError, ValueError):
            pass
    mean_brier = f"{sum(brier_values) / len(brier_values):.3f}" if brier_values else "—"

    history_rows = []
    for item in history:
        raw_direction = str(item.get("direction") or "").upper()
        direction = DIRECTION_LABELS.get(raw_direction, raw_direction or "—")
        try:
            probability = f"{float(item.get('probability')):.0%}"
        except (TypeError, ValueError):
            probability = "—"
        is_verified = item.get("correct") is not None
        result_class = "history-pending"
        result = "待验证"
        if is_verified:
            won = bool(item.get("correct"))
            result_class = "history-hit" if won else "history-miss"
            realized_key = "excess_return" if "/" in str(item.get("target") or "") else "asset_return"
            try:
                realized = f"{float(item.get(realized_key)):+.2%}"
            except (TypeError, ValueError):
                realized = "—"
            result = f"{'命中' if won else '未命中'} · {realized}"
        created = str(item.get("created_at") or "")[:10] or "—"
        target_session = str(item.get("target_session") or "")[:10] or "—"
        history_rows.append(
            f"<tr><td>{esc(created)}</td><td>{esc(target_session)}</td>"
            f"<td><strong>{esc(item.get('target'))}</strong></td><td>{esc(direction)}</td>"
            f"<td>{probability}</td><td><span class='{result_class}'>{esc(result)}</span></td></tr>"
        )

    if history_rows:
        history_html = (
            "<div class='history-review'><div class='forecast-block-title'>"
            "<span>历史验证记录</span><small>只追加结果，不回改原判断</small></div>"
            "<div class='table-wrap history-table'><table><thead><tr>"
            "<th>生成日</th><th>验证日</th><th>标的</th><th>原判断</th><th>原概率</th><th>真实结果</th>"
            "</tr></thead><tbody>" + "".join(history_rows) + "</tbody></table></div></div>"
        )
    else:
        history_html = (
            "<div class='history-review history-empty'><div class='forecast-block-title'>"
            "<span>历史验证记录</span><small>完成首批到期验证后自动显示</small></div></div>"
        )

    summary = (
        "<div class='forecast-summary'>"
        f"<div><small>历史样本</small><strong>{len(history)}</strong></div>"
        f"<div><small>已验证</small><strong>{len(verified)}</strong></div>"
        f"<div><small>命中率</small><strong>{hit_rate}</strong></div>"
        f"<div><small>平均 Brier</small><strong>{mean_brier}</strong></div></div>"
    )
    return (
        f"{summary}<div class='forecast-block'><div class='forecast-block-title'>"
        f"<span>本期预测</span><small>{len(cards)} 项 · 生成后冻结</small></div>{current_html}</div>"
        f"{history_html}"
    )

# Final report skin.  Keep the seven report sections visually distinct while
# sharing one restrained editorial system.  Assigning CSS here intentionally
# replaces the older experimental passes above instead of stacking more rules.
CSS = r"""
:root{
    --navy:#071a34;--navy-2:#123552;--blue:#23658f;--red:#a51f32;
    --gold:#b89b58;--ink:#172638;--muted:#647384;--line:#c6d0d8;
    --canvas:#d9e0e6;--section:#edf1f4;--section-alt:#e7edf1;
    --card:#f8fafb;--white:#fff
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
    margin:0;background:var(--canvas);color:var(--ink);
    font:16px/1.65 "Noto Sans SC","Source Han Sans SC","Microsoft YaHei UI","Microsoft YaHei",Arial,sans-serif;
    -webkit-font-smoothing:antialiased
}
.wrap{width:100%;max-width:1600px;margin:0 auto;padding-left:48px;padding-right:48px}
.ticker-bar{overflow:hidden;background:#06152b;color:#dce5ee;font:700 9px/1 Arial,sans-serif;letter-spacing:.25em;white-space:nowrap}
.ticker-track{display:flex;width:max-content;min-width:200%;animation:headline-scroll 38s linear infinite}
.ticker-track span{display:block;padding:10px 60px 9px 0}.ticker-track b{color:#d44b59}
@keyframes headline-scroll{to{transform:translateX(-50%)}}
.gov-notice{background:#263d55;color:#dce4ec;border-bottom:1px solid rgba(255,255,255,.12);font-size:11px;letter-spacing:.045em}
.gov-notice .wrap{min-height:32px;display:flex;align-items:center;gap:10px}
.flag-mark{display:inline-grid;grid-template-columns:repeat(3,4px);gap:2px;width:18px}
.flag-mark i{width:4px;height:4px;background:#cf5260}.flag-mark i:nth-child(2n){background:#9ebbd3}
.masthead{position:relative;overflow:hidden;background:linear-gradient(110deg,#071a34 0%,#0c2e4c 68%,#173e5d 100%);color:#fff}
.masthead:after{content:"";position:absolute;inset:0;background:radial-gradient(circle at 86% 15%,rgba(184,155,88,.15),transparent 25%);pointer-events:none}
.brand{position:relative;z-index:1;min-height:190px;display:grid;grid-template-columns:118px minmax(0,1fr) 248px;align-items:center;gap:32px}
.logo{display:block;width:108px;height:108px;border-radius:50%;background:var(--seal-image) center/cover no-repeat;box-shadow:0 0 0 6px rgba(255,255,255,.055),0 0 0 7px rgba(184,155,88,.38),0 14px 28px rgba(0,0,0,.25)}
.mast-copy{min-width:0}.overline{margin-bottom:12px;color:#ddc990;font:800 11px/1 Arial,sans-serif;letter-spacing:.31em}
.masthead h1{margin:0;color:#fff;font:500 clamp(42px,4.3vw,66px)/1 Georgia,"Noto Serif SC","Songti SC",serif;letter-spacing:.035em}
.mast-subtitle{margin-top:15px;color:#d8e2eb;font-size:16px;letter-spacing:.075em}.mast-rule{width:76px;height:3px;margin-top:18px;background:linear-gradient(90deg,var(--red),var(--gold))}
.report-stamp{border:1px solid rgba(255,255,255,.24);border-left:4px solid var(--gold);padding:20px 22px;text-align:right;background:rgba(255,255,255,.045)}
.report-stamp span{display:block;color:#dbc78d;font:800 9px/1 Arial,sans-serif;letter-spacing:.24em}.report-stamp strong{display:block;margin-top:10px;color:#fff;font:500 23px/1.2 Georgia,serif;letter-spacing:.04em}.report-stamp em{display:block;margin-top:8px;color:#aebdcb;font-size:10px;font-style:normal;letter-spacing:.08em}
.language-control{position:absolute;z-index:4;top:16px;right:48px;display:flex;align-items:center;gap:8px}.language-control label{color:#d3dde7;font:700 9px/1 Arial,sans-serif;letter-spacing:.12em}.language-control select{min-width:135px;padding:7px 9px;border:1px solid rgba(255,255,255,.28);border-radius:4px;background:#284762;color:#fff;font:700 12px/1.2 Arial,sans-serif}.language-control option{background:#fff;color:#172638}
.navbar{position:sticky;top:0;z-index:30;background:#f3f5f6;border-bottom:3px solid var(--red);box-shadow:0 4px 12px rgba(7,26,52,.10)}
.nav-inner{min-height:52px;display:flex;align-items:center;justify-content:space-between;gap:13px}.nav-inner a{color:#173450;font:800 10px/1 Arial,sans-serif;letter-spacing:.15em;text-decoration:none;white-space:nowrap;padding:9px 12px;border-bottom:2px solid transparent}.nav-inner a:hover{color:var(--red);border-color:var(--gold)}
main{width:100%;max-width:1600px;margin:0 auto;padding:18px;background:#d2dae1}
section{position:relative;scroll-margin-top:72px;margin:0 0 14px;padding:30px 34px;background:var(--section);border:1px solid #bbc6cf;border-top:4px solid var(--navy-2);box-shadow:0 3px 10px rgba(7,26,52,.05)}
section:nth-of-type(even){background:var(--section-alt)}
.section-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid #c2ccd4}
.section-heading h2{position:relative;margin:0;color:var(--navy);font:650 clamp(27px,2.25vw,35px)/1.15 Georgia,"Noto Serif SC","Songti SC",serif}.section-heading h2:after{content:"";display:block;width:62px;height:3px;margin-top:10px;background:linear-gradient(90deg,var(--red),var(--gold))}
.section-heading small{padding-bottom:4px;color:#718090;font:800 10px/1 Arial,sans-serif;letter-spacing:.22em;white-space:nowrap}
.section-deck{max-width:900px;margin:-8px 0 21px;color:#5c6b7b;font-size:13px}
.muted{color:var(--muted)}

/* 01 — market direction: conclusion first, time windows second. */
#direction{background:#edf2f5;border-top-color:#8e2535}
.hero{margin-bottom:12px;padding:20px 24px;background:#dce5eb;border:1px solid #c2ccd4;border-left:6px solid var(--red)}
.hero-title{color:var(--navy);font:650 clamp(25px,2.15vw,33px)/1.25 Georgia,"Noto Serif SC","Songti SC",serif}.hero-text{max-width:1100px;margin-top:7px;color:#34495d;font-size:16px}
.horizon-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.horizon{min-width:0;padding:16px 18px;background:var(--card);border:1px solid #c6d0d8;border-top:3px solid #4e708d}
.horizon-time{color:var(--red);font:800 10px/1 Arial,sans-serif;letter-spacing:.17em}.horizon-direction{margin:11px 0 7px;color:var(--navy);font:650 21px/1.3 Georgia,"Noto Serif SC","Songti SC",serif}.focus{color:#21608b;font-size:13px;font-weight:800;letter-spacing:.025em}.horizon p{margin:9px 0;color:#34495c}.risk{padding-top:9px;border-top:1px solid #dde3e8;color:#98283a;font-size:12px}

/* 02 — action agenda: compact commands, no reading detours. */
#agenda{border-top-color:#9e8447}
.action-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}
.action-box{min-height:0;padding:16px 18px;background:#f5f7f8;border:1px solid #c5cfd7;border-left:4px solid #9e8447}.action-box:nth-child(1){border-left-color:#52718d}.action-box:nth-child(3){border-left-color:#a51f32}
.action-box h3{margin:0 0 12px;color:var(--navy);font:650 21px/1.2 Georgia,"Noto Serif SC","Songti SC",serif}.action-box ul{list-style:none;margin:0;padding:0}.action-box li{position:relative;padding-left:16px;color:#293e52;font-size:14px;line-height:1.5}.action-box li:before{content:"";position:absolute;left:0;top:.58em;width:6px;height:6px;background:var(--red)}.action-box li+li{margin-top:8px;padding-top:8px;border-top:1px solid #d9e0e6}

/* 03 — verified 14-day calendar. */
#calendar{background:#e9eef2;border-top-color:#426985}
.calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));background:#f7f9fa;border:1px solid #bec9d2}
.day{min-width:0;min-height:116px;border-right:1px solid #ccd5dc;border-bottom:1px solid #ccd5dc}.day:nth-child(7n){border-right:0}.day:nth-last-child(-n+7){border-bottom:0}.day:nth-child(7n),.day:nth-child(7n-1){background:#f1f4f6}
.day-head{padding:9px 11px 8px;background:#dfe6eb;border-bottom:1px solid #c6d0d8}.day h3{margin:0;color:var(--navy);font:650 15px/1.2 Georgia,"Noto Serif SC","Songti SC",serif}.weekday{margin-top:3px;color:#718090;font-size:10px}.event{padding:8px 10px}.event+.event{border-top:1px solid #dce2e7}.event>span{color:var(--red);font:800 8px/1 Arial,sans-serif}.event strong{display:block;margin-top:4px;color:#243a4f;font-size:11px;line-height:1.4}.event small{display:block;margin-top:4px;color:#697888;font-size:9px}.event small a{display:inline-flex;align-items:center;gap:4px;color:#235f89;text-decoration:none;border-bottom:1px solid #9ab2c3}.event-company{box-shadow:inset 3px 0 #aa8f4c}.event-empty{padding:9px 10px;color:#929da7;font-size:10px}

/* 04 — capital movement and transmission are separated by purpose. */
#capital-flow{border-top-color:#294f70}
.capital-thesis{display:flex;align-items:center;gap:18px;padding:13px 17px;background:#d9e2e8;border:1px solid #bec9d2;border-left:5px solid var(--red)}
.capital-thesis>span{color:#647485;font:800 9px/1 Arial,sans-serif;letter-spacing:.18em;white-space:nowrap}.capital-thesis>strong{color:var(--navy);font:650 22px/1.3 Georgia,"Noto Serif SC","Songti SC",serif}
.capital-map{display:grid;grid-template-columns:minmax(260px,.62fr) minmax(0,1.38fr);gap:12px;margin-top:12px}.capital-column{background:#f5f7f8;border:1px solid #c2ccd4}.capital-subhead{display:flex;justify-content:space-between;gap:15px;align-items:baseline;padding:11px 14px;background:#e0e7ec;border-bottom:1px solid #c2ccd4}.capital-subhead span{color:var(--navy);font:700 16px/1.2 Georgia,"Noto Serif SC","Songti SC",serif}.capital-subhead small{color:#728190;font:800 8px/1 Arial,sans-serif;letter-spacing:.15em}
.capital-route{position:relative;padding:12px 14px 12px 44px}.capital-route+.capital-route{border-top:1px solid #d6dde3}.flow-index{color:var(--red);font:800 9px/1 Arial,sans-serif;letter-spacing:.13em}.capital-route .flow-index{position:absolute;left:14px;top:16px}.route-pair{display:flex;align-items:center;gap:9px;color:var(--navy)}.route-pair i{color:var(--red);font-style:normal}.capital-route p{margin:5px 0 0;color:#536476;font-size:11px;line-height:1.45}
.transmission-row{display:grid;grid-template-columns:22px minmax(90px,.9fr) 12px minmax(105px,1fr) 12px minmax(105px,1fr) minmax(130px,1fr);gap:7px;align-items:center;padding:11px 13px}.transmission-row+.transmission-row{border-top:1px solid #d3dbe2}.transmission-index{color:var(--red);font:800 9px/1 Arial,sans-serif}.logic-step small,.logic-action small{display:block;margin-bottom:4px;color:#7d8995;font:800 8px/1 Arial,sans-serif;letter-spacing:.12em}.logic-step strong,.logic-step span,.logic-action span{color:#293e51;font-size:11px;line-height:1.4}.logic-arrow{color:var(--red);text-align:center}.logic-action{padding:8px 9px;background:#e1e8ed;color:var(--navy);font-weight:700}

/* 05 — exactly eight names: four columns by two rows on desktop. */
#equity{background:#e9eef2;border-top-color:#386a55}
.source-grid{display:grid;gap:12px}.company-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.media-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.source-card{display:flex;flex-direction:column;min-width:0;padding:19px 20px;background:var(--card);border:1px solid #c4ced6;border-left:4px solid #61798e}.source-card.signal-focus{border-left-color:#2f7b50}.source-card.signal-wait{border-left-color:#286790}.source-card.signal-avoid{border-left-color:#a62b3b}.source-card.tone-positive{border-left-color:#2f7b50}.source-card.tone-cautious{border-left-color:#a8752f}.source-card.tone-neutral{border-left-color:#60778c}
.card-label{align-self:flex-start;margin-bottom:12px;padding:5px 8px;background:#e1e8ee;color:#405d75;font:800 10px/1 Arial,sans-serif;letter-spacing:.07em}.signal-focus .card-label,.tone-positive .card-label{background:#e2eee6;color:#246642}.signal-wait .card-label,.tone-neutral .card-label{background:#e2ebf2;color:#285f85}.signal-avoid .card-label{background:#f2e2e5;color:#982638}.tone-cautious .card-label{background:#f2e9d8;color:#815d24}
.source-card h3{margin:0;color:var(--navy);font:650 20px/1.25 Georgia,"Noto Serif SC","Songti SC",serif}.source-card>p{margin:11px 0;color:#34495d;font-size:14px}.stock-meta{margin:4px 0;padding:7px 8px;background:#e9eef2;border:1px solid #d4dce3;color:#506578;font-size:11px}.card-note,.card-risk{margin-top:8px;padding-top:8px;border-top:1px solid #dce2e7;font-size:12px}.card-note{color:#38526a}.card-risk{color:#96283a}.source-links{display:flex;flex-wrap:wrap;gap:7px 11px;margin-top:auto;padding-top:14px}.source-links a,.source-links span{color:#235f89;font-size:11px;text-decoration:none;border-bottom:1px solid #9bb2c3}.source-links a span{border:0}

/* 06 — event focus: fewer cards, stronger topic hierarchy. */
#market-focus{border-top-color:#8b7138}.media-grid{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}.media-grid .source-card{min-height:0;padding:19px 20px;border-top:4px solid #8b7138;border-left:1px solid #c4ced6}.media-grid .source-card h3{font-size:21px}.media-grid .source-card>p{font-size:14px;line-height:1.55}.media-grid .card-note{margin-top:8px}

/* 07 — current forecast and append-only verification record. */
#forecast{background:#e9eef2;border-top-color:#694a68}.prediction-note{margin:-8px 0 18px;color:#647384;font-size:13px}.forecast-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px;background:#dde5eb;border:1px solid #bec9d2}.forecast-summary div{padding:13px 16px;border-right:1px solid #bec9d2}.forecast-summary div:last-child{border-right:0}.forecast-summary small{display:block;color:#657586;font:800 8px/1 Arial,sans-serif;letter-spacing:.13em}.forecast-summary strong{display:block;margin-top:5px;color:var(--navy);font:650 21px/1 Georgia,serif}
.forecast-block,.history-review{background:#f5f7f8;border:1px solid #c2ccd4}.history-review{margin-top:12px}.forecast-block-title{display:flex;align-items:baseline;justify-content:space-between;gap:18px;padding:11px 14px;background:#e0e7ec;border-bottom:1px solid #c2ccd4}.forecast-block-title span{color:var(--navy);font-weight:800}.forecast-block-title small{color:#6e7e8e;font-size:10px}.forecast-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:11px}.forecast-card{display:grid;grid-template-columns:1fr auto;gap:10px 14px;padding:14px;background:#f9fafb;border:1px solid #ccd5dc;border-top:3px solid #60788d}.forecast-card.direction-up{border-top-color:#347b52}.forecast-card.direction-down{border-top-color:#a52a3a}.forecast-card.direction-neutral{border-top-color:#3d6e91}.forecast-card-top{grid-column:1/-1;display:flex;align-items:center;gap:10px}.forecast-horizon{color:#667687;font-size:10px;font-weight:800}.forecast-target{margin-right:auto;color:var(--navy);font:650 19px/1 Georgia,serif}.direction-pill,.history-hit,.history-miss,.history-pending{display:inline-block;padding:3px 7px;font-size:10px;font-weight:800}.forecast-card.direction-up .direction-pill,.history-hit{background:#deece3;color:#246642}.forecast-card.direction-neutral .direction-pill,.history-pending{background:#dfe9f0;color:#285f85}.forecast-card.direction-down .direction-pill,.history-miss{background:#f1dfe2;color:#982638}.forecast-probability{align-self:start}.forecast-probability strong{display:block;color:var(--navy);font:650 24px/1 Georgia,serif}.forecast-probability small,.forecast-reason small,.forecast-invalidation small{color:#778594;font:800 8px/1 Arial,sans-serif;letter-spacing:.1em}.forecast-reason,.forecast-invalidation{grid-column:1/-1;border-top:1px solid #dce2e7;padding-top:8px}.forecast-reason p,.forecast-invalidation p{margin:4px 0 0;color:#34495d;font-size:12px}.forecast-invalidation p{color:#922b3a}.table-wrap{overflow:auto}.history-table{border:0}table{width:100%;border-collapse:collapse;background:#f8fafb}th{padding:9px 11px;background:#d6e0e7;color:var(--navy);border-bottom:2px solid #9cacba;text-align:left;font:800 9px/1.2 Arial,sans-serif;letter-spacing:.08em}td{padding:10px 11px;border-bottom:1px solid #d6dde3;vertical-align:top;font-size:11px}tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f1f4f6}.history-empty{min-height:52px}

.integrity{display:flex;align-items:center;gap:18px;margin:0;padding:14px 18px;background:#e6ebef;border:1px solid #bac5ce;color:#657382;font-size:11px}.integrity-title{color:#31495f;font-weight:800;white-space:nowrap}.audit-ok,.audit-warn{flex:1}.audit-ok strong{color:#2b6844}.audit-warn strong{color:#9b2a3a}.metrics{display:flex;gap:14px;white-space:nowrap}.metrics strong{color:#263e54}

/* White House-inspired footer: directory first, identity and seal last. */
footer{background:#07142b;color:#d8e1eb;border-top:4px solid var(--red)}footer a{color:inherit;text-decoration:none}
.footer-main{display:grid;grid-template-columns:minmax(270px,.85fr) minmax(430px,1.35fr) minmax(270px,.8fr);gap:36px;align-items:start;padding-top:28px;padding-bottom:25px}.footer-identity{display:flex;align-items:center;gap:16px}.footer-seal{display:block;width:68px;height:68px;flex:0 0 68px;border-radius:50%;background:var(--seal-image) center/cover no-repeat;box-shadow:0 0 0 4px rgba(255,255,255,.045),0 0 0 5px rgba(184,155,88,.35)}.footer-wordmark{color:#fff;font:500 clamp(25px,2.2vw,34px)/.98 Georgia,serif;letter-spacing:.025em}.footer-wordmark small{display:block;margin-top:7px;color:#9ca9b9;font:800 6px/1.2 Arial,sans-serif;letter-spacing:.2em;text-transform:uppercase}.footer-directory{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}.footer-col h3,.footer-brief h3{margin:0 0 10px;color:#fff;font:800 8px/1 Arial,sans-serif;letter-spacing:.2em}.footer-links{list-style:none;margin:0;padding:0}.footer-links li+li{margin-top:5px}.footer-links a,.footer-framework{color:#aeb9c8;font-size:10px;line-height:1.45}.footer-links a:hover{color:#fff}.footer-framework{margin:0;line-height:1.55}.footer-brief{padding-left:26px;border-left:1px solid rgba(255,255,255,.17)}.footer-brief-lead{margin:0 0 9px;color:#fff;font:500 15px/1.25 Georgia,"Noto Serif SC","Songti SC",serif}.footer-report-links{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:8px}.footer-report-link{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.42);color:#fff;font:800 7px/1.2 Arial,sans-serif;letter-spacing:.08em}.footer-report-link span{color:#dbc276}.footer-disclosure{margin:0;color:#919eae;font-size:8px;line-height:1.45}.footer-bottom{display:flex;align-items:center;justify-content:space-between;gap:24px;padding-top:11px;padding-bottom:12px;border-top:1px solid rgba(255,255,255,.17);color:#8493a5;font-size:7px;letter-spacing:.07em}.footer-quick{display:flex;flex-wrap:wrap;gap:8px 15px}.footer-quick a{color:#d7dfe9;font:800 7px/1 Arial,sans-serif;letter-spacing:.11em}.footer-quick a:hover{color:#dbc276}.footer-legal{display:flex;gap:18px;white-space:nowrap}

/* Navy reading theme: the page itself is dark; hierarchy comes from tone,
   borders and typography rather than large white surfaces. */
:root{--ink:#e8eef4;--muted:#a6b4c2;--line:#37516a;--canvas:#06152b;--section:#0b243d;--section-alt:#0d2944;--card:#102d48}
body{background:#06152b;color:var(--ink)}
.masthead{background:linear-gradient(110deg,#05152b 0%,#0a2a47 68%,#123a57 100%)}
.brand{min-height:162px}.mast-rule{margin-top:16px}.navbar{background:#0a2138;border-bottom-color:#a92b3c;box-shadow:0 4px 12px rgba(0,0,0,.28)}.nav-inner a{color:#dbe5ee}.nav-inner a:hover{color:#fff}
.language-control{top:13px}.language-control label{font-size:8px}.language-control select{min-width:112px;padding:5px 7px;border-radius:3px;font-size:10px}
main{background:#06152b}
section,section:nth-of-type(even){background:var(--section);border-color:#314b63;box-shadow:0 3px 10px rgba(0,0,0,.14)}
#direction,#calendar,#equity,#forecast{background:var(--section)}
#agenda,#capital-flow,#market-focus{background:var(--section-alt)}
.section-heading{border-color:#365069}.section-heading h2{color:#f3f6f9}.section-heading small{color:#93a8ba}.section-deck,.prediction-note{color:#a7b5c3}
.hero{background:#12314d;border-color:#3b566d}.hero-title{color:#fff}.hero-text{color:#c6d2dc}
.horizon,.action-box{background:#102b45;border-color:#3a5369}.horizon-direction,.action-box h3{color:#f5f7f9}.horizon p,.action-box li{color:#c5d0da}.focus{color:#83b9df}.risk{border-color:#3b5267;color:#ee9aa6}.action-box li+li{border-color:#354c61}
#calendar{background:#0c2741}.calendar-grid{background:#0c2741;border-color:#3c566d}.day{border-color:#3a5369}.day:nth-child(7n),.day:nth-child(7n-1){background:#0a2239}.day-head{background:#173750;border-color:#486078}.day h3{color:#f4f7f9;font:800 16px/1.2 "Noto Sans SC","Microsoft YaHei UI",sans-serif}.weekday{color:#9cafbf;font-size:10px}.event+.event{border-color:#354d63}.event strong{color:#eaf0f5;font:700 12px/1.4 "Noto Sans SC","Microsoft YaHei UI",sans-serif}.event small{color:#9eafbd;font-size:10px}.event small a{color:#86bddf;border-color:#537c98}.event-empty{color:#71869a;font:500 10px/1.4 "Noto Sans SC","Microsoft YaHei UI",sans-serif}
.capital-thesis{background:#12314d;border-color:#3b556d}.capital-thesis>span{color:#9eb0c0}.capital-thesis>strong{color:#fff;font-size:21px}.capital-column{background:#102b45;border-color:#3a536a}.capital-subhead{background:#173750;border-color:#425b71}.capital-subhead span{color:#fff;font:800 17px/1.2 "Noto Sans SC","Microsoft YaHei UI",sans-serif}.capital-subhead small{color:#9db0c0}.capital-route+.capital-route,.transmission-row+.transmission-row{border-color:#354d62}.route-pair{color:#f1f5f8}.route-pair strong{font:800 15px/1.35 "Noto Sans SC","Microsoft YaHei UI",sans-serif}.capital-route p{color:#adbdca;font-size:12px}.logic-step small,.logic-action small{color:#8fa4b5;font-size:9px}.logic-step strong,.logic-step span,.logic-action span{color:#dce5ec;font-size:12px}.logic-action{background:#173750;color:#fff}
#equity{background:#0c2741}.company-grid .source-card{padding:17px 18px}.company-grid .card-label{margin-bottom:10px;padding:6px 9px}.company-grid .source-card h3{font-size:19px}.company-grid .source-card>p{margin:9px 0;font-size:13px;line-height:1.55}.company-grid .stock-meta{font-size:10px;padding:6px 7px}.company-grid .card-note,.company-grid .card-risk{margin-top:6px;padding-top:6px;font-size:11px;line-height:1.5}.company-grid .source-links{padding-top:10px}.source-card{background:#102b45;border-color:#3a5369}.source-card h3{color:#fff}.source-card>p{color:#c4d0da}.stock-meta{background:#173750;border-color:#405a70;color:#b9c8d4}.card-note,.card-risk{border-color:#354d62}.card-note{color:#b9cfdf}.card-risk{color:#ef9aa6}.source-links a,.source-links span{color:#87bfdf;border-color:#547d98}
.media-grid .source-card{border-left-color:#3a5369}.media-grid .source-card>p{color:#c8d3dc}
#forecast{padding-top:20px;padding-bottom:20px}.prediction-note{margin:-4px 0 10px;font-size:11px}.forecast-summary{margin-bottom:7px;background:#173750;border-color:#425b72}.forecast-summary div{padding:6px 10px;border-color:#425b72}.forecast-summary small{color:#9eb0c0;font-size:7px}.forecast-summary strong{color:#fff;font-size:16px}.forecast-block,.history-review{background:#102b45;border-color:#3a5369}.history-review{margin-top:7px}.forecast-block-title{padding:7px 10px;background:#173750;border-color:#425b72}.forecast-block-title span{color:#fff;font-size:14px}.forecast-block-title small{color:#9fb0bf;font-size:8px}.forecast-cards{gap:6px;padding:6px}.forecast-card{grid-template-columns:60px minmax(0,1fr) minmax(0,1fr);gap:5px 10px;padding:8px 9px;background:#0d263f;border-color:#3a5369}.forecast-target,.forecast-probability strong{color:#fff}.forecast-target{font-size:17px}.forecast-horizon{font-size:8px}.forecast-probability{grid-column:1;grid-row:2}.forecast-probability strong{font-size:18px}.forecast-reason{grid-column:2;grid-row:2}.forecast-invalidation{grid-column:3;grid-row:2}.forecast-reason,.forecast-invalidation{padding:0 0 0 8px;border-top:0;border-left:1px solid #385066}.forecast-probability small,.forecast-reason small,.forecast-invalidation small{color:#8fa3b4;font-size:7px}.forecast-reason p,.forecast-invalidation p{margin-top:3px;font-size:10px}.forecast-reason p{color:#c3d0da}.forecast-invalidation p{color:#ef9aa6}.history-table table{background:#0d263f}.history-table th{padding:6px 9px;background:#193a54;color:#eaf0f5;border-color:#587086;font-size:8px}.history-table td{padding:7px 9px;color:#c7d2dc;border-color:#354d62;font-size:9px}.history-table tbody tr:nth-child(even){background:#102d48}
#forecast .section-heading{margin-bottom:10px}
.integrity{background:#0b2239;border-color:#314a61;color:#aebdca}.integrity-title,.metrics strong{color:#e3eaf0}
footer{background:#040f22}.footer-col h3,.footer-brief h3{font-size:10px}.footer-links a,.footer-framework{font-size:12px}.footer-brief-lead{font-size:17px}.footer-report-link{font-size:9px}.footer-disclosure{font-size:9.5px}.footer-wordmark small{font-size:8px}.footer-quick a{font-size:8.5px}.footer-bottom{font-size:8.5px}

@media(max-width:1200px){
    .brand{grid-template-columns:104px minmax(0,1fr)}.report-stamp{display:none}.logo{width:94px;height:94px}
    .calendar-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.day:nth-child(7n),.day:nth-last-child(-n+7){border-right:1px solid #ccd5dc;border-bottom:1px solid #ccd5dc}.day:nth-child(4n){border-right:0}.day:nth-last-child(-n+2){border-bottom:0}
    .company-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.capital-map{grid-template-columns:1fr}.footer-main{grid-template-columns:minmax(240px,.8fr) minmax(0,1.2fr);gap:28px}.footer-brief{grid-column:1/-1;padding:18px 0 0;border-left:0;border-top:1px solid rgba(255,255,255,.17)}
}
@media(max-width:900px){
    .wrap{padding-left:24px;padding-right:24px}.horizon-grid,.action-grid,.media-grid,.forecast-cards{grid-template-columns:1fr}.transmission-row{grid-template-columns:24px 1fr}.transmission-row .logic-arrow{display:none}.transmission-row .logic-step,.transmission-row .logic-action{grid-column:2}.forecast-summary{grid-template-columns:1fr 1fr}.forecast-summary div:nth-child(2){border-right:0}.forecast-summary div:nth-child(-n+2){border-bottom:1px solid #bec9d2}.footer-scope{grid-template-columns:1fr}.footer-quick{justify-content:flex-start}
}
@media(max-width:700px){
    .ticker-bar{display:none}.gov-notice{font-size:9px}.brand{min-height:160px;grid-template-columns:70px minmax(0,1fr);gap:18px}.logo{width:64px;height:64px}.masthead h1{font-size:34px}.mast-subtitle{font-size:12px;letter-spacing:.04em}.overline{font-size:8px}.language-control{top:10px;right:16px}.language-control label{display:none}.language-control select{min-width:112px;font-size:10px}.navbar{position:relative}.nav-inner{justify-content:flex-start;overflow:auto;padding-left:8px;padding-right:8px}.nav-inner a{font-size:9px;padding:8px}
    main{padding:12px}section{scroll-margin-top:14px;padding:26px 18px;margin-bottom:12px}.section-heading{align-items:flex-start;flex-direction:column;gap:8px}.section-heading small{white-space:normal}.calendar-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.day:nth-child(4n){border-right:1px solid #ccd5dc}.day:nth-child(2n){border-right:0}.day:nth-last-child(-n+2){border-bottom:0}.company-grid{grid-template-columns:1fr}.capital-thesis{align-items:flex-start;flex-direction:column;gap:7px}.forecast-summary{grid-template-columns:1fr}.forecast-summary div{border-right:0;border-bottom:1px solid #bec9d2}.forecast-summary div:last-child{border-bottom:0}.integrity{align-items:flex-start;flex-direction:column}.metrics{flex-wrap:wrap;white-space:normal}.footer-main{grid-template-columns:1fr;gap:22px;padding-top:24px;padding-bottom:22px}.footer-directory{grid-template-columns:1fr 1fr;gap:22px 18px}.footer-directory .footer-col:last-child{grid-column:1/-1}.footer-brief{grid-column:auto}.footer-identity{align-items:center}.footer-seal{width:58px;height:58px;flex-basis:58px}.footer-bottom{align-items:flex-start;flex-direction:column}.footer-legal{flex-direction:column;gap:4px;white-space:normal}
}
@media(max-width:430px){.footer-directory{grid-template-columns:1fr}.footer-directory .footer-col:last-child{grid-column:auto}.footer-identity{flex-direction:column}}
@media(prefers-reduced-motion:reduce){.ticker-track{animation:none}}
@media print{.ticker-track{animation:none}.navbar{position:relative}section{break-inside:avoid;box-shadow:none}}
"""


def render_report(context: dict) -> str:
    direction = context.get("direction", {})
    gate = context["gate"]
    failures = context.get("core_failures", [])
    audit_class = "audit-ok" if gate.allowed else "audit-warn"
    audit_title = "核心数据源本轮读取正常" if gate.allowed else "数据存在缺口，本轮不冻结预测"
    report_date = str(context.get("report_date") or date.today().isoformat())[:10]
    report_time = datetime.now(ZoneInfo("America/Denver")).strftime("%H:%M")
    seal_data_uri = _seal_data_uri()

    ticker = (
        "DOWNLOAD THE DAILY MARKET BRIEF · REAL-TIME POLICY WATCH · GLOBAL MACRO SIGNALS · "
        f"CAPITAL FLOW · SECTOR ROTATION · EQUITY ACTIONS · REPORT {report_date} {report_time} MT →"
    )

    failures_text = " · ".join(failures) or "无"
    reasons_text = ", ".join(gate.reasons) or "无"
    integrity_zh = f"{audit_title}　核心失败：{failures_text}　门槛原因：{reasons_text}"

    integrity_i18n = {
        "zh_tw": ("核心資料源本輪讀取正常" if gate.allowed else "資料存在缺口，本輪不凍結預測")
                 + f"　核心失敗：{failures_text}　門檻原因：{reasons_text}",
        "en": ("Core official sources loaded normally" if gate.allowed else "Data gaps detected; forecasts not frozen")
              + f"  Core failures: {' · '.join(failures) or 'None'}  Gate reasons: {', '.join(gate.reasons) or 'None'}",
    }
    # Technical failure/reason identifiers are intentionally kept as-is in other languages.
    for code in LANG_CODES:
        if code not in integrity_i18n:
            integrity_i18n[code] = integrity_i18n["en"]

    options = "".join(
        f"<option value='{code}'{' selected' if code == 'zh' else ''}>{label}</option>"
        for code, label in LANG_OPTIONS
    )
    language_control = (
        '<div class="language-control"><label for="languageSelect">LANGUAGE</label>'
        f'<select id="languageSelect" aria-label="Language">{options}</select></div>'
    )

    script = r"""
<script>
(function () {
    const select = document.getElementById("languageSelect");
    if (!select) return;

    function decodeMap(encoded) {
        try {
            const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
            const jsonText = new TextDecoder("utf-8").decode(bytes);
            return JSON.parse(jsonText);
        } catch (e) {
            return {};
        }
    }

    const nodes = Array.from(document.querySelectorAll("[data-i18n]"));
    nodes.forEach(el => {
        el._i18nMap = decodeMap(el.dataset.i18n || "");
        el.dataset.zh = el.textContent;
    });

    const labelNodes = Array.from(document.querySelectorAll("[data-i18n-label]"));
    labelNodes.forEach(el => {
        el._i18nMap = decodeMap(el.dataset.i18nLabel || "");
        const firstText = Array.from(el.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
        el._i18nTextNode = firstText || null;
        el.dataset.zhLabel = firstText ? firstText.nodeValue : el.textContent;
    });

    function translated(map, lang, fallback) {
        if (lang === "zh") return fallback;
        return map[lang] || map.en || fallback;
    }

    function setLanguage(lang) {
        nodes.forEach(el => {
            el.textContent = translated(el._i18nMap || {}, lang, el.dataset.zh || "");
        });

        labelNodes.forEach(el => {
            const value = translated(el._i18nMap || {}, lang, el.dataset.zhLabel || "");
            if (el._i18nTextNode) el._i18nTextNode.nodeValue = value;
            else el.textContent = value;
        });

        const htmlLang = {
            zh: "zh-CN", zh_tw: "zh-Hant", en: "en", bg: "bg", ru: "ru",
            ja: "ja", ko: "ko", fr: "fr", de: "de", es: "es", th: "th"
        };
        document.documentElement.lang = htmlLang[lang] || "en";
        document.body.dataset.lang = lang;
        select.value = lang;
    }

    select.addEventListener("change", function () {
        setLanguage(this.value);
    });

    // Default is always Simplified Chinese.
    setLanguage("zh");
})();
</script>
"""

    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEWS FINANCE | Global Market Intelligence</title><style>{CSS}</style></head><body data-lang="zh" style="--seal-image:url({seal_data_uri})"><!-- legacy-layout-labels: 一｜今日投资方向 | 二｜具体动作 | 三｜未来14日重要日程 | 四｜资金流向与投资逻辑 | 五｜重点公司前瞻 | 六｜市场正在交易什么 | 七｜预测与验证 -->
<div class="ticker-bar" aria-label="市场研究栏目"><div class="ticker-track"><span><b>●</b> {esc(ticker)}</span><span aria-hidden="true"><b>●</b> {esc(ticker)}</span></div></div>
<div class="gov-notice"><div class="wrap"><span class="flag-mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></span>Independent Investment Research · Public Data · Non-Government Website</div></div>
<header class="masthead">{language_control}<div class="wrap brand">{_logo()}<div class="mast-copy"><div class="overline">GLOBAL MARKET INTELLIGENCE</div><h1>NEWS FINANCE</h1><div class="mast-rule" aria-hidden="true"></div></div><div class="report-stamp"><span>REPORT DATE</span><strong>{esc(report_date)}</strong><em>PUBLIC DATA · INDEPENDENT VIEW</em></div></div></header>
<nav class="navbar" aria-label="报告目录"><div class="wrap nav-inner"><a href="#direction">MARKET</a><a href="#agenda">ACTION</a><a href="#calendar">CALENDAR</a><a href="#capital-flow">CAPITAL FLOW</a><a href="#equity">EQUITY</a><a href="#market-focus">EVENTS</a><a href="#forecast">FORECAST</a></div></nav><main>
<section id="direction"><div class="section-heading"><h2{_i18n_attr(_static_i18n("section_direction"))}>一｜市场定调</h2><small>MARKET DIRECTION</small></div><div class="hero"><div class="hero-title"{_i18n_attr(_field_i18n(direction, "title"))}>{esc(direction.get('title','等待确认'))}</div><div class="hero-text"{_i18n_attr(_field_i18n(direction, "brief"))}>{esc(direction.get('brief'))}</div></div><div class="horizon-grid">{_horizons(context)}</div></section>
<section id="agenda"><div class="section-heading"><h2{_i18n_attr(_static_i18n("section_action"))}>二｜策略动作</h2><small>ACTION AGENDA</small></div><div class="action-grid"><div class="action-box"><h3{_i18n_attr(_static_i18n("watch"))}>观察</h3>{_list(context, 'watch')}</div><div class="action-box"><h3{_i18n_attr(_static_i18n("prepare"))}>准备</h3>{_list(context, 'prepare')}</div><div class="action-box"><h3{_i18n_attr(_static_i18n("avoid"))}>规避</h3>{_list(context, 'avoid')}</div></div></section>
<section id="calendar"><div class="section-heading"><h2{_i18n_attr(_static_i18n("section_calendar"))}>三｜关键日历</h2><small>ECONOMIC &amp; CORPORATE CALENDAR</small></div><div class="calendar-grid">{_calendar(context)}</div></section>
<section id="capital-flow"><div class="section-heading"><h2{_i18n_attr(_static_i18n("section_flow"))}>四｜资金路径</h2><small>CAPITAL FLOW &amp; TRANSMISSION</small></div><div class="capital-thesis"><span>当前主路径</span><strong{_i18n_attr(_field_i18n(direction, "title"))}>{esc(direction.get('title','等待确认'))}</strong></div>{_logic(context)}</section>
<section id="equity"><div class="section-heading"><h2{_i18n_attr(_static_i18n("section_equity"))}>五｜个股雷达</h2><small>EQUITY WATCHLIST</small></div><div class="source-grid company-grid">{_source_cards(context,'company')}</div></section>
<section id="market-focus"><div class="section-heading"><h2{_i18n_attr(_static_i18n("section_market"))}>六｜事件焦点</h2><small>MARKET FOCUS</small></div><div class="source-grid media-grid">{_source_cards(context,'media')}</div></section>
<section id="forecast"><div class="section-heading"><h2{_i18n_attr(_static_i18n("section_forecast"))}>七｜预测验证</h2><small>FORECAST &amp; REVIEW</small></div><p class="prediction-note"{_i18n_attr(_static_i18n("prediction_note"))}>判断生成后即冻结，后续仅以真实市场结果检验；不因结果倒推或修改原始结论。</p>{_predictions(context)}</section>
<aside class="integrity"><span class="integrity-title"{_i18n_attr(_static_i18n("data_integrity"))}>数据完整性</span><div class="{audit_class}"{_i18n_attr(integrity_i18n)}>{esc(integrity_zh)}</div><div class="metrics"><span{_i18n_attr(_static_i18n("coverage"))}>覆盖率</span> <strong>{context.get('market_coverage',0):.0%}</strong><span{_i18n_attr(_static_i18n("frozen"))}>冻结</span> <strong>{context.get('predictions_frozen',0)}</strong><span{_i18n_attr(_static_i18n("sources"))}>来源</span> <strong>{len(context.get('sources',[]))}</strong></div></aside>
</main><footer><div class="wrap footer-main"><div class="footer-identity"><span class="footer-seal" role="img" aria-label="美国国徽"></span><div class="footer-wordmark">NEWS FINANCE<small>Independent Market Research</small></div></div><nav class="footer-directory" aria-label="报告栏目"><div class="footer-col"><h3>MARKET</h3><ul class="footer-links"><li><a href="#direction">市场定调</a></li><li><a href="#agenda">策略动作</a></li><li><a href="#calendar">关键日历</a></li></ul></div><div class="footer-col"><h3>RESEARCH</h3><ul class="footer-links"><li><a href="#capital-flow">资金路径</a></li><li><a href="#equity">个股雷达</a></li><li><a href="#market-focus">事件焦点</a></li></ul></div><div class="footer-col"><h3>METHOD</h3><p class="footer-framework"{_i18n_attr(_static_i18n("footer_framework"))}>官方数据 · 公司公告<br>跨资产验证 · 事件推演<br>历史参照 · 事后复盘</p></div></nav><aside class="footer-brief"><h3>DAILY MARKET BRIEF</h3><p class="footer-brief-lead">Independent research for clearer market decisions.</p><div class="footer-report-links"><a class="footer-report-link" href="#direction">今日结论 <span aria-hidden="true">→</span></a><a class="footer-report-link" href="#forecast">预测验证 <span aria-hidden="true">→</span></a></div><p class="footer-disclosure"{_i18n_attr(_static_i18n("disclosure"))}>独立投资研究，非美国政府网站。本报告仅用于研究与学习，不构成投资建议、收益保证或证券买卖承诺。</p></aside></div><div class="wrap footer-bottom"><nav class="footer-quick" aria-label="底部快捷入口"><a href="#direction">MARKET</a><a href="#agenda">ACTION</a><a href="#calendar">CALENDAR</a><a href="#capital-flow">CAPITAL FLOW</a><a href="#equity">EQUITY</a><a href="#market-focus">EVENTS</a><a href="#forecast">REVIEW</a></nav><div class="footer-legal"><span>PUBLIC DATA · INDEPENDENT ANALYSIS</span><span>NON-GOVERNMENT WEBSITE · {esc(report_date)}</span></div></div></footer>{script}</body></html>'''
