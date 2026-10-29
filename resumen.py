"""Generate the 'Resumen ejecutivo' bullet points and headline from the computed data,
following the style/structure observed in real Unvesting bulletins.
"""


def fmt_pct(v, decimals=2):
    if v is None:
        return "-"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def fmt_money(v, decimals=2):
    if v is None:
        return "-"
    return f"{v:,.{decimals}f}"


def generate_headline(sector_etfs):
    valid = [s for s in sector_etfs if s["pct_day"] is not None]
    if not valid:
        return "Mercados mixtos en la jornada"
    top = max(valid, key=lambda s: s["pct_day"])
    if top["pct_day"] >= 0:
        return f"{top['nombre']} lidera el avance de los mercados"
    worst = min(valid, key=lambda s: s["pct_day"])
    return f"{worst['nombre']} presiona los mercados a la baja"


def generate_rate_bullets(tasas):
    bullets = []
    for t in tasas:
        if t["tasa"] is None:
            continue
        label = t.get("tasa_label") or f"{t['tasa']:.2f}%"
        bullets.append(f"Tasa {t['banco']} ({t['pais']}): {label} (desde {t['fecha']}).")
    return bullets


def generate_bullets(data):
    bullets = []
    bullets.extend(generate_rate_bullets(data.get("tasas_bancos_centrales", [])))

    magnificas = [m for m in data["siete_magnificas"] if m["pct_day"] is not None]
    if magnificas:
        avg = sum(m["pct_day"] for m in magnificas) / len(magnificas)
        bullets.append(f"Las 8 Magníficas suben {avg:.2f}% en promedio." if avg >= 0
                        else f"Las 8 Magníficas caen {abs(avg):.2f}% en promedio.")

    sectores_validos = [s for s in data["etfs_sectoriales"] if s["pct_day"] is not None]
    if sectores_validos:
        top_sector = max(sectores_validos, key=lambda s: s["pct_day"])
        bullets.append(f"Sector {top_sector['nombre']} ({top_sector['ticker']}) lidera con {fmt_pct(top_sector['pct_day'])}.")

    sp500 = data["indicadores"].get("S&P 500")
    if sp500 and sp500["pct_day"] is not None:
        verbo = "avanza" if sp500["pct_day"] >= 0 else "retrocede"
        bullets.append(f"El S&P 500 {verbo} {abs(sp500['pct_day']):.2f}% al cierre.")

    if magnificas:
        top_mag = max(magnificas, key=lambda m: m["pct_day"])
        bullets.append(f"{top_mag['nombre_empresa']} destaca con {fmt_pct(top_mag['pct_day'])}.")

    usdcop = data["divisas"].get("USD/COP")
    dxy = data["divisas"].get("DXY")
    if usdcop and usdcop["pct_day"] is not None:
        verbo = "se debilita" if usdcop["pct_day"] >= 0 else "se fortalece"
        dxy_txt = ""
        if dxy and dxy["pct_day"] is not None:
            tono = "al alza" if dxy["pct_day"] >= 0 else "a la baja"
            dxy_txt = f", en una jornada de dólar global {tono} (DXY {fmt_pct(dxy['pct_day'])})"
        bullets.append(f"El peso {verbo} a ${fmt_money(usdcop['price'])} ({fmt_pct(usdcop['pct_day'])}){dxy_txt}.")

    trm = data.get("trm")
    if trm and usdcop:
        rel = "debajo" if trm["valor"] < usdcop["price"] else "encima"
        bullets.append(f"TRM de hoy ${fmt_money(trm['valor'])}, {rel} del mercado (${fmt_money(usdcop['price'])}).")

    oro = data["materias_primas"].get("Oro")
    if oro and oro["pct_day"] is not None:
        if oro["pct_day"] >= 0:
            bullets.append(f"Oro (COMEX) sube {oro['pct_day']:.2f}%, refugio ante aversión al riesgo.")
        else:
            bullets.append(f"Oro (COMEX) retrocede {abs(oro['pct_day']):.2f}%, con menor demanda de refugio.")

    mercados_validos = [m for m in data["mercados_globales"] if m["pct_day"] is not None and m["ticker"] != "WTI"]
    emergentes = [m for m in mercados_validos if m["nombre"] in ("MCHI", "IEMG", "EMXC", "EWY", "EWT", "INDA")]
    if emergentes:
        top_em = max(emergentes, key=lambda m: abs(m["pct_day"]))
        verbo = "avanza" if top_em["pct_day"] >= 0 else "retrocede"
        bullets.append(f"{top_em['nombre']} - {top_em['pais']} {verbo} {fmt_pct(top_em['pct_day'])} en mercados emergentes.")

    desarrollados = [m for m in mercados_validos if m["nombre"] in ("DAX", "CAC 40", "Nikkei 225", "EFA", "EWU", "EWP")]
    if desarrollados:
        top_dev = max(desarrollados, key=lambda m: abs(m["pct_day"]))
        verbo = "lidera" if top_dev["pct_day"] >= 0 else "pesa mas"
        bullets.append(f"{top_dev['nombre']} ({top_dev['pais']}) {verbo} entre los desarrollados con {fmt_pct(top_dev['pct_day'])}.")

    wti = next((m for m in data["mercados_globales"] if m["ticker"] == "WTI"), None)
    if wti and wti["pct_day"] is not None:
        tono = "presion alcista" if wti["pct_day"] >= 0 else "presion bajista"
        bullets.append(f"WTI se ubica en ${fmt_money(wti['price'])} ({fmt_pct(wti['pct_day'])}), {tono} en energia.")

    btc = data["indicadores"].get("BITCOIN")
    if btc and btc["pct_day"] is not None:
        verbo = "avanza" if btc["pct_day"] >= 0 else "retrocede"
        tono = "en linea con" if btc["pct_day"] >= 0 else "en contra de"
        bullets.append(f"Bitcoin {verbo} {fmt_pct(btc['pct_day'])}, {tono} el apetito por riesgo.")

    rut = data["indicadores"].get("RUSSELL 2000")
    if rut and rut["pct_day"] is not None:
        verbo = "avanza" if rut["pct_day"] >= 0 else "retrocede"
        tono = "impulsado por" if rut["pct_day"] >= 0 else "presionado por"
        bullets.append(f"Russell 2000 {verbo} {fmt_pct(rut['pct_day'])}, {tono} pequeñas empresas.")

    cafe = data.get("cafe")
    if cafe and cafe.get("precio_carga_125kg"):
        bullets.append(
            f"Cafe colombiano pergamino seco: ${cafe['precio_carga_125kg']:,.0f} COP/carga 125 Kg "
            f"(Fedecafe, {cafe['fecha']})."
        )

    return bullets
