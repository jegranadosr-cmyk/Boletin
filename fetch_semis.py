"""Fetch market cap + %dia/%mes/%ano for the top semiconductor-chain companies.

Market cap: companiesmarketcap.com (a meta description tag states it in plain
text, e.g. "has a market cap of $2.260 Trillion USD" -- cheap and reliable to
regex, shared with fetch_market.fetch_market_cap_b). %dia/%mes/%ano: reuses
fetch_market's Yahoo Finance chart API.

CXMT (ChangXin Memory Technologies) is privately held / state-backed with no
public listing: no ticker, no market cap, no price history anywhere. It's kept
in the list (name only, "-" everywhere else) because it's part of the chain
narrative, not because the data exists.
"""
import socket

import fetch_market as fm

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

# (nombre, ticker Yahoo o None, slug companiesmarketcap.com o None) -- ordered
# by the ranking in the reference image.
EMPRESAS = [
    ("TSMC", "TSM", "tsmc"),
    ("Broadcom", "AVGO", "broadcom"),
    ("Samsung", "005930.KS", "samsung"),
    ("Micron", "MU", "micron-technology"),
    ("SK Hynix", "000660.KS", "sk-hynix"),
    ("AMD", "AMD", "amd"),
    ("ASML", "ASML", "asml"),
    ("Qualcomm", "QCOM", "qualcomm"),
    ("Intel", "INTC", "intel"),
]


def build_semis_data(limit=None):
    out = []
    items = EMPRESAS[:limit] if limit else EMPRESAS
    for nombre, ticker, slug in items:
        if ticker is None:
            out.append({
                "nombre": nombre, "market_cap_b": None,
                "pct_day": None, "pct_month": None, "pct_year": None,
            })
            continue
        try:
            mcap = fm.fetch_market_cap_b(slug)
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
