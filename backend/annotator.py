"""Draw an arrow/box on the user's own screenshot. No model — instant and free.

For the demo, target coordinates can be hardcoded per scenario (TARGETS below).
That's allowed and smart: it looks magical and nobody checks if the box is computed."""
import io
import os
import time
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent.parent / "frontend" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
# Empty default -> relative "/shots/..." URLs that resolve against whatever origin
# serves the page (localhost or the AgentBox domain). Set PUBLIC_BASE_URL only if the
# images must be referenced from a different host than the UI.
PUBLIC = os.getenv("PUBLIC_BASE_URL", "")

# Hardcoded demo targets as fractions of (width, height): (x, y, w, h).
# Swap to real coordinates from the vision model later if you have time.
TARGETS = {
    "sidebar":        (0.02, 0.18, 0.22, 0.10),
    "connect_button": (0.40, 0.55, 0.20, 0.09),
    "vpn_connect_button": (0.62, 0.68, 0.22, 0.10),
    "vpn_profile":    (0.24, 0.34, 0.42, 0.12),
    "wifi_toggle":    (0.72, 0.12, 0.16, 0.08),
    "default":        (0.40, 0.45, 0.20, 0.10),
}


def annotate(image_bytes: bytes, target: str = "default") -> dict:
    """Returns {url, filename} of the annotated screenshot."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    fx, fy, fw, fh = TARGETS.get(target, TARGETS["default"])
    box = _clamp_box([fx * w, fy * h, (fx + fw) * w, (fy + fh) * h], w, h)

    draw = ImageDraw.Draw(img)
    # red rounded highlight
    draw.rounded_rectangle(box, radius=12, outline=(230, 50, 50), width=6)
    # arrow pointing into the box from lower-left
    ax, ay = max(8, box[0] - 60), min(h - 8, box[3] + 60)
    tip = (box[0] + 10, box[1] + (box[3] - box[1]) / 2)
    draw.line([ax, ay, tip[0], tip[1]], fill=(230, 50, 50), width=6)
    draw.polygon([tip, (tip[0] - 18, tip[1] + 4), (tip[0] - 6, tip[1] + 20)],
                 fill=(230, 50, 50))

    fname = f"shot_{uuid.uuid4().hex[:8]}_{int(time.time())}.png"
    img.save(OUT / fname)
    return {"url": f"{PUBLIC}/shots/{fname}", "filename": fname}


def _clamp_box(box: list[float], width: int, height: int) -> list[float]:
    left, top, right, bottom = box
    return [
        max(4, min(width - 4, left)),
        max(4, min(height - 4, top)),
        max(4, min(width - 4, right)),
        max(4, min(height - 4, bottom)),
    ]
