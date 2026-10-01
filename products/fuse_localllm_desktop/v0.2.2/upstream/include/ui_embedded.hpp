#pragma once
namespace fuse_ui {
inline constexpr const char* INDEX_HTML = R"FUSEUI(<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>FUSE LocalLLM</title>
<link rel="stylesheet" href="/app.css"/>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="brandmark">F</div>
      <div><strong>FUSE</strong><span>LocalLLM</span></div>
    </div>

    <button class="new-chat" id="newChat">＋ New chat</button>

    <nav>
      <button class="nav active" data-view="chat"><span>◫</span> Chat</button>
      <button class="nav" data-view="models"><span>◈</span> Models</button>
      <button class="nav" data-view="library"><span>▱</span> Library</button>
      <button class="nav" data-view="apps"><span>⊞</span> Apps</button>
      <button class="nav" data-view="settings"><span>⚙</span> Settings</button>
    </nav>

    <div class="history-title">Recent</div>
    <div id="history" class="history"></div>

    <div class="runtime-pill">
      <i id="runtimeDot"></i>
      <div><b id="runtimeLabel">Starting runtime…</b><small id="runtimeModel">No model loaded</small></div>
    </div>
  </aside>

  <main>
    <section class="view active" id="view-chat">
      <div class="topbar">
        <div>
          <select id="modelPicker" class="model-picker"></select>
        </div>
        <button class="ghost" id="clearChat">Clear</button>
      </div>

      <div class="chat-scroll" id="chatScroll">
        <div class="empty-state" id="emptyState">
          <div class="orb">F</div>
          <h1>What do you want to build?</h1>
          <p>Private local inference on your machine. Your GGUF stays on your PC.</p>
          <div class="chips">
            <button data-prompt="Summarize the architecture of this project.">Summarize a project</button>
            <button data-prompt="Help me design a creative concept.">Creative concept</button>
            <button data-prompt="Review this idea and identify the strongest implementation path.">Review an idea</button>
          </div>
        </div>
        <div id="messages" class="messages"></div>
      </div>

      <div class="composer-wrap">
        <div id="attachmentBar" class="attachments"></div>
        <div class="composer">
          <button class="circle" id="attachBtn" title="Attach text/code file">＋</button>
          <textarea id="prompt" placeholder="Send a message" rows="1"></textarea>
          <button class="send" id="sendBtn">↑</button>
        </div>
        <div class="composer-meta">
          <span>Local · FUSE-owned runtime</span>
          <span id="perf"></span>
        </div>
      </div>
      <input type="file" id="fileInput" hidden multiple accept=".txt,.md,.json,.csv,.py,.js,.ts,.cpp,.h,.hpp,.html,.css,.xml,.yaml,.yml"/>
    </section>

    <section class="view" id="view-models">
      <div class="page">
        <div class="page-head">
          <div><h1>Models</h1><p>GGUF models detected on this PC.</p></div>
          <button id="refreshModels">Refresh</button>
        </div>
        <div id="modelCards" class="cards"></div>
        <div class="hint">
          <b>Model folder</b>
          <p>FUSE automatically scans <code>%USERPROFILE%\Downloads\Programs\FUSE</code> and <code>%LOCALAPPDATA%\FUSE\LocalLLM\models</code>.</p>
          <button id="openModelFolder">Open local model folder</button>
        </div>
      </div>
    </section>

    <section class="view" id="view-library">
      <div class="page">
        <h1>Library</h1>
        <p>Reusable local context for chats. Text/code attachments stay inside this browser profile and are sent only to the local runtime.</p>
        <div id="libraryItems" class="cards"></div>
      </div>
    </section>

    <section class="view" id="view-apps">
      <div class="page">
        <h1>Apps</h1>
        <p>Connect local tools to the same FUSE runtime without changing your model.</p>
        <div class="cards">
          <article><h3>OpenAI-compatible API</h3><p><code>http://127.0.0.1:8999/v1</code></p><span class="badge good">Ready</span></article>
          <article><h3>Ollama-compatible surface</h3><p><code>/api/chat</code>, <code>/api/generate</code>, <code>/api/tags</code>, <code>/api/version</code></p><span class="badge good">Ready</span></article>
          <article><h3>FUSE Sovereignty Plane</h3><p>SFCP local-private executor binding target.</p><span class="badge warn">Runtime proof pending</span></article>
        </div>
      </div>
    </section>

