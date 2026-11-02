"""One-off test script (not part of the production pipeline): resends the
same images from the previous test (tall canvas + bigger font + filled
content, no dead space) plus a matching 2-page PDF (vector, same layout).
No template/CSS file is touched -- everything is injected at runtime via
add_style_tag. Sends to Telegram, then is meant to be deleted along with
its workflow.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

import main as bmain  # noqa: E402
import render as rd  # noqa: E402
import send_telegram as st  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

data = bmain.main()

TARGET_RAW_HEIGHT = 3960
SCALE = 2
viewport_png = {"width": 1000, "height": TARGET_RAW_HEIGHT // SCALE}
viewport_pdf = {"width": 1000, "height": 400}  # height irrelevant for pdf() call itself

FILL_CSS = """
table.boletin-table { font-size: 13.5px; margin-bottom: 20px; }
table.boletin-table thead th { font-size: 11.5px; padding: 11px 7px 9px; }
table.boletin-table tbody td { padding: 11px 7px; }
table.boletin-table caption.caption-lg { font-size: 17px; padding: 13px 0; }
.chart-block { margin-bottom: 20px; }
.bar-chart { height: 205px; }
.bar-chart .bar-val { font-size: 12px; }
.bar-chart .bar-label { font-size: 11px; }
.section-title { font-size: 14.5px; margin: 6px 0 14px; }
.indicator-card { padding: 11px 16px; margin-bottom: 12px; gap: 14px; }
.indicator-card .value { font-size: 20px; }
.indicator-card .name { font-size: 11px; }
.indicator-card .icon { width: 32px; height: 32px; font-size: 13px; }
.indicator-card .change-row .pct { font-size: 14.5px; }
.indicator-card .change-label { font-size: 10.5px; }
.sector-grid { gap: 13px; }
.sector-card { padding: 13px 6px; gap: 9px; }
.sector-card .ticker, .sector-card .nombre { font-size: 15.5px; }
.sector-card .pct { font-size: 12.5px; }
.sector-card .stat-label { font-size: 10.5px; }
.col-spread { justify-content: space-between; }
.content { justify-content: space-between; }
"""

out_dir = "render_out"
os.makedirs(out_dir, exist_ok=True)
png_paths = []
single_pdf_paths = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, template in [("page1", "page1.html"), ("page2", "page2.html")]:
        html_str = rd.render_html(data, template)
        tmp_html = os.path.abspath(os.path.join(out_dir, f"_fv3pdf_{name}.tmp.html"))
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(html_str)

        # PNG (tall fixed canvas, same as what was already sent)
        page = browser.new_page(viewport=viewport_png, device_scale_factor=SCALE)
        page.goto("file:///" + tmp_html.replace("\\", "/"))
        page.add_style_tag(content=FILL_CSS)
        page.wait_for_timeout(200)

        content_h = page.evaluate(
            "document.querySelector('.col-spread')?.scrollHeight || document.querySelector('.page').scrollHeight"
        )
        if content_h > viewport_png["height"]:
            raise RuntimeError(f"{name} excede el alto del lienzo: {content_h}px > {viewport_png['height']}px")

        page.evaluate(f"document.querySelector('.page').style.minHeight = '{viewport_png['height']}px'")
        page.wait_for_timeout(300)
        png_path = os.path.join(out_dir, f"{name}_fillv3_resend.png")
        page.screenshot(path=png_path)
        page.close()
        png_paths.append(png_path)

        # Matching PDF page: vector, native CSS width, content-sized height
        # (no reason to force the tall canvas in a PDF -- it's resolution
        # independent, so just size it to the real content like production does)
        pdf_page = browser.new_page(viewport={"width": 1000, "height": 400})
        pdf_page.goto("file:///" + tmp_html.replace("\\", "/"))
        pdf_page.add_style_tag(content=FILL_CSS)
        pdf_page.wait_for_timeout(200)
        h = pdf_page.evaluate("document.documentElement.scrollHeight")
        single_pdf = os.path.join(out_dir, f"_fv3_{name}.pdf")
        pdf_page.pdf(
            path=single_pdf, width="1000px", height=f"{h}px", print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        pdf_page.close()
        single_pdf_paths.append(single_pdf)

        os.remove(tmp_html)
    browser.close()

from pypdf import PdfWriter  # noqa: E402
writer = PdfWriter()
for p_ in single_pdf_paths:
    writer.append(p_)
merged_pdf = os.path.join(out_dir, "boletin_fillv3.pdf")
with open(merged_pdf, "wb") as f:
    writer.write(f)
for p_ in single_pdf_paths:
    os.remove(p_)

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]

img_result = st.send_media_group(token, chat_id, png_paths, caption=f"Lupa al mercado (prueba) -- {data['fecha_larga']}")
print("imagenes:", img_result)
if not img_result.get("ok"):
    raise RuntimeError(f"Telegram image send failed: {img_result}")

doc_result = st.send_document(token, chat_id, merged_pdf, caption=f"Lupa al mercado (prueba, PDF) -- {data['fecha_larga']}")
print("pdf:", doc_result)
if not doc_result.get("ok"):
    raise RuntimeError(f"Telegram PDF send failed: {doc_result}")
