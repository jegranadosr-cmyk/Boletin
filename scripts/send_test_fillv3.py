"""One-off test script (not part of the production pipeline): fresh data +
tall fixed canvas (3960px) + a width-safe content/padding/font reflow that
fills the canvas on BOTH pages without leaving large blank gaps. No
template/CSS file is touched -- everything is injected at runtime via
add_style_tag. Verified beforehand (per-table scrollWidth vs container,
page scrollWidth, scrollHeight vs budget) to not overflow or crop anything.
Sends to Telegram captioned as a test, then is meant to be deleted along
with its workflow.
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

FILL_CSS = """
table.boletin-table { font-size: 13.5px; margin-bottom: 24px; }
table.boletin-table thead th { font-size: 11.5px; padding: 12px 7px 10px; }
table.boletin-table tbody td { padding: 13px 7px; }
table.boletin-table caption.caption-lg { font-size: 17px; padding: 13px 0; }
.chart-block { margin-bottom: 24px; }
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

CHECK_JS = """
() => Array.from(document.querySelectorAll('table.boletin-table')).map(t => {
  const col = t.closest('.col, .col-spread') || t.parentElement;
  return {cap: t.querySelector('caption')?.textContent?.trim(), tableW: t.scrollWidth, containerW: col.clientWidth};
})
"""

out_dir = "render_out"
os.makedirs(out_dir, exist_ok=True)
out_paths = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, template in [("page1", "page1.html"), ("page2", "page2.html")]:
        html_str = rd.render_html(data, template)
        tmp_html = os.path.abspath(os.path.join(out_dir, f"_fillv3_{name}.tmp.html"))
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(html_str)

        page = browser.new_page(viewport=viewport, device_scale_factor=SCALE)
        page.goto("file:///" + tmp_html.replace("\\", "/"))
        page.add_style_tag(content=FILL_CSS)
        page.wait_for_timeout(200)

        for r in page.evaluate(CHECK_JS):
            if r["tableW"] > r["containerW"]:
                raise RuntimeError(f"{name}: tabla '{r['cap']}' se desborda: {r['tableW']}px > {r['containerW']}px")

        page_w = page.evaluate("document.querySelector('.page').scrollWidth")
        if page_w > viewport["width"]:
            raise RuntimeError(f"{name} desborda horizontalmente: {page_w}px > {viewport['width']}px")

        content_h = page.evaluate(
            "document.querySelector('.col-spread')?.scrollHeight || document.querySelector('.page').scrollHeight"
        )
        if content_h > viewport["height"]:
            raise RuntimeError(f"{name} excede el alto del lienzo: {content_h}px > {viewport['height']}px (se cortaria)")
        print(f"{name}: OK (content height {content_h}/{viewport['height']})")

        page.evaluate(f"document.querySelector('.page').style.minHeight = '{viewport['height']}px'")
        page.wait_for_timeout(300)
        out_path = os.path.join(out_dir, f"{name}_fillv3.png")
        page.screenshot(path=out_path)
        page.close()
        os.remove(tmp_html)
        out_paths.append(out_path)
    browser.close()

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]
caption = f"PRUEBA -- contenido y letra reorganizados para llenar el lienzo sin espacios muertos -- {data['fecha_larga']}"
result = st.send_media_group(token, chat_id, out_paths, caption=caption)
print(result)
if not result.get("ok"):
    raise RuntimeError(f"Telegram send failed: {result}")