    <section class="view" id="view-settings">
      <div class="page">
        <h1>Settings</h1>
        <div class="settings-grid">
          <label>Context window<input type="number" id="ctx" min="512" max="131072" step="512"/></label>
          <label>Max output tokens<input type="number" id="maxTokens" min="16" max="8192"/></label>
          <label>Temperature<input type="number" id="temperature" min="0" max="2" step="0.05"/></label>
          <label>Top P<input type="number" id="topP" min="0.05" max="1" step="0.05"/></label>
          <label>Top K<input type="number" id="topK" min="1" max="200"/></label>
          <label class="check"><input type="checkbox" id="noThink"/> Hide model reasoning tags where supported</label>
        </div>
        <button id="saveSettings">Save settings</button>
        <div class="status-panel">
          <h3>Runtime</h3>
          <pre id="runtimeJson">Loading…</pre>
        </div>
      </div>
    </section>
  </main>
</div>
<script src="/app.js"></script>
</body>
</html>)FUSEUI";
inline constexpr const char* APP_CSS = R"FUSEUI(
:root{--bg:#fbfbfc;--panel:#f4f5f7;--line:#e8e9ed;--ink:#17191d;--muted:#737985;--accent:#101216;--soft:#eef0f3;--green:#18a36b;--warn:#b7791f}
*{box-sizing:border-box}html,body{margin:0;height:100%;font-family:Inter,ui-sans-serif,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--bg)}
button,input,textarea,select{font:inherit}.app{display:grid;grid-template-columns:240px 1fr;height:100vh;overflow:hidden}
.sidebar{background:#f7f7f8;border-right:1px solid var(--line);padding:16px 12px;display:flex;flex-direction:column;min-width:0}
.brand{display:flex;gap:10px;align-items:center;padding:4px 8px 18px}.brandmark{width:30px;height:30px;border-radius:9px;background:#111;color:#fff;display:grid;place-items:center;font-weight:800}.brand strong{display:block;font-size:14px}.brand span{display:block;color:var(--muted);font-size:11px}
.new-chat,.nav,.history button{border:0;background:transparent;border-radius:10px;text-align:left;cursor:pointer}
.new-chat{padding:10px 12px;border:1px solid var(--line);background:#fff;margin-bottom:12px;font-weight:600}.new-chat:hover{background:var(--soft)}
nav{display:grid;gap:2px}.nav{padding:9px 10px;color:#40444d}.nav span{display:inline-block;width:24px}.nav:hover,.nav.active{background:#e9eaed;color:#111}
.history-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#8d929b;padding:20px 8px 7px}.history{overflow:auto;min-height:0}.history button{display:block;width:100%;padding:8px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#50555e}.history button:hover{background:#eceef1}
.runtime-pill{margin-top:auto;border-top:1px solid var(--line);padding:14px 6px 2px;display:flex;gap:10px;align-items:center}.runtime-pill i{width:9px;height:9px;border-radius:99px;background:#aaa}.runtime-pill i.on{background:var(--green);box-shadow:0 0 0 3px #18a36b22}.runtime-pill b{display:block;font-size:11px}.runtime-pill small{display:block;color:var(--muted);max-width:185px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
main{min-width:0;height:100vh}.view{display:none;height:100%}.view.active{display:block}#view-chat.active{display:grid;grid-template-rows:58px 1fr auto}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:10px 20px;border-bottom:1px solid var(--line);background:#ffffffcc;backdrop-filter:blur(12px)}.model-picker{max-width:520px;border:0;background:transparent;font-weight:600;padding:8px}.ghost{border:0;background:transparent;padding:8px 12px;border-radius:8px;cursor:pointer}.ghost:hover{background:var(--soft)}
.chat-scroll{overflow:auto;padding:24px 0}.empty-state{max-width:720px;margin:10vh auto 0;text-align:center;padding:24px}.orb{width:54px;height:54px;border-radius:18px;margin:auto;background:#111;color:#fff;display:grid;place-items:center;font-size:24px;font-weight:800}.empty-state h1{font-size:28px;margin:18px 0 8px}.empty-state p{color:var(--muted)}.chips{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:20px}.chips button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:9px 13px;cursor:pointer}
.messages{max-width:800px;margin:auto;padding:0 24px}.msg{display:flex;margin:20px 0}.msg.user{justify-content:flex-end}.bubble{max-width:82%;padding:12px 15px;border-radius:16px;white-space:pre-wrap;line-height:1.5}.user .bubble{background:#eceef1}.assistant .bubble{background:transparent;padding-left:0}.role{font-size:11px;color:var(--muted);margin-bottom:4px}.thinking{opacity:.55;font-style:italic}
.composer-wrap{max-width:850px;width:calc(100% - 40px);margin:0 auto 18px}.composer{display:grid;grid-template-columns:auto 1fr auto;align-items:end;border:1px solid #dfe1e5;background:#fff;border-radius:22px;padding:9px;box-shadow:0 8px 28px #0000000c}.composer textarea{resize:none;max-height:180px;border:0;outline:0;padding:8px 10px;line-height:1.45;background:transparent}.circle,.send{width:36px;height:36px;border-radius:50%;border:0;cursor:pointer}.circle{background:#f1f2f4}.send{background:#111;color:#fff;font-size:20px}.composer-meta{display:flex;justify-content:space-between;color:#9a9fa8;font-size:10px;padding:5px 10px}.attachments{display:flex;gap:6px;overflow:auto}.attachment{font-size:11px;background:#eef0f3;border-radius:8px;padding:5px 8px;margin-bottom:6px}
.page{max-width:1050px;margin:auto;padding:42px 38px;height:100%;overflow:auto}.page h1{font-size:30px;margin:0 0 6px}.page>p,.page-head p{color:var(--muted);margin-top:0}.page-head{display:flex;justify-content:space-between;align-items:start}.page button{border:1px solid var(--line);background:#fff;border-radius:10px;padding:9px 12px;cursor:pointer}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:22px}.cards article{border:1px solid var(--line);background:#fff;border-radius:14px;padding:16px}.cards h3{margin:0 0 6px}.cards p{color:var(--muted);font-size:13px}.badge{display:inline-block;font-size:10px;font-weight:700;padding:4px 7px;border-radius:99px;background:#eee}.badge.good{color:#067647;background:#e9f8f1}.badge.warn{color:#8b5d0b;background:#fff5d8}.model-card.active{outline:2px solid #111}.model-meta{font-size:11px;color:var(--muted)}.hint{margin-top:24px;border:1px dashed #ccd0d7;border-radius:14px;padding:16px;background:#fafafa}.settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:24px 0}.settings-grid label{display:grid;gap:6px;font-size:12px;color:#5e636d}.settings-grid input{padding:10px;border:1px solid var(--line);border-radius:9px;background:#fff}.settings-grid .check{grid-column:1/-1;display:flex;align-items:center}.check input{margin-right:8px}.status-panel{margin-top:26px;border-top:1px solid var(--line);padding-top:20px}.status-panel pre{white-space:pre-wrap;background:#111;color:#d8e0e8;border-radius:12px;padding:14px;font-size:11px;max-height:320px;overflow:auto}
code{background:#f0f1f3;border-radius:5px;padding:2px 5px}
@media(max-width:760px){.app{grid-template-columns:64px 1fr}.brand div:not(.brandmark),.new-chat,.nav:not(.active){font-size:0}.nav span{font-size:18px}.history-title,.history,.runtime-pill div{display:none}.sidebar{padding:12px 8px}.settings-grid{grid-template-columns:1fr}}
)FUSEUI";
inline constexpr const char* APP_JS = R"FUSEUI(
const $=id=>document.getElementById(id);
const state={
  chats:JSON.parse(localStorage.getItem("fuse.chats")||"[]"),
  active:localStorage.getItem("fuse.active")||null,
  files:JSON.parse(localStorage.getItem("fuse.library")||"[]"),
  settings:Object.assign({ctx:4096,max_tokens:512,temperature:.6,top_p:.95,top_k:20,no_think:false},JSON.parse(localStorage.getItem("fuse.settings")||"{}")),
  models:[],runtime:null,busy:false
};
function save(){
  localStorage.setItem("fuse.chats",JSON.stringify(state.chats));
  localStorage.setItem("fuse.active",state.active||"");
  localStorage.setItem("fuse.library",JSON.stringify(state.files));
}
function chat(){return state.chats.find(x=>x.id===state.active)}
function newChat(){
  const c={id:crypto.randomUUID(),title:"New chat",created:Date.now(),messages:[]};state.chats.unshift(c);state.active=c.id;save();renderHistory();renderChat();show("chat");
}
function renderHistory(){
  $("history").innerHTML="";
  state.chats.slice(0,25).forEach(c=>{const b=document.createElement("button");b.textContent=c.title;b.onclick=()=>{state.active=c.id;save();renderChat();show("chat")};$("history").appendChild(b)});
}
function renderChat(){
  const c=chat();$("messages").innerHTML="";const empty=!c||!c.messages.length;$("emptyState").style.display=empty?"block":"none";
  if(!c)return;
  c.messages.forEach(m=>addMessageNode(m.role,m.content,false));
  $("chatScroll").scrollTop=$("chatScroll").scrollHeight;
}
function addMessageNode(role,content,append=true){
  const wrap=document.createElement("div");wrap.className="msg "+role;
  const b=document.createElement("div");b.className="bubble";
  if(role==="assistant"){const r=document.createElement("div");r.className="role";r.textContent="FUSE LocalLLM";b.appendChild(r)}
  const t=document.createElement("div");t.textContent=content;b.appendChild(t);wrap.appendChild(b);$("messages").appendChild(wrap);
  if(append){let c=chat();c.messages.push({role,content});if(c.messages.length===1)c.title=content.slice(0,44)||"New chat";save();renderHistory()}
  $("emptyState").style.display="none";$("chatScroll").scrollTop=$("chatScroll").scrollHeight;
  return t;
}
function show(name){
  document.querySelectorAll(".view").forEach(v=>v.classList.toggle("active",v.id==="view-"+name));
  document.querySelectorAll(".nav").forEach(v=>v.classList.toggle("active",v.dataset.view===name));
  if(name==="models")loadModels(); if(name==="settings")loadRuntime();
}
async function api(path,opts){const r=await fetch(path,opts);if(!r.ok)throw new Error(await r.text());return r.json()}
async function loadRuntime(){
  try{
    const r=await api("/v1/fuse/runtime");state.runtime=r;$("runtimeDot").className="on";$("runtimeLabel").textContent="Runtime ready";$("runtimeModel").textContent=r.model?.filename||"No model";
    $("runtimeJson").textContent=JSON.stringify(r,null,2);
  }catch(e){$("runtimeDot").className="";$("runtimeLabel").textContent="Runtime unavailable";$("runtimeModel").textContent=String(e)}
}
async function loadModels(){
  try{
    const d=await api("/v1/fuse/models/local");state.models=d.data||[];
    const p=$("modelPicker");p.innerHTML="";state.models.forEach(m=>{let o=document.createElement("option");o.value=m.path;o.textContent=m.filename+(m.active?" · loaded":"");p.appendChild(o);if(m.active)p.value=m.path});
    const cards=$("modelCards");cards.innerHTML="";
    state.models.forEach(m=>{let a=document.createElement("article");a.className="model-card"+(m.active?" active":"");a.innerHTML=`<h3>${escapeHtml(m.filename)}</h3><div class="model-meta">${formatBytes(m.bytes)}${m.active?" · Loaded":""}</div><p>${escapeHtml(m.path)}</p><button>${m.active?"Loaded":"Load model"}</button>`;
      a.querySelector("button").onclick=async()=>{if(m.active)return; a.querySelector("button").textContent="Loading…";await api("/v1/fuse/models/select",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({path:m.path})});await loadModels();await loadRuntime()};
      cards.appendChild(a);
    });
    if(!state.models.length)cards.innerHTML="<article><h3>No GGUF found</h3><p>Place a GGUF in the monitored model folder, then refresh.</p></article>";
  }catch(e){$("modelCards").innerHTML=`<article><h3>Runtime error</h3><p>${escapeHtml(String(e))}</p></article>`}
}
function contextText(){
  const c=chat();let s=(c?.messages||[]).slice(-12).map(m=>`${m.role.toUpperCase()}: ${m.content}`).join("\n\n");
  if(state.files.length)s+="\n\nATTACHED LOCAL CONTEXT:\n"+state.files.slice(-5).map(f=>`--- ${f.name} ---\n${f.content}`).join("\n");
  return s;
}
async function send(){
  if(state.busy)return;let text=$("prompt").value.trim();if(!text)return;if(!chat())newChat();
  addMessageNode("user",text,true);$("prompt").value="";state.busy=true;$("sendBtn").textContent="■";
  const node=addMessageNode("assistant","",false);node.className="thinking";node.textContent="Thinking…";
  const c=chat();const body={model:"local",stream:true,messages:[{role:"user",content:contextText()}],...state.settings};
  const t0=performance.now();let acc="";
  try{
    const r=await fetch("/v1/chat/completions",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body)});
    if(!r.ok)throw new Error(await r.text());
    const reader=r.body.getReader(),dec=new TextDecoder();node.className="";node.textContent="";
    let pending="";
    while(true){const {done,value}=await reader.read();if(done)break;pending+=dec.decode(value,{stream:true});
      const lines=pending.split("\n");pending=lines.pop();
      for(const line of lines){if(!line.startsWith("data: "))continue;const data=line.slice(6);if(data==="[DONE]")continue;try{const j=JSON.parse(data);const d=j.choices?.[0]?.delta?.content||"";acc+=d;node.textContent=acc;$("chatScroll").scrollTop=$("chatScroll").scrollHeight}catch{}}
    }
    c.messages.push({role:"assistant",content:acc});save();$("perf").textContent=`${((performance.now()-t0)/1000).toFixed(1)} s`;
  }catch(e){node.className="";node.textContent="Runtime error: "+e.message;acc=node.textContent;c.messages.push({role:"assistant",content:acc});save()}
  state.busy=false;$("sendBtn").textContent="↑";
}
function escapeHtml(x){return String(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function formatBytes(n){if(!n)return"0 B";const u=["B","KB","MB","GB"];let i=Math.min(3,Math.floor(Math.log(n)/Math.log(1024)));return(n/1024**i).toFixed(i?1:0)+" "+u[i]}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>show(b.dataset.view));
document.querySelectorAll(".chips button").forEach(b=>b.onclick=()=>{$("prompt").value=b.dataset.prompt;$("prompt").focus()});
$("newChat").onclick=newChat;$("clearChat").onclick=()=>{if(chat()){chat().messages=[];save();renderChat()}};
$("sendBtn").onclick=send;$("prompt").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}};
$("prompt").oninput=e=>{e.target.style.height="auto";e.target.style.height=Math.min(180,e.target.scrollHeight)+"px"};
$("attachBtn").onclick=()=>$("fileInput").click();
$("fileInput").onchange=async e=>{for(const f of e.target.files){if(f.size>2_000_000)continue;state.files.push({id:crypto.randomUUID(),name:f.name,content:await f.text()})}save();renderLibrary();renderAttachments()};
function renderAttachments(){$("attachmentBar").innerHTML="";state.files.slice(-4).forEach(f=>{let x=document.createElement("div");x.className="attachment";x.textContent=f.name;$("attachmentBar").appendChild(x)})}
function renderLibrary(){$("libraryItems").innerHTML="";state.files.forEach(f=>{let a=document.createElement("article");a.innerHTML=`<h3>${escapeHtml(f.name)}</h3><p>${f.content.length.toLocaleString()} characters</p><button>Remove</button>`;a.querySelector("button").onclick=()=>{state.files=state.files.filter(x=>x.id!==f.id);save();renderLibrary();renderAttachments()};$("libraryItems").appendChild(a)})}
$("refreshModels").onclick=loadModels;$("modelPicker").onchange=async e=>{if(!e.target.value)return;await api("/v1/fuse/models/select",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({path:e.target.value})});await loadRuntime();await loadModels()};
$("openModelFolder").onclick=async()=>{try{await api("/v1/fuse/models/open-folder",{method:"POST"})}catch(e){alert(e.message)}};
["ctx","maxTokens","temperature","topP","topK"].forEach(id=>$(id).value=state.settings[id==="maxTokens"?"max_tokens":id==="topP"?"top_p":id==="topK"?"top_k":id]);
$("noThink").checked=state.settings.no_think;
$("saveSettings").onclick=()=>{state.settings={ctx:+$("ctx").value,max_tokens:+$("maxTokens").value,temperature:+$("temperature").value,top_p:+$("topP").value,top_k:+$("topK").value,no_think:$("noThink").checked};localStorage.setItem("fuse.settings",JSON.stringify(state.settings));$("saveSettings").textContent="Saved";setTimeout(()=>$("saveSettings").textContent="Save settings",900)};
if(!state.chats.length)newChat();else{if(!chat())state.active=state.chats[0].id;renderHistory();renderChat()}
renderLibrary();renderAttachments();loadRuntime();loadModels();setInterval(loadRuntime,15000);
)FUSEUI";
}
