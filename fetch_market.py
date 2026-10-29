"""Fetch market data from Yahoo Finance's public chart API (no key required)."""
import datetime
import socket
import time
import urllib.request
import urllib.error
import json

# This environment has a broken/slow IPv6 route: every connection attempts IPv6
# first, hangs for ~15s, then falls back to IPv4. Force IPv4-only resolution so
# requests connect immediately instead of eating a timeout on every call.
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MCAP_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MCAP_URL = "https://companiesmarketcap.com/{slug}/marketcap/"


def fetch_market_cap_b(slug):
    """Market cap in billions USD, scraped from companiesmarketcap.com's meta
    description tag (e.g. "has a market cap of $2.260 Trillion USD")."""
    import re
    req = urllib.request.Request(MCAP_URL.format(slug=slug), headers=MCAP_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    m = re.search(r"market cap of \$([\d.]+) (Trillion|Billion) USD", html)
    if not m:
        return None
    value, unit = m.groups()
    value = float(value)
    return value * 1000 if unit == "Trillion" else value


def fetch_private_company_changes(slug):
    """For non-public companies tracked by companiesmarketcap.com (e.g. SpaceX)
    via secondary-market share price discovery -- returns (pct_day, pct_year)
    from their "Change (1 day)" / "Change (1 year)" stat boxes. Either can come
    back None if the site shows "N/A" (no secondary-market trades in that
    window) -- there is no "1 month" stat at all on these pages.
    """
    import re
    req = urllib.request.Request(MCAP_URL.format(slug=slug), headers=MCAP_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    def _extract(label):
        # Scope the match to a single info-box (no other "line1" in between),
        # otherwise a non-greedy .*? would span across multiple stat boxes and
        # grab the wrong value.
        m = re.search(
            r'<div class="line1">((?:(?!<div class="line1">).)*?)</div>\s*'
            r'<div class="line2">' + re.escape(label) + r'</div>',
            html, re.S,
        )
        if not m:
            return None
        pm = re.search(r'(-?[\d.]+)%', m.group(1))
        return float(pm.group(1)) if pm else None

    return _extract("Change (1 day)"), _extract("Change (1 year)")


def _get_json(url, retries=3, timeout=15):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def fetch_chart(symbol, range_="2y", interval="1d"):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range={range_}&interval={interval}"
    )
    data = _get_json(url)
    result = data["chart"]["result"]
    if not result:
        raise ValueError(f"No data for {symbol}")
    r = result[0]
    meta = r["meta"]
    timestamps = r.get("timestamp", [])
    closes = r["indicators"]["quote"][0].get("close", [])
    series = {}
    for ts, c in zip(timestamps, closes):
        if c is None:
            continue
        d = datetime.datetime.utcfromtimestamp(ts).date()
        series[d] = c
    return meta, series


def _baseline_before(series, cutoff_date):
    """Latest close strictly before cutoff_date."""
    candidates = [d for d in series if d < cutoff_date]
    if not candidates:
        return None
    best = max(candidates)
    return series[best]


def pct_changes_for_symbol(symbol, today=None):
    """Returns dict: price, pct_day, pct_month, pct_year. Raises on hard failure."""
    today = today or datetime.datetime.utcnow().date()
    meta, series = fetch_chart(symbol)
    price = meta.get("regularMarketPrice")
    pct_day = meta.get("regularMarketChangePercent")

    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    month_base = _baseline_before(series, month_start)
    year_base = _baseline_before(series, year_start)

    pct_month = ((price - month_base) / month_base * 100) if month_base else None
    pct_year = ((price - year_base) / year_base * 100) if year_base else None

    return {
        "price": price,
        "pct_day": pct_day,
        "pct_month": pct_month,
        "pct_year": pct_year,
        "series": series,
    }


def cross_pct_changes(sym_num, sym_den, invert_num=False, today=None):
    """Compute pct changes for a cross rate built from two Yahoo FX symbols.

    If invert_num is False: cross = price(sym_num) * price(sym_den)   (e.g. EURUSD * USDCOP)
    If invert_num is True:  cross = price(sym_den) / price(sym_num)   (e.g. USDCOP / USDMXN)
    """
    today = today or datetime.datetime.utcnow().date()
    meta_a, series_a = fetch_chart(sym_num)
    meta_b, series_b = fetch_chart(sym_den)

    def combine(a, b):
        return (b / a) if invert_num else (a * b)

    price = combine(meta_a["regularMarketPrice"], meta_b["regularMarketPrice"])

    common_dates = sorted(set(series_a) & set(series_b))
    cross_series = {d: combine(series_a[d], series_b[d]) for d in common_dates}

    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    prev_dates = [d for d in common_dates if d < today]
    prev_close = cross_series[prev_dates[-1]] if prev_dates else None
    pct_day = ((price - prev_close) / prev_close * 100) if prev_close else None

    month_base = _baseline_before(cross_series, month_start)
    year_base = _baseline_before(cross_series, year_start)
    pct_month = ((price - month_base) / month_base * 100) if month_base else None
    pct_year = ((price - year_base) / year_base * 100) if year_base else None

    return {"price": price, "pct_day": pct_day, "pct_month": pct_month, "pct_year": pct_year}


SIETE_MAGNIFICAS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "SPACEX"]

