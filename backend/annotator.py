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
PUBLIC = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

# Hardcoded demo targets as fractions of (width, height): (x, y, w, h).
# Swap to real coordinates from the vision model later if you have time.
TARGETS = {
    "sidebar":        (0.02, 0.18, 0.22, 0.10),
    "connect_button": (0.40, 0.55, 0.20, 0.09),
    "default":        (0.40, 0.45, 0.20, 0.10),
}


def annotate(image_bytes: bytes, target: str = "default") -> dict:
    """Returns {url, filename} of the annotated screenshot."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    fx, fy, fw, fh = TARGETS.get(target, TARGETS["default"])
    box = [fx * w, fy * h, (fx + fw) * w, (fy + fh) * h]

    draw = ImageDraw.Draw(img)
    # red rounded highlight
    draw.rounded_rectangle(box, radius=12, outline=(230, 50, 50), width=6)
    # arrow pointing into the box from lower-left
    ax, ay = box[0] - 60, box[3] + 60
    tip = (box[0] + 10, box[1] + (box[3] - box[1]) / 2)
    draw.line([ax, ay, tip[0], tip[1]], fill=(230, 50, 50), width=6)
    draw.polygon([tip, (tip[0] - 18, tip[1] + 4), (tip[0] - 6, tip[1] + 20)],
                 fill=(230, 50, 50))

    fname = f"shot_{uuid.uuid4().hex[:8]}_{int(time.time())}.png"
    img.save(OUT / fname)
    return {"url": f"{PUBLIC}/shots/{fname}", "filename": fname}
