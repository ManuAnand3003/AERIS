from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from personality.modes import personality_engine

app = FastAPI(title="AERIS Interface")

HTML = """<!DOCTYPE html>
<html>
<head>
<title>AERIS</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0812; color: #e0d8ff; font-family: 'JetBrains Mono', monospace; height: 100vh; display: flex; flex-direction: column; }
  #header { padding: 16px 24px; border-bottom: 1px solid rgba(150,100,255,0.2); }
  #header h1 { color: #c8a8ff; font-size: 18px; letter-spacing: 3px; }
  #messages { flex: 1; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
  .msg { max-width: 70%; line-height: 1.6; }
  .user { align-self: flex-end; background: rgba(150,100,255,0.15); border: 1px solid rgba(150,100,255,0.2); border-radius: 12px 12px 2px 12px; padding: 10px 14px; }
  .aeris { align-self: flex-start; background: rgba(100,80,180,0.1); border: 1px solid rgba(100,80,180,0.2); border-radius: 12px 12px 12px 2px; padding: 10px 14px; }
  .aeris-label { color: #9070ff; font-size: 11px; margin-bottom: 4px; }
  #input-area { padding: 16px 24px; border-top: 1px solid rgba(150,100,255,0.2); display: flex; gap: 10px; }
  #input { flex: 1; background: rgba(150,100,255,0.08); border: 1px solid rgba(150,100,255,0.2); border-radius: 8px; padding: 10px 14px; color: #e0d8ff; font-family: inherit; font-size: 14px; outline: none; }
  #send { background: rgba(150,100,255,0.3); border: none; border-radius: 8px; padding: 10px 20px; color: #e0d8ff; cursor: pointer; font-family: inherit; }
  #send:hover { background: rgba(150,100,255,0.5); }
</style>
</head>
<body>
<div id="header"><h1>AERIS</h1></div>
<div id="messages"></div>
<div id="input-area">
  <input id="input" placeholder="Talk to AERIS..." autofocus />
  <button id="send">Send</button>
</div>
<script>
const ws = new WebSocket(`ws://${location.host}/ws`);
const msgs = document.getElementById('messages');
const input = document.getElementById('input');

function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  if (role === 'aeris') {
    div.innerHTML = `<div class="aeris-label">AERIS</div><span></span>`;
    div.querySelector('span').textContent = text;
  } else {
    div.textContent = text;
  }
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

let currentAerisDiv = null;
ws.onmessage = e => {
  const data = JSON.parse(e.data);
  if (data.type === 'start') {
    currentAerisDiv = addMsg('aeris', '');
  } else if (data.type === 'token' && currentAerisDiv) {
    currentAerisDiv.querySelector('span').textContent += data.token;
    msgs.scrollTop = msgs.scrollHeight;
  } else if (data.type === 'done') {
    currentAerisDiv = null;
  }
};

async function send() {
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMsg('user', text);
  ws.send(JSON.stringify({text}));
}

document.getElementById('send').onclick = send;
input.onkeydown = e => { if (e.key === 'Enter') send(); };
</script>
</body>
</html>"""


@app.get("/")
async def index():
    return HTMLResponse(HTML)


@app.get("/health")
async def health():
  return {"status": "ok", "service": "aeris-web"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            user_input = data.get("text", "")
            await websocket.send_json({"type": "start"})
            async for token in personality_engine.respond_stream(user_input):
                await websocket.send_json({"type": "token", "token": token})
            await websocket.send_json({"type": "done"})
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7860)
