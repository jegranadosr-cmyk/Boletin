"""Fetch Colombia-specific data: official TRM and Fedecafe coffee price."""
import re
import io
import urllib.request

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

TRM_URL = "https://www.datos.gov.co/resource/mcec-87by.json?$order=vigenciadesde%20DESC&$limit=1"
CAFE_PDF_URL = "https://federaciondecafeteros.org/wp-content/uploads/2026/03/precio_cafe.pdf"

MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}


def fetch_trm():
    import json
    req = urllib.request.Request(TRM_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if not data:
        return None
    row = data[0]
    return {
        "valor": float(row["valor"]),
        "vigenciadesde": row["vigenciadesde"][:10],
    }


def fetch_cafe_pergamino():
    import pdfplumber
    req = urllib.request.Request(CAFE_PDF_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        text = pdf.pages[0].extract_text()

    price_match = re.search(r"pergamino seco FR 94\s+([\d,]+)\s*COP", text)
    date_match = re.search(r"([A-Za-z]+)\s+(\d{1,2})\s*/\s*(\d{4})", text)

    if not price_match or not date_match:
        return None

    price = int(price_match.group(1).replace(",", ""))
    mes_nombre = date_match.group(1).strip().lower()
    dia = date_match.group(2).zfill(2)
    anio = date_match.group(3)
    mes_num = MESES.get(mes_nombre)
    iso_date = f"{anio}-{mes_num}-{dia}" if mes_num else None

    return {"precio_carga_125kg": price, "fecha": iso_date}
