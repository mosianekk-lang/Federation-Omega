from __future__ import annotations

import html
import json


def render_live_thread_root() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Mosiane Live Thread</title>
  <style>
    body{font-family:system-ui,sans-serif;margin:0;background:#f5f5f2;color:#171717;display:grid;place-items:center;min-height:100vh}
    main{max-width:680px;background:white;border:1px solid #ddd;border-radius:18px;padding:32px;box-shadow:0 12px 35px rgba(0,0,0,.07)}
    h1{margin-top:0} p{line-height:1.55}.muted{color:#666}
  </style>
</head>
<body>
<main>
  <h1>Mosiane Live Thread</h1>
  <p>This service provides one continuously refreshed, canonical conversation stream.</p>
  <p class="muted">Open a complete private room link to enter. Room links are intentionally unlisted.</p>
</main>
</body>
</html>"""


def render_live_thread_page(*, room_id: str, suggested_name: str) -> str:
    safe_room = html.escape(room_id)
    room_json = json.dumps(room_id)
    name_json = json.dumps(suggested_name)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="referrer" content="no-referrer">
  <title>Live Shared Thread</title>
  <style>
    :root{{--bg:#f4f4f1;--panel:#fff;--ink:#171717;--muted:#6b6b6b;--line:#deded8;--good:#176b3a;--bad:#9d2d2d;--bubble:#f0f0eb;--assistant:#eef3ff}}
    *{{box-sizing:border-box}}
    body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}}
    .shell{{width:min(920px,100%);margin:0 auto;min-height:100vh;display:grid;grid-template-rows:auto 1fr auto}}
    header{{position:sticky;top:0;z-index:2;background:rgba(255,255,255,.95);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:16px 20px}}
    h1{{font-size:1.05rem;margin:0 0 6px}} .sub{{font-size:.83rem;color:var(--muted);display:flex;gap:12px;flex-wrap:wrap}}
    #integrity.good{{color:var(--good)}} #integrity.bad{{color:var(--bad)}}
    main{{padding:20px;overflow:auto}}
    #messages{{display:flex;flex-direction:column;gap:12px}}
    .message{{background:var(--bubble);border:1px solid var(--line);border-radius:16px;padding:13px 15px;max-width:86%;align-self:flex-start}}
    .message.assistant{{background:var(--assistant);align-self:stretch;max-width:100%}}
    .message.mine{{align-self:flex-end}}
    .meta{{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin-bottom:7px;font-size:.78rem;color:var(--muted)}}
    .sender{{font-weight:700;color:var(--ink)}} .content{{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.48}}
    .hash{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.69rem}}
    .draft{{opacity:.88}} .draft .cursor{{display:inline-block;width:.55em;border-right:2px solid;animation:blink .8s steps(1) infinite}}
    @keyframes blink{{50%{{opacity:0}}}}
    footer{{position:sticky;bottom:0;background:rgba(255,255,255,.97);backdrop-filter:blur(10px);border-top:1px solid var(--line);padding:14px}}
    form{{display:grid;grid-template-columns:160px 1fr auto;gap:9px;align-items:end}}
    input,textarea,button{{font:inherit}}
    input,textarea{{width:100%;border:1px solid #c9c9c2;border-radius:12px;padding:11px;background:white}}
    textarea{{min-height:48px;max-height:160px;resize:vertical}}
    button{{border:0;border-radius:12px;padding:12px 16px;background:#171717;color:white;font-weight:700;cursor:pointer}}
    button:disabled{{opacity:.5;cursor:not-allowed}}
    .controls{{display:flex;justify-content:space-between;align-items:center;margin-top:8px;font-size:.78rem;color:var(--muted)}}
    label{{display:flex;gap:6px;align-items:center}}
    .notice{{display:none;padding:10px 12px;margin-bottom:12px;border-radius:12px;background:#fff4d6;border:1px solid #ead18c}}
    @media(max-width:680px){{form{{grid-template-columns:1fr auto}}#name{{grid-column:1/-1}}main{{padding:14px}}.message{{max-width:94%}}}}
  </style>
</head>
<body>
<div class="shell">
  <header>
    <h1>Live Shared Thread</h1>
    <div class="sub">
      <span>Room <strong>{safe_room[:12]}…</strong></span>
      <span id="integrity">Checking integrity…</span>
      <span>No read or presence tracking</span>
    </div>
  </header>
  <main>
    <div id="notice" class="notice"></div>
    <div id="messages" aria-live="polite"></div>
  </main>
  <footer>
    <form id="composer">
      <input id="name" maxlength="80" placeholder="Your name" autocomplete="name" required>
      <textarea id="content" maxlength="12000" placeholder="Write a message…" required></textarea>
      <button id="send" type="submit">Send</button>
    </form>
    <div class="controls">
      <label><input id="request-ai" type="checkbox" checked> Ask Shared AI to answer</label>
      <span>All viewers receive the same canonical message IDs and hashes.</span>
    </div>
  </footer>
</div>
<script>
const ROOM_ID = {room_json};
const SUGGESTED_NAME = {name_json};
const state = {{lastSeq:0,rendered:new Set(),delay:900,stopped:false}};
const elMessages=document.getElementById('messages');
const elIntegrity=document.getElementById('integrity');
const elNotice=document.getElementById('notice');
const elName=document.getElementById('name');
const elContent=document.getElementById('content');
const elSend=document.getElementById('send');
const elRequestAI=document.getElementById('request-ai');
elName.value=SUGGESTED_NAME||localStorage.getItem('live-thread-name')||'';
function showNotice(text){{elNotice.textContent=text;elNotice.style.display=text?'block':'none';}}
function formatTime(iso){{try{{return new Date(iso).toLocaleString();}}catch{{return iso;}}}}
function renderMessage(message){{
  if(state.rendered.has(message.message_id))return;
  state.rendered.add(message.message_id);
  const card=document.createElement('article');
  card.className='message '+(message.role==='assistant'?'assistant':'');
  if(message.sender===elName.value.trim())card.classList.add('mine');
  const meta=document.createElement('div');meta.className='meta';
  const sender=document.createElement('span');sender.className='sender';sender.textContent=message.sender;
  const seq=document.createElement('span');seq.textContent='#'+message.seq;
  const time=document.createElement('span');time.textContent=formatTime(message.created_at);
  const hash=document.createElement('span');hash.className='hash';hash.textContent='hash '+message.content_hash.slice(0,12);
  meta.append(sender,seq,time,hash);
  const content=document.createElement('div');content.className='content';content.textContent=message.content;
  card.append(meta,content);elMessages.append(card);state.lastSeq=Math.max(state.lastSeq,message.seq);
}}
function renderDraft(draft){{
  let card=document.getElementById('assistant-draft');
  if(!draft){{if(card)card.remove();return;}}
  if(!card){{card=document.createElement('article');card.id='assistant-draft';card.className='message assistant draft';card.innerHTML='<div class="meta"><span class="sender">Shared AI</span><span id="draft-state"></span></div><div class="content" id="draft-content"></div>';elMessages.append(card);}}
  document.getElementById('draft-state').textContent=draft.state==='failed'?'generation failed':'generating';
  const content=document.getElementById('draft-content');content.textContent=draft.content||'Thinking…';
  if(draft.state==='generating'){{const cursor=document.createElement('span');cursor.className='cursor';content.append(cursor);}}
}}
async function poll(){{
  while(!state.stopped){{
    try{{
      const response=await fetch(`/live/api/rooms/${{encodeURIComponent(ROOM_ID)}}/messages?after=${{state.lastSeq}}`,{{cache:'no-store',headers:{{'Accept':'application/json'}}}});
      if(!response.ok)throw new Error('poll_failed');
      const data=await response.json();for(const message of data.messages)renderMessage(message);renderDraft(data.draft);
      elIntegrity.textContent=data.chain_valid?'Integrity verified':'Integrity mismatch';elIntegrity.className=data.chain_valid?'good':'bad';
      showNotice('');state.delay=data.poll_after_ms||900;window.scrollTo({{top:document.body.scrollHeight,behavior:'smooth'}});
    }}catch(error){{elIntegrity.textContent='Reconnecting…';elIntegrity.className='';showNotice('Connection interrupted. Automatic reconnection is active.');state.delay=Math.min(Math.max(state.delay*1.6,1200),5000);}}
    await new Promise(resolve=>setTimeout(resolve,state.delay));
  }}
}}
document.getElementById('composer').addEventListener('submit',async(event)=>{{
  event.preventDefault();const sender=elName.value.trim();const content=elContent.value.trim();if(!sender||!content)return;
  localStorage.setItem('live-thread-name',sender);elSend.disabled=true;
  try{{
    const response=await fetch(`/live/api/rooms/${{encodeURIComponent(ROOM_ID)}}/messages`,{{method:'POST',headers:{{'Content-Type':'application/json','Accept':'application/json'}},body:JSON.stringify({{sender,content,request_ai:elRequestAI.checked}})}});
    if(!response.ok)throw new Error(await response.text());const message=await response.json();renderMessage(message);elContent.value='';showNotice('');
  }}catch(error){{showNotice('Message was not sent. It remains in this browser only; please retry.');}}finally{{elSend.disabled=false;elContent.focus();}}
}});
window.addEventListener('beforeunload',()=>{{state.stopped=true;}});poll();
</script>
</body>
</html>"""
