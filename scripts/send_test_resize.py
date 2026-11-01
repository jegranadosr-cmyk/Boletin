"""One-off test script (not part of the production pipeline): generates the
normal bulletin via the existing main.py/render.py, then resizes page1.png
and page2.png down to 1293px wide (pure uniform downscale, no layout/CSS
changes) and sends them to Telegram as a test, clearly captioned as such.
Meant to run once via a temporary workflow_dispatch workflow and then be
deleted along with that workflow.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")

import main as bmain  # noqa: E402
import render as rd  # noqa: E402
import send_telegram as st  # noqa: E402
from PIL import Image  # noqa: E402

data = bmain.main()
p1, p2, _pdf = rd.render_bulletin(data, "render_out")

TARGET_WIDTH = 1293
resized_paths = []
for src in (p1, p2):
    im = Image.open(src)
    w, h = im.size
    target_h = round(h * TARGET_WIDTH / w)
    resized = im.resize((TARGET_WIDTH, target_h), Image.LANCZOS)
    out_path = src.replace(".png", "_test1293.png")
    resized.save(out_path)
    resized_paths.append(out_path)
    print(f"{src}: {w}x{h} -> {out_path}: {TARGET_WIDTH}x{target_h}")

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]
caption = f"PRUEBA -- 2 columnas reescaladas a 1293px (sin cambios de layout) -- {data['fecha_larga']}"
result = st.send_media_group(token, chat_id, resized_paths, caption=caption)
print(result)
if not result.get("ok"):
    raise RuntimeError(f"Telegram send failed: {result}")
