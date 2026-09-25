
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
