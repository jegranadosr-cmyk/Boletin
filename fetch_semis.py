"""Fetch market cap + %dia/%mes/%ano for the top semiconductor-chain companies.

Market cap: companiesmarketcap.com (a meta description tag states it in plain
text, e.g. "has a market cap of $2.260 Trillion USD" -- cheap and reliable to
regex). %dia/%mes/%ano: reuses fetch_market's Yahoo Finance chart API.

CXMT (ChangXin Memory Technologies) is privately held / state-backed with no
public listing, so it has no ticker and is skipped entirely.
"""
import re
import socket
import urllib.request

import fetch_market as fm

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MCAP_URL = "https://companiesmarketcap.com/{slug}/marketcap/"

# (nombre, ticker Yahoo, slug companiesmarketcap.com) -- ordered by the ranking
# in the reference image; CXMT omitted (no public ticker).
EMPRESAS = [
    ("TSMC", "TSM", "tsmc"),
    ("Broadcom", "AVGO", "broadcom"),
    ("Samsung Electronics", "005930.KS", "samsung"),
    ("Micron", "MU", "micron-technology"),
    ("SK Hynix", "000660.KS", "sk-hynix"),
    ("AMD", "AMD", "amd"),
    ("ASML", "ASML", "asml"),
    ("Intel", "INTC", "intel"),
]


def _fetch_market_cap_b(slug):
    url = MCAP_URL.format(slug=slug)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    m = re.search(r"market cap of \$([\d.]+) (Trillion|Billion) USD", html)
    if not m:
        return None
    value, unit = m.groups()
    value = float(value)
    return value * 1000 if unit == "Trillion" else value


def build_semis_data(limit=None):
    out = []
    items = EMPRESAS[:limit] if limit else EMPRESAS
    for nombre, ticker, slug in items:
        try:
            mcap = _fetch_market_cap_b(slug)
        except Exception:
            mcap = None
        try:
            r = fm.pct_changes_for_symbol(ticker)
            pct_day, pct_month, pct_year = r["pct_day"], r["pct_month"], r["pct_year"]
        except Exception:
            pct_day = pct_month = pct_year = None
        out.append({
            "nombre": nombre, "market_cap_b": mcap,
            "pct_day": pct_day, "pct_month": pct_month, "pct_year": pct_year,
        })
    return out
