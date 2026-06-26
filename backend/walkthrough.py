"""Build the personalized walkthrough from the call: the user's own annotated
screenshots + clean numbered steps + (optional) TTS narration.

Illustrated HTML guide = the deliverable. MP4 (ffmpeg) is a stretch goal — do
NOT generate UI footage with a video model; the frames are the user's real screens."""
import os
import uuid
from pathlib import Path

from . import gmi

OUT = Path(__file__).parent.parent / "frontend" / "guides"
OUT.mkdir(parents=True, exist_ok=True)
PUBLIC = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")


def build(scenario: dict, transcript: list[str], shots: list[str]) -> dict:
    """shots = list of annotated screenshot URLs captured during the call.
    Returns {title, steps, html_url} and the dict to cache in Redis."""
    title = scenario.get("title", "Your fix")
    steps = gmi.summarize_steps(transcript, title)

    # Pair each step with a screenshot if we have one.
    paired = []
    for i, step in enumerate(steps):
        paired.append({"text": step, "image": shots[i] if i < len(shots) else None})

    html = _render_html(title, paired)
    fname = f"guide_{uuid.uuid4().hex[:8]}.html"
    (OUT / fname).write_text(html, encoding="utf-8")

    return {"title": title, "steps": paired, "html_url": f"{PUBLIC}/guides/{fname}"}


def _render_html(title: str, paired: list[dict]) -> str:
    rows = ""
    for i, s in enumerate(paired, 1):
        img = f'<img src="{s["image"]}" alt="step {i}"/>' if s["image"] else ""
        rows += f"""
        <li>
          <div class="step"><span class="n">{i}</span><p>{s['text']}</p></div>
          {img}
        </li>"""
    narration = " ".join(f"Step {i}. {s['text']}." for i, s in enumerate(paired, 1))
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:680px;margin:32px auto;padding:0 18px;color:#1a1a1a}}
 h1{{font-size:22px}} ol{{list-style:none;padding:0}}
 li{{margin:20px 0;border:1px solid #e6e6e6;border-radius:12px;padding:16px}}
 .step{{display:flex;gap:12px;align-items:flex-start}}
 .n{{background:#e63232;color:#fff;border-radius:50%;width:26px;height:26px;
     display:inline-flex;align-items:center;justify-content:center;font-weight:700;flex:0 0 26px}}
 .step p{{margin:0;font-size:16px;line-height:1.4}}
 img{{width:100%;border-radius:8px;margin-top:12px;border:1px solid #eee}}
 button{{font-size:15px;padding:10px 16px;border:0;border-radius:8px;background:#1a1a1a;color:#fff;cursor:pointer}}
</style></head><body>
 <h1>{title}</h1>
 <p>A guide built from your own screen. Keep it — next time you can fix this in seconds.</p>
 <button onclick="speak()">▶ Play narration</button>
 <ol>{rows}</ol>
 <script>
  function speak(){{const u=new SpeechSynthesisUtterance({narration!r});u.rate=.95;speechSynthesis.speak(u);}}
 </script>
</body></html>"""
