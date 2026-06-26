"""FastAPI entry point. WebSocket carries the call; REST serves audio,
annotated shots, guides, and the dashboard metrics."""
import base64
import os
import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import deepgram_client, orchestrator, store

app = FastAPI(title="Tier Zero")

# serve the widget + generated shots/guides
FRONT = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/shots", StaticFiles(directory=os.path.join(FRONT, "shots")), name="shots")
app.mount("/guides", StaticFiles(directory=os.path.join(FRONT, "guides")), name="guides")


@app.get("/")
def root():
    return RedirectResponse("/login.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return store.metrics()


@app.get("/escalations")
def escalations(limit: int = 20):
    return {"items": store.list_escalations(limit=limit)}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    """Protocol (JSON messages from the widget):
       {type:'text', text:'...'}                      # typed input
       {type:'audio', audio:'<base64 wav>'}           # mic input -> STT
       {type:'image', image:'<base64 png>', text?:''} # screenshot upload
    Server replies with a JSON turn result; audio (if any) follows as bytes."""
    await websocket.accept()
    call_id = uuid.uuid4().hex
    try:
        while True:
            msg = await websocket.receive_json()
            user_text = msg.get("text", "")
            image_bytes = None

            if msg.get("type") == "audio" and msg.get("audio"):
                user_text = deepgram_client.transcribe(base64.b64decode(msg["audio"])) or user_text
            if msg.get("type") == "image" and msg.get("image"):
                image_bytes = base64.b64decode(msg["image"])

            result = orchestrator.handle_turn(call_id, user_text, image_bytes)
            audio = result.pop("_audio", None)
            result["transcribed"] = user_text
            await websocket.send_json(result)
            if audio:
                await websocket.send_bytes(audio)  # widget plays this
    except WebSocketDisconnect:
        pass


# convenience REST fallback if you don't want to wire the socket first
@app.post("/turn")
async def turn(payload: dict):
    img = base64.b64decode(payload["image"]) if payload.get("image") else None
    res = orchestrator.handle_turn(payload.get("call_id", "demo"),
                                   payload.get("text", ""), img)
    res.pop("_audio", None)
    return JSONResponse(res)


# serve the frontend UI (login/widget/dashboard). MUST be last so the API routes,
# /ws, /shots and /guides above take precedence over this catch-all mount.
app.mount("/", StaticFiles(directory=FRONT, html=True), name="ui")