# SpaceX has no ticker -- it's privately held, so there is no Yahoo quote for it,
# only a market cap (from its latest funding-round valuation, tracked by
# companiesmarketcap.com same as other private companies like CXMT).
SIETE_MAGNIFICAS_TICKERS = {
    "AAPL": "AAPL", "MSFT": "MSFT", "GOOGL": "GOOGL", "AMZN": "AMZN",
    "NVDA": "NVDA", "TSLA": "TSLA", "META": "META", "SPACEX": None,
}

SIETE_MAGNIFICAS_MCAP_SLUGS = {
    "AAPL": "apple",
    "MSFT": "microsoft",
    "GOOGL": "alphabet-google",
    "AMZN": "amazon",
    "NVDA": "nvidia",
    "TSLA": "tesla",
    "META": "meta-platforms",
    "SPACEX": "spacex",
}

INDICADORES = {
    "S&P 500": "^GSPC",
    "S&P 500 EQUIPONDERADO": "RSP",
    "NASDAQ-100": "^NDX",
    "DOW JONES": "^DJI",
    "RUSSELL 2000": "^RUT",
    "VIX": "^VIX",
    "MOVE": "^MOVE",
    "BITCOIN": "BTC-USD",
}

ETFS_SECTORIALES = [
    ("XLK", "Tecnología"),
    ("XLF", "Financiero"),
    ("XLI", "Industrial"),
    ("XLV", "Salud"),
    ("XLE", "Energía"),
    ("XLP", "Cons. básico"),
    ("XLC", "Comunicación"),
    ("XLRE", "Bienes raíces"),
    ("AIQ", "IA / Big Data"),
    ("XLU", "Utilities"),
    ("XLY", "Cons. discrecional"),
    ("XLB", "Materiales"),
    ("SMH", "Semiconductores"),
    ("KRE", "Banca regional"),
    ("GDX", "Mineras de oro"),
]

MERCADOS_GLOBALES = [
    ("DAX", "^GDAXI", "Alemania"),
    ("EWZ", "EWZ", "Brasil"),
    ("MCHI", "MCHI", "China"),
    ("EWY", "EWY", "Corea del Sur"),
    ("EWP", "EWP", "España"),
    ("CAC 40", "^FCHI", "Francia"),
    ("INDA", "INDA", "India"),
    ("EWI", "EWI", "Italia"),
    ("Nikkei 225", "^N225", "Japón"),
    ("EWW", "EWW", "México"),
    ("EWU", "EWU", "Reino Unido"),
    ("EWT", "EWT", "Taiwán"),
    ("EFA", "EFA", "Desarrollados ex-EE.UU."),
    ("IEMG", "IEMG", "Emergentes"),
    ("EMXC", "EMXC", "Emergentes ex-China"),
    ("ACWI", "ACWI", "Mundial"),
]

MATERIAS_PRIMAS = [
    ("Brent", "BZ=F"),
    ("Oro", "GC=F"),
    ("Plata", "SI=F"),
]

EXTRA = {
    "DXY": "DX-Y.NYB",
}
