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


SIETE_MAGNIFICAS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META"]

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
    ("^SOX", "Semiconductores (índice)"),
    ("XLB", "Materiales"),
    ("SMH", "Semiconductores"),
    ("KRE", "Banca regional"),
    ("GDX", "Mineras de oro"),
]

MERCADOS_GLOBALES = [
    ("DAX", "^GDAXI", "Alemania"),
    ("CAC 40", "^FCHI", "Francia"),
    ("Nikkei 225", "^N225", "Japón"),
    ("EFA", "EFA", "Desarrollados ex-EE.UU."),
    ("MCHI", "MCHI", "China"),
    ("IEMG", "IEMG", "Emergentes (amplio)"),
    ("EMXC", "EMXC", "Emergentes ex-China"),
    ("EWY", "EWY", "Corea del Sur"),
    ("EWT", "EWT", "Taiwán"),
    ("INDA", "INDA", "India"),
    ("EWU", "EWU", "Reino Unido"),
    ("EWP", "EWP", "España"),
    ("WTI", "CL=F", "Petróleo (EE.UU.)"),
]

MATERIAS_PRIMAS = [
    ("Brent", "BZ=F"),
    ("Oro", "GC=F"),
    ("Plata", "SI=F"),
    ("Gas natural", "NG=F"),
]

EXTRA = {
    "DXY": "DX-Y.NYB",
}
