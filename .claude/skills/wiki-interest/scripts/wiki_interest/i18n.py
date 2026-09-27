"""Labels for the PDF report and chart in the user's language (uk, en; fallback en)."""

from matplotlib.dates import num2date

MONTHS = {
    "uk": ["січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

MONTHS_FULL = {
    "uk": ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень",
           "вересень", "жовтень", "листопад", "грудень"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December"],
}

LANG_NAMES = {
    "uk": {
        "uk": "українська", "en": "англійська", "pl": "польська", "cs": "чеська", "sk": "словацька",
        "de": "німецька", "fr": "французька", "es": "іспанська", "it": "італійська",
        "pt": "португальська", "nl": "нідерландська", "sv": "шведська", "fi": "фінська",
        "ro": "румунська", "hu": "угорська", "bg": "болгарська", "lt": "литовська",
        "lv": "латиська", "et": "естонська", "be": "білоруська", "ru": "російська",
        "tr": "турецька", "ja": "японська", "zh": "китайська", "ka": "грузинська",
    },
    "en": {
        "uk": "Ukrainian", "en": "English", "pl": "Polish", "cs": "Czech", "sk": "Slovak",
        "de": "German", "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
        "nl": "Dutch", "sv": "Swedish", "fi": "Finnish", "ro": "Romanian", "hu": "Hungarian",
        "bg": "Bulgarian", "lt": "Lithuanian", "lv": "Latvian", "et": "Estonian",
        "be": "Belarusian", "ru": "Russian", "tr": "Turkish", "ja": "Japanese", "zh": "Chinese",
        "ka": "Georgian",
    },
}

TEXT = {
    "uk": {
        "title": "Звіт: «{topic}»",
        "subtitle": "Інтерес за переглядами Вікіпедії · {period} · {date}",
        "results": "Результати",
        "col_lang": "Мова",
        "col_direction": "Тренд",
        "col_yoy": "Зміна за рік",
        "col_site": "Уся Вікіпедія\nцією мовою",
        "col_views": "Медіана\nна місяць",
        "col_conf": "Надійність",
        "growing": "зростає",
        "declining": "падає",
        "flat": "без чіткого тренду",
        "conf_high": "висока",
        "conf_medium": "середня",
        "conf_low": "низька",
        "problems": "Критичні проблеми",
        "conclusion": "Висновок",
        "recommendations": "Рекомендації",
        "chart": "Динаміка переглядів",
        "followup": "Уточнення: {question}",
        "seasonality": "Сезонність",
        "col_year": "Рік",
        "col_season": "Сезон",
        "col_season_mean": "Середнє\nна місяць",
        "col_peak": "Пік (проти середнього)",
        "col_low": "Мінімум (проти середнього)",
        "peak_repeats": "Найвищий місяць щороку — {month}.",
        "peak_varies": "Найвищий місяць щороку різний: {months}.",
        "low_repeats": "Найнижчий місяць щороку — {month}.",
        "low_varies": "Найнижчий місяць щороку різний: {months}.",
        "peak_is_trend": "Пік сезону {season} не вищий за сусідні місяці, тож це радше наслідок загального тренду, ніж сезонність.",
        "season_note": "Кожен сезон (12 місяців) порівнюється з його власним середнім. Зелений — пік сезону, червоний — мінімум.",
        "views_per_month": "переглядів на місяць",
        "no_data": "Немає даних",
        "missing_lang": "Мовою «{name}» статті немає, тому даних немає (це не означає нульовий інтерес).",
        "no_views_lang": "Мовою «{name}» стаття є, але за цей період немає переглядів або повного місяця від її створення.",
        "low_volume": "{name}: мало переглядів (медіана {median} на місяць), тож відсотки змін ненадійні.",
        "short_history": "{name}: даних менше ніж за 2 роки, зміну рік до року порахувати не можна.",
        "footer": "Джерело: Wikimedia Pageviews API. Перегляди Вікіпедії показують увагу до теми, а не попит.",
        "na": "н/д",
    },
    "en": {
        "title": "Report: “{topic}”",
        "subtitle": "Interest by Wikipedia pageviews · {period} · {date}",
        "results": "Results",
        "col_lang": "Language",
        "col_direction": "Trend",
        "col_yoy": "Change over\nthe year",
        "col_site": "All Wikipedia\nin this language",
        "col_views": "Median views\nper month",
        "col_conf": "Reliability",
        "growing": "growing",
        "declining": "declining",
        "flat": "no clear trend",
        "conf_high": "high",
        "conf_medium": "medium",
        "conf_low": "low",
        "problems": "Critical issues",
        "conclusion": "Conclusion",
        "recommendations": "Recommendations",
        "chart": "Pageviews over time",
        "followup": "Follow-up: {question}",
        "seasonality": "Seasonality",
        "col_year": "Year",
        "col_season": "Season",
        "col_season_mean": "Average\nper month",
        "col_peak": "Peak (vs average)",
        "col_low": "Low (vs average)",
        "peak_repeats": "The highest month every year is {month}.",
        "peak_varies": "The highest month differs by year: {months}.",
        "low_repeats": "The lowest month every year is {month}.",
        "low_varies": "The lowest month differs by year: {months}.",
        "peak_is_trend": "The peak of season {season} is not above its neighbouring months, so it reflects the overall trend rather than seasonality.",
        "season_note": "Each season (12 months) is compared with its own average. Green = season peak, red = season low.",
        "views_per_month": "views per month",
        "no_data": "No data",
        "missing_lang": "There is no {name} article, so there is no data (which is not the same as zero interest).",
        "no_views_lang": "The {name} article exists, but in this period it has no views or no complete month since it was created.",
        "low_volume": "{name}: few views (median {median} per month), so percentage changes are unreliable.",
        "short_history": "{name}: less than 2 years of data, so the change over the year can't be computed.",
        "footer": "Source: Wikimedia Pageviews API. Wikipedia pageviews show attention to a topic, not demand.",
        "na": "n/a",
    },
}


def _l(lang: str) -> str:
    return lang if lang in TEXT else "en"


def t(key: str, lang: str, **kwargs) -> str:
    return TEXT[_l(lang)][key].format(**kwargs)


def lang_name(code: str, lang: str) -> str:
    return LANG_NAMES[_l(lang)].get(code, code)


def month_name(month: str, lang: str, full: bool = False) -> str:
    """'11' -> 'листопад' (full) or 'лис'."""
    return (MONTHS_FULL if full else MONTHS)[_l(lang)][int(month) - 1]


def month_label(x: float, lang: str) -> str:
    d = num2date(x)
    return f"{MONTHS[_l(lang)][d.month - 1]} {d.year}"


def period_label(start: str, end: str, lang: str) -> str:
    """'2024-09-01', '2026-08-31' -> 'вер 2024 – сер 2026'."""
    names = MONTHS[_l(lang)]
    (y1, m1), (y2, m2) = (map(int, s.split("-")[:2]) for s in (start, end))
    return f"{names[m1 - 1]} {y1} – {names[m2 - 1]} {y2}"
