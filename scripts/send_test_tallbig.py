"""One-off test script (not part of the production pipeline): generates the
bulletin with fresh data via the existing main.py, then renders page1/page2
with two test tweaks layered on top of the UNMODIFIED production templates
(no template/CSS file is touched):
  1. a taller fixed canvas (3960px raw, same figure BoletinMacro uses for
     its page1) instead of a screenshot sized to content -- this makes the
     bulletin compress to a narrower (~1293px), more legible width when
     WhatsApp recompresses it, same mechanism observed in BoletinMacro.
  2. a modest font-size bump (CSS injected at runtime via add_style_tag)
     on the main text-bearing elements, verified beforehand not to overflow
     the fixed-width columns or the taller canvas.
Sends the result to Telegram captioned as a test, then is meant to be
deleted (along with its workflow) once it's run once.
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
viewport = {"width": 1000, "height": TARGET_RAW_HEIGHT // SCALE}

FONT_BUMP_CSS = """
table.boletin-table { font-size: 13.5px; }
table.boletin-table thead th { font-size: 11.5px; }
table.boletin-table caption.caption-lg { font-size: 17px; }
.indicator-card .value { font-size: 19px; }
.indicator-card .name { font-size: 11px; }
.indicator-card .change-row .pct { font-size: 14px; }
.indicator-card .change-label { font-size: 10px; }
.section-title { font-size: 14px; }
.sector-card .ticker, .sector-card .nombre { font-size: 15.5px; }
.sector-card .pct { font-size: 12.5px; }
.sector-card .stat-label { font-size: 10.5px; }
.bar-chart .bar-val { font-size: 12px; }
.bar-chart .bar-label { font-size: 11px; }
"""

out_dir = "render_out"
os.makedirs(out_dir, exist_ok=True)
out_paths = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, template in [("page1", "page1.html"), ("page2", "page2.html")]:
        html_str = rd.render_html(data, template)
        tmp_html = os.path.abspath(os.path.join(out_dir, f"_send_{name}.tmp.html"))
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(html_str)

        page = browser.new_page(viewport=viewport, device_scale_factor=SCALE)
        page.goto("file:///" + tmp_html.replace("\\", "/"))
        page.add_style_tag(content=FONT_BUMP_CSS)
        page.wait_for_timeout(200)

        page_w = page.evaluate("document.querySelector('.page').scrollWidth")
        page_h = page.evaluate("document.querySelector('.page').scrollHeight")
        print(f"{name}: scrollWidth={page_w}/{viewport['width']}, scrollHeight={page_h}/{viewport['height']}")
        if page_w > viewport["width"]:
            raise RuntimeError(f"{name} desborda horizontalmente: {page_w}px > {viewport['width']}px")
        if page_h > viewport["height"]:
            raise RuntimeError(f"{name} excede el alto del lienzo: {page_h}px > {viewport['height']}px (se cortaria)")

        page.evaluate(f"document.querySelector('.page').style.minHeight = '{viewport['height']}px'")
        page.wait_for_timeout(300)
        out_path = os.path.join(out_dir, f"{name}_tallbig.png")
        page.screenshot(path=out_path)
        page.close()
        os.remove(tmp_html)
        out_paths.append(out_path)
    browser.close()

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]
caption = f"PRUEBA -- lienzo alto (3960px) + letra un poco mas grande -- {data['fecha_larga']}"
result = st.send_media_group(token, chat_id, out_paths, caption=caption)
print(result)
if not result.get("ok"):
    raise RuntimeError(f"Telegram send failed: {result}")
