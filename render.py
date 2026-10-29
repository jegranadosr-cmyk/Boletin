import os
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


def fmt_price(v):
    if v is None:
        return "-"
    return f"{v:,.2f}"


def fmt_big(nombre, v):
    if v is None:
        return "-"
    if nombre == "BITCOIN":
        return f"${v:,.2f}"
    return f"{v:,.2f}"


def pct_plain(v):
    if v is None:
        return "-"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def pct_span(v):
    if v is None:
        return '<span class="na">-</span>'
    cls = "up" if v >= 0 else "down"
    sign = "+" if v >= 0 else ""
    return f'<span class="pct {cls}"><span class="dot {cls}"></span>{sign}{v:.2f}%</span>'


def pct_span_compact(v):
    if v is None:
        return '<span class="na">-</span>'
    cls = "up" if v >= 0 else "down"
    sign = "+" if v >= 0 else ""
    return f'<span class="pct {cls}">{sign}{v:.2f}%</span>'


def arrow(v):
    if v is None:
        return ""
    return "▲" if v >= 0 else "▼"


def bar_chart_layout(items, key="pct_day", wrap_h=150, top_reserve=14,
                      bottom_ticker=18, bottom_reserve=14, min_bar=3):
    """Lays out a diverging (zero-centered) bar chart: positive values grow
    up from a shared zero line, negative values grow down from it, each side
    scaled independently so neither sign dwarfs the other. Returns the zero
    line's y (px from the top of each bar-wrap) plus per-item bar/label
    pixel positions, all addressed from that same top-left origin.
    """
    vals = [i.get(key) for i in items]
    pos_vals = [v for v in vals if v is not None and v >= 0]
    neg_vals = [abs(v) for v in vals if v is not None and v < 0]
    max_pos = max(pos_vals) if pos_vals else 0
    max_neg = max(neg_vals) if neg_vals else 0
    total = max_pos + max_neg

    bar_budget = wrap_h - top_reserve - bottom_ticker - bottom_reserve
    up_budget = bar_budget * (max_pos / total) if total else bar_budget / 2
    down_budget = bar_budget - up_budget
    zero_y = top_reserve + up_budget

    bars = []
    for v in vals:
        if v is None:
            bars.append({"bar_top": zero_y, "bar_h": 0, "neg": False, "val_top": zero_y - 14})
        elif v >= 0:
            bar_h = max(min_bar, (v / max_pos) * up_budget) if max_pos else min_bar
            bar_top = zero_y - bar_h
            bars.append({"bar_top": bar_top, "bar_h": bar_h, "neg": False, "val_top": bar_top - 14})
        else:
            bar_h = max(min_bar, (abs(v) / max_neg) * down_budget) if max_neg else min_bar
            bars.append({"bar_top": zero_y, "bar_h": bar_h, "neg": True, "val_top": zero_y + bar_h + 2})

    return {"zero_y": zero_y, "bars": bars}


def _env():
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    env.filters["pct_span"] = pct_span
    env.globals.update(
        fmt_price=fmt_price,
        fmt_big=fmt_big,
        pct_plain=pct_plain,
        pct_span=lambda v: _markup(pct_span(v)),
        pct_span_compact=lambda v: _markup(pct_span_compact(v)),
        arrow=arrow,
        bar_chart_layout=bar_chart_layout,
    )
    return env


def _markup(html_str):
    from markupsafe import Markup
    return Markup(html_str)


def render_html(data, template_name):
    env = _env()
    tpl = env.get_template(template_name)
    assets_uri = "file:///" + ASSETS_DIR.replace("\\", "/")
    templates_uri = "file:///" + TEMPLATES_DIR.replace("\\", "/")
    return tpl.render(
        assets=assets_uri,
        templates=templates_uri,
        time_label="11:30",
        **data,
    )


def html_to_png(html_str, out_path):
    tmp_html = os.path.abspath(out_path.replace(".png", ".tmp.html"))
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_str)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 400}, device_scale_factor=2)
        page.goto("file:///" + tmp_html.replace("\\", "/"))
        page.wait_for_timeout(400)
        page.screenshot(path=out_path, full_page=True)
        browser.close()
    os.remove(tmp_html)


def render_bulletin(data, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    page1_html = render_html(data, "page1.html")
    page2_html = render_html(data, "page2.html")
    p1_path = os.path.join(out_dir, "page1.png")
    p2_path = os.path.join(out_dir, "page2.png")
    html_to_png(page1_html, p1_path)
    html_to_png(page2_html, p2_path)
    return p1_path, p2_path
