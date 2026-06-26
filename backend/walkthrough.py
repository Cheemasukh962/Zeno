"""Build a personalized walkthrough from a resolved call."""
import html as html_lib
import json
import os
import uuid
from pathlib import Path

from . import gmi

OUT = Path(__file__).parent.parent / "frontend" / "guides"
OUT.mkdir(parents=True, exist_ok=True)
PUBLIC = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")


def build(scenario: dict, transcript: list[str], shots: list[str]) -> dict:
    """Return the guide payload cached in Redis and shown to the user."""
    title = scenario.get("title", "Your fix")
    steps = gmi.summarize_steps(transcript, title)

    paired = []
    for i, step in enumerate(steps):
        paired.append({"text": step, "image": shots[i] if i < len(shots) else None})

    rendered = _render_html(title, paired)
    fname = f"guide_{uuid.uuid4().hex[:8]}.html"
    (OUT / fname).write_text(rendered, encoding="utf-8")

    return {"title": title, "steps": paired, "html_url": f"{PUBLIC}/guides/{fname}"}


def _render_html(title: str, paired: list[dict]) -> str:
    safe_title = html_lib.escape(title)
    rows = ""
    for i, step in enumerate(paired, 1):
        safe_text = html_lib.escape(str(step["text"]))
        image = ""
        if step["image"]:
            safe_image = html_lib.escape(str(step["image"]), quote=True)
            image = f'<img src="{safe_image}" alt="step {i}"/>'
        rows += f"""
        <li>
          <div class="step"><span class="n">{i}</span><p>{safe_text}</p></div>
          {image}
        </li>"""

    narration = " ".join(f"Step {i}. {step['text']}." for i, step in enumerate(paired, 1))
    narration_json = json.dumps(narration)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{safe_title}</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:680px;margin:32px auto;padding:0 18px;color:#1a1a1a}}
 h1{{font-size:22px}} ol{{list-style:none;padding:0}}
 li{{margin:20px 0;border:1px solid #e6e6e6;border-radius:8px;padding:16px}}
 .step{{display:flex;gap:12px;align-items:flex-start}}
 .n{{background:#e63232;color:#fff;border-radius:50%;width:26px;height:26px;
     display:inline-flex;align-items:center;justify-content:center;font-weight:700;flex:0 0 26px}}
 .step p{{margin:0;font-size:16px;line-height:1.4}}
 img{{width:100%;border-radius:8px;margin-top:12px;border:1px solid #eee}}
 button{{font-size:15px;padding:10px 16px;border:0;border-radius:8px;background:#1a1a1a;color:#fff;cursor:pointer}}
</style></head><body>
 <h1>{safe_title}</h1>
 <p>A guide built from your own screen. Keep it for the next time this happens.</p>
 <button onclick="speak()">Play narration</button>
 <ol>{rows}</ol>
 <script>
  function speak(){{const u=new SpeechSynthesisUtterance({narration_json});u.rate=.95;speechSynthesis.speak(u);}}
 </script>
</body></html>"""
