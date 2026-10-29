"""Fetch BVC (Bolsa de Valores de Colombia) stock prices + daily/monthly/yearly %
change from La Republica's public JSON API (no login, no headless browser needed).

Endpoint discovered via the 'movimiento accionario' stock pages:
  https://www.larepublica.co/api/quote/bvc-historic/{TICKER}?scale=4&qName={TICKER}
scale=4 returns ~1 year of daily closes, which is enough to compute %dia, %mes
(vs last close before the 1st of the current month) and %ano (vs last close
before Jan 1 of the current year) the same way fetch_market.py does for Yahoo
Finance tickers.

Market cap (in COP): stockanalysis.com/quote/bvc/{TICKER}/market-cap/ states it
plainly in a stat card (e.g. "114.30T"). iCOLCAP is an ETF (tracks the index,
no market cap of its own), so it's skipped there -> "-" in the bulletin.
"""
import datetime
import json
import re
import urllib.request

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MCAP_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

URL_TMPL = "https://www.larepublica.co/api/quote/bvc-historic/{code}?scale=4&qName={code}"
MCAP_URL_TMPL = "https://stockanalysis.com/quote/bvc/{code}/market-cap/"
MCAP_PATTERN = re.compile(r'>Market Cap\s*<div[^>]*>.*?-->([\d.]+)([TBM])<', re.S)

EMISORES = [
    ("iCOLCAP", "ICOLCAP"),
    ("Ecopetrol", "ECOPETROL"),
    ("Grupo Cibest PF", "CIBEST"),
    ("ISA", "ISA"),
    ("Cementos Argos", "CEMARGOS"),
    ("Grupo Sura PF", "GRUPOSURA"),
    ("Grupo Argos", "GRUPOARGOS"),
    ("Grupo Energía Bogotá", "GEB"),
    ("Mineros", "MINEROS"),
    ("Celsia", "CELSIA"),
    ("Corficolombiana", "CORFICOLCF"),
    ("Grupo Aval PF", "GRUPOAVAL"),
]

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}


def _parse_fecha(s):
    # formats like "28 oct 26"
    dia, mes_txt, anio2 = s.split(" ")
    mes = MESES[mes_txt.strip(".").lower()]
    anio = 2000 + int(anio2)
    return datetime.date(anio, mes, int(dia))


def _fetch_series(code):
    url = URL_TMPL.format(code=code)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    rows = data["graphData"][1:]
    series = {}
    for fecha_str, precio in rows:
        try:
            d = _parse_fecha(fecha_str)
        except Exception:
            continue
        if precio is not None:
            series[d] = float(precio)
    return series


def _baseline_before(series, cutoff_date):
    candidates = [d for d in series if d < cutoff_date]
    if not candidates:
        return None
    return series[max(candidates)]


def _pct_changes(series, today):
    if not series:
        return None, None, None, None
    dates_sorted = sorted(series)
    last_date = dates_sorted[-1]
    price = series[last_date]

    prev_dates = [d for d in dates_sorted if d < last_date]
    prev_close = series[prev_dates[-1]] if prev_dates else None
    pct_day = ((price - prev_close) / prev_close * 100) if prev_close else None

    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    month_base = _baseline_before(series, month_start)
    year_base = _baseline_before(series, year_start)
    pct_month = ((price - month_base) / month_base * 100) if month_base else None
    pct_year = ((price - year_base) / year_base * 100) if year_base else None

    return price, pct_day, pct_month, pct_year


def _fetch_market_cap_cop_b(codigo):
    """Market cap in miles de millones COP (COP billions, 10^9)."""
    url = MCAP_URL_TMPL.format(code=codigo)
    req = urllib.request.Request(url, headers=MCAP_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    m = MCAP_PATTERN.search(html)
    if not m:
        return None
    value, unit = float(m.group(1)), m.group(2)
    scale = {"T": 1000, "B": 1, "M": 0.001}[unit]
    return value * scale


def build_bvc_data(today=None):
    today = today or datetime.date.today()
    out = []
    for nombre, codigo in EMISORES:
        try:
            series = _fetch_series(codigo)
            price, pct_day, pct_month, pct_year = _pct_changes(series, today)
        except Exception:
            price = pct_day = pct_month = pct_year = None
        if codigo == "ICOLCAP":
            market_cap_b = None
        else:
            try:
                market_cap_b = _fetch_market_cap_cop_b(codigo)
            except Exception:
                market_cap_b = None
        out.append({
            "nombre": nombre, "codigo": codigo, "market_cap_b": market_cap_b,
            "precio": price, "pct_day": pct_day, "pct_month": pct_month, "pct_year": pct_year,
        })
    return out
