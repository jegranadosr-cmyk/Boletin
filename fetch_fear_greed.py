"""Fetch CNN's Fear & Greed Index. Their API 418s requests without a Referer/Origin
that looks like it came from the actual fear-and-greed page -- not an auth
requirement, just basic bot-filtering on the edge.
"""
import json
import socket
import urllib.request

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Origin": "https://www.cnn.com",
    "Accept-Language": "en-US,en;q=0.9",
}

RATING_ES = {
    "extreme fear": "Miedo extremo",
    "fear": "Miedo",
    "neutral": "Neutral",
    "greed": "Codicia",
    "extreme greed": "Codicia extrema",
}


def fetch_fear_greed():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())

    fg = data["fear_and_greed"]
    score = fg["score"]
    month_ago = fg["previous_1_month"]
    rating = fg["rating"]

    return {
        "score": score,
        "rating": rating,
        "rating_es": RATING_ES.get(rating, rating),
        "change_month": score - month_ago if month_ago is not None else None,
    }
