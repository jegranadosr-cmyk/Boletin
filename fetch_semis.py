"""Fetch market cap + %dia/%mes/%ano for the top semiconductor-chain companies.

Market cap: companiesmarketcap.com (a meta description tag states it in plain
text, e.g. "has a market cap of $2.260 Trillion USD" -- cheap and reliable to
regex, shared with fetch_market.fetch_market_cap_b). %dia/%mes/%ano: reuses
fetch_market's Yahoo Finance chart API.

CXMT (ChangXin Memory Technologies) IPO'd on Shanghai's STAR Market on
2026-07-27 (ticker 688825.SS, IPO price 8.66 CNY), so like SpaceX in the
Ocho Magnificas it has no full year of trading yet: %pct_year falls back to
the change since its IPO price instead of a 1-year-ago close.
"""
import socket

import fetch_market as fm

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

# (nombre, ticker Yahoo o None, slug companiesmarketcap.com o None).
# Order doesn't matter here anymore -- build_semis_data sorts by market cap.
EMPRESAS = [
    ("TSMC", "TSM", "tsmc"),
    ("Nvidia", "NVDA", "nvidia"),
    ("Broadcom", "AVGO", "broadcom"),
    ("Samsung", "005930.KS", "samsung"),
    ("Micron", "MU", "micron-technology"),
    ("SK Hynix", "000660.KS", "sk-hynix"),
    ("AMD", "AMD", "amd"),
    ("ASML", "ASML", "asml"),
    ("Qualcomm", "QCOM", "qualcomm"),
    ("Intel", "INTC", "intel"),
    ("CXMT", "688825.SS", "cxmt"),
]

# Companies that IPO'd within the last year have no year-start baseline in
# Yahoo's series, so pct_year falls back to the change since IPO price.
IPO_PRICE = {"CXMT": 8.66}


def build_semis_data(limit=None):
    out = []
    for nombre, ticker, slug in EMPRESAS:
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
            ipo_price = IPO_PRICE.get(nombre)
            if ipo_price and pct_year is None and r.get("price") is not None:
                pct_year = (r["price"] - ipo_price) / ipo_price * 100
        except Exception:
            pct_day = pct_month = pct_year = None
        out.append({
            "nombre": nombre, "market_cap_b": mcap,
            "pct_day": pct_day, "pct_month": pct_month, "pct_year": pct_year,
        })

    out.sort(key=lambda x: x["market_cap_b"] if x["market_cap_b"] is not None else -1, reverse=True)
    return out[:limit] if limit else out
