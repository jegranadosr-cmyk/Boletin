import datetime
import json
import os
import sys
import traceback

import fetch_market as fm
import fetch_colombia as fc
import fetch_bvc as fb
import fetch_rates as fr
import fetch_macro as fmac
import fetch_fear_greed as ffg
import fetch_semis as fsem
import resumen as rs
import render as rd
import send_telegram as st

COMPANY_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet",
    "AMZN": "Amazon", "NVDA": "NVIDIA", "TSLA": "Tesla", "META": "Meta",
    "SPACEX": "SpaceX",
}

MESES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def build_data():
    today = datetime.date.today()
    errors = []
    data = {"fecha": today}

    # Ocho Magnificas (Siete + SpaceX)
    siete = []
    for t in fm.SIETE_MAGNIFICAS:
        yahoo_ticker = fm.SIETE_MAGNIFICAS_TICKERS[t]
        mcap, mcap_err = safe(fm.fetch_market_cap_b, fm.SIETE_MAGNIFICAS_MCAP_SLUGS[t])
        if mcap_err:
            errors.append(f"{t} mcap: {mcap_err}")
        if yahoo_ticker is None:
            # Privately held (SpaceX): no ticker, no daily price history.
            siete.append({"ticker": COMPANY_NAMES[t], "nombre_empresa": COMPANY_NAMES[t], "market_cap_b": mcap,
                          "pct_day": None, "pct_month": None, "pct_year": None})
            continue
        r, err = safe(fm.pct_changes_for_symbol, yahoo_ticker)
        if err:
            errors.append(f"{t}: {err}")
            siete.append({"ticker": t, "nombre_empresa": COMPANY_NAMES[t], "market_cap_b": mcap,
                          "pct_day": None, "pct_month": None, "pct_year": None})
        else:
            siete.append({"ticker": t, "nombre_empresa": COMPANY_NAMES[t], "market_cap_b": mcap,
                          **{k: v for k, v in r.items() if k not in ("series", "price")}})

    siete.sort(key=lambda x: x["market_cap_b"] if x["market_cap_b"] is not None else -1, reverse=True)
    data["siete_magnificas"] = siete

    # Top empresas de la cadena de semiconductores (market cap + variaciones)
    r, err = safe(fsem.build_semis_data, 10)
    data["semis"] = r if not err else []
    if err:
        errors.append(f"Semis: {err}")

    # Indicadores (S&P500, Nasdaq100, Dow, Russell2000, VIX, MOVE, Bitcoin)
    indicadores = {}
    for nombre, t in fm.INDICADORES.items():
        r, err = safe(fm.pct_changes_for_symbol, t)
        if err:
            errors.append(f"{nombre}: {err}")
            indicadores[nombre] = {"price": None, "pct_day": None}
        else:
            indicadores[nombre] = {k: v for k, v in r.items() if k != "series"}
    data["indicadores"] = indicadores

    # Fear & Greed Index (CNN) -- shown right under Bitcoin
    r, err = safe(ffg.fetch_fear_greed)
    data["fear_greed"] = r
    if err:
        errors.append(f"FearGreed: {err}")

    # ETFs sectoriales
    sectoriales = []
    for ticker, nombre in fm.ETFS_SECTORIALES:
        display_ticker = ticker.lstrip("^")
        r, err = safe(fm.pct_changes_for_symbol, ticker)
        if err:
            errors.append(f"{ticker}: {err}")
            sectoriales.append({"ticker": display_ticker, "nombre": nombre, "price": None, "pct_day": None})
        else:
            sectoriales.append({"ticker": display_ticker, "nombre": nombre, **{k: v for k, v in r.items() if k != "series"}})
    data["etfs_sectoriales"] = sectoriales

    # Mercados globales
    globales = []
    for nombre, ticker, pais in fm.MERCADOS_GLOBALES:
        r, err = safe(fm.pct_changes_for_symbol, ticker)
        if err:
            errors.append(f"{ticker}: {err}")
            globales.append({"nombre": nombre, "ticker": nombre, "pais": pais, "price": None, "pct_day": None,
                             "pct_month": None, "pct_year": None})
        else:
            globales.append({"nombre": nombre, "ticker": nombre, "pais": pais, **{k: v for k, v in r.items() if k != "series"}})
    data["mercados_globales"] = globales

    # Divisas
    divisas = {}
    r, err = safe(fm.pct_changes_for_symbol, fm.EXTRA["DXY"])
    if err:
        divisas["DXY"] = {"price": None, "pct_day": None, "pct_month": None, "pct_year": None}
        errors.append(f"DXY: {err}")
    else:
        divisas["DXY"] = {k: v for k, v in r.items() if k != "series"}

    r, err = safe(fm.pct_changes_for_symbol, "COP=X")
    if err:
        divisas["USD/COP"] = {"price": None, "pct_day": None, "pct_month": None, "pct_year": None}
        errors.append(f"USD/COP: {err}")
    else:
        divisas["USD/COP"] = {k: v for k, v in r.items() if k != "series"}

    for nombre, (sym_num, sym_den, invert) in {
        "EUR/COP": ("EURUSD=X", "COP=X", False),
    }.items():
        r, err = safe(fm.cross_pct_changes, sym_num, sym_den, invert)
        divisas[nombre] = r if not err else {"price": None, "pct_day": None, "pct_month": None, "pct_year": None}
        if err:
            errors.append(f"{nombre}: {err}")

    for nombre, ticker in {"USD/EUR": "USDEUR=X", "USD/CNY": "USDCNY=X", "USD/JPY": "USDJPY=X"}.items():
        r, err = safe(fm.pct_changes_for_symbol, ticker)
        if err:
            divisas[nombre] = {"price": None, "pct_day": None, "pct_month": None, "pct_year": None}
            errors.append(f"{nombre}: {err}")
        else:
            divisas[nombre] = {k: v for k, v in r.items() if k != "series"}

    data["divisas"] = divisas

    # Cafe Fedecafe (fetched first so it can be slotted into materias primas below)
    r, err = safe(fc.fetch_cafe_pergamino)
    data["cafe"] = r
    if err:
        errors.append(f"Cafe: {err}")

    # Materias primas
    materias = {}
    for nombre, ticker in fm.MATERIAS_PRIMAS:
        r, err = safe(fm.pct_changes_for_symbol, ticker)
        if err:
            materias[nombre] = {"price": None, "pct_day": None, "pct_month": None, "pct_year": None}
            errors.append(f"{nombre}: {err}")
        else:
            materias[nombre] = {k: v for k, v in r.items() if k != "series"}

    data["materias_primas"] = materias

    # TRM oficial
    r, err = safe(fc.fetch_trm)
    data["trm"] = r
    if err:
        errors.append(f"TRM: {err}")

    # Tasas de interes de politica monetaria (bancos centrales)
    r, err = safe(fr.fetch_policy_rates)
    data["tasas_bancos_centrales"] = r if not err else []
    if err:
        errors.append(f"TasasBC: {err}")

    # Deuda/PIB y bono a 10 anos: Francia, EE.UU., China, Japon, Colombia
    r, err = safe(fmac.fetch_debt_and_bonds)
    data["deuda_bonos"] = r if not err else []
    if err:
        errors.append(f"DeudaBonos: {err}")

    # Resumen coyuntural: una tabla por pais con tasa de politica monetaria,
    # deuda/PIB y bono a 10 anos. Francia usa la tasa del BCE (Eurozona).
    rate_by_country = {t["pais"]: t for t in data["tasas_bancos_centrales"]}
    RATE_LOOKUP = {
        "Francia": "Eurozona", "EE.UU.": "EE.UU.", "China": "China",
        "Japón": "Japón", "Colombia": "Colombia",
    }
    resumen_coyuntural = []
    for d in data["deuda_bonos"]:
        rate = rate_by_country.get(RATE_LOOKUP.get(d["pais"]))
        if rate and rate["tasa"] is not None:
            tasa_label = f"{rate['tasa_label']} ({rate['banco']})"
        else:
            tasa_label = "-"
        resumen_coyuntural.append({
            "pais": d["pais"], "tasa_label": tasa_label,
            "deuda_pib": d["deuda_pib"], "bono_10y": d["bono_10y"], "bono_5y": d.get("bono_5y"),
        })
    data["resumen_coyuntural"] = resumen_coyuntural

    # BVC acciones (price + %dia/%mes/%ano all come from La Republica's historic API)
    r, err = safe(fb.build_bvc_data, today)
    if err:
        errors.append(f"BVC: {err}")
        data["bvc"] = [{"nombre": n, "codigo": c, "market_cap_b": None, "precio": None, "pct_day": None, "pct_month": None, "pct_year": None}
                        for n, c in fb.EMISORES]
    else:
        data["bvc"] = r

    data["errors"] = errors
    return data


def main():
    data = build_data()

    if data["errors"]:
        print("WARNINGS during fetch:", file=sys.stderr)
        for e in data["errors"]:
            print(" -", e, file=sys.stderr)

    data["headline"] = rs.generate_headline(data["etfs_sectoriales"])
    data["bullets"] = rs.generate_bullets(data)

    today = data["fecha"]
    data["fecha_larga"] = f"{DIAS_ES[today.weekday()].capitalize()}, {today.day} de {MESES_ES[today.month]} de {today.year}"

    with open("data_dump.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print("Data built OK. Dumped to data_dump.json")
    return data


def run(send=True):
    data = main()

    p1, p2 = rd.render_bulletin(data, "render_out")
    print(f"Rendered: {p1}, {p2}")

    if send:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, skipping send.", file=sys.stderr)
            return data
        result = st.send_media_group(token, chat_id, [p1, p2])
        print(json.dumps(result, indent=2))
        if not result.get("ok"):
            raise RuntimeError(f"Telegram send failed: {result}")
    return data


if __name__ == "__main__":
    try:
        send_flag = os.environ.get("SKIP_SEND") != "1"
        run(send=send_flag)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
