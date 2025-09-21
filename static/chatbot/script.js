// script.js - handles login, analyze, suggestions, charts, history

// ----- Local fallback storage -----
const LOCAL_HISTORY_KEY = "mhs_local_history_v1";
function saveLocalHistory(items){ try{ localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(items)); }catch(e){} }
function loadLocalHistory(){ try{ return JSON.parse(localStorage.getItem(LOCAL_HISTORY_KEY) || "[]"); }catch(e){ return []; } }

// ----- UI refs -----
const analyzeBtn = document.getElementById("analyzeBtn");
const userInput = document.getElementById("userInput");
const resultEl = document.getElementById("result");
const suggestionEl = document.getElementById("suggestion-text");
const historyEl = document.getElementById("history");
const clearHistoryBtn = document.getElementById("clearHistory");
const exportHistoryBtn = document.getElementById("exportHistory");
const openChatBtn = document.getElementById("openChatBtn");

// Charts
let doughnutChart = null;
let lineChart = null;

// On load
document.addEventListener("DOMContentLoaded", function(){
  // Login form
  const loginForm = document.getElementById("loginForm");
  if(loginForm){
    loginForm.addEventListener("submit", async function(e){
      e.preventDefault();
      const username = document.getElementById("username").value.trim();
      const password = document.getElementById("password").value;
      if(!username || !password){ alert("Enter username and password"); return; }
      try{
        const res = await fetch("/api/login", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if(res.ok && data.ok){
          localStorage.setItem("user_id", String(data.user_id));
          localStorage.setItem("user_name", username);
          window.location.href = "dashboard.html";
        } else alert(data.message || "Login failed");
      }catch(err){ console.error(err); alert("Login request failed."); }
    });
  }

  if(analyzeBtn) analyzeBtn.addEventListener("click", analyzeText);
  if(openChatBtn) openChatBtn.addEventListener("click", () => window.location.href="/api/analyze-sentimentbot/index.html");

  if(clearHistoryBtn) clearHistoryBtn.addEventListener("click", ()=>{
    if(confirm("Clear local history?")){ saveLocalHistory([]); renderHistory([]); updateCharts([]); }
  });

  if(exportHistoryBtn){
    exportHistoryBtn.addEventListener("click", ()=>{
      const items = loadLocalHistory();
      const blob = new Blob([JSON.stringify(items,null,2)], {type:"application/json"});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href=url; a.download="mhs_history.json"; a.click();
      URL.revokeObjectURL(url);
    });
  }

  initHistoryAndCharts();
});

// -------- analyzeText ----------
async function analyzeText(){
  const text = (userInput && userInput.value) ? userInput.value.trim() : "";
  if(!text){ alert("Please write something to analyze."); return; }

  let replyData=null;
  try{
    const res = await fetch("/api/api/analyze-sentiment", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ text })
    });
    replyData = await res.json();
  }catch(err){ console.error("Server error", err); }

  // Normalize
  const label = replyData?.label || "neutral";
  const score = (typeof replyData?.score === "number") ? replyData.score : 0.0;
  const replyText = replyData?.reply || replyData?.message || "Thanks for sharing.";
  const suggestion = replyData?.suggestion || getSuggestion(text, score);

  // Update UI
  if(resultEl) {
    resultEl.innerHTML = `
      <div><strong>Reply:</strong> ${escapeHtml(replyText)}</div>
      <div style="font-size:13px; color:#555;">
        Sentiment: <strong>${label}</strong>, Score: ${score.toFixed(2)}
      </div>
    `;
  }

  if(suggestionEl) {
    const levelClass = getSuggestionLevel(score);
    suggestionEl.innerHTML = `
      <div class="suggestion-box ${levelClass}">
        💡 ${escapeHtml(suggestion)}
      </div>
    `;
  }

  // Save history
  const item = { text, reply:replyText, label, score, suggestion, timestamp:new Date().toISOString() };
  const current = loadLocalHistory();
  current.unshift(item);
  saveLocalHistory(current);

  renderHistory(current);
  updateCharts(current);

  if(userInput) userInput.value="";
}

// ---- Suggestions based on score ----
function getSuggestion(text, score){
  if(score <= -0.5){
    return "Your input indicates high stress. Try deep breathing for a few minutes and consider sharing your thoughts with someone you trust.";
  } 
  else if(score > -0.5 && score <= -0.2){
    return "Your input shows moderate stress. A short walk or writing down your feelings may help calm your mind.";
  } 
  else if(score > -0.2 && score <= 0.2){
    return "Your input suggests low stress. You could try a quick relaxation exercise, like stretching or listening to music.";
  } 
  else {
    return "Your input reflects no stress. Keep maintaining your positive habits and continue doing what makes you feel good.";
  }
}

// ---- Stress level CSS class ----
function getSuggestionLevel(score){
  if(score <= -0.5) return "high-stress";
  if(score > -0.5 && score <= -0.2) return "moderate-stress";
  if(score > -0.2 && score <= 0.2) return "low-stress";
  return "no-stress";
}

// ---- History load ----
async function initHistoryAndCharts(){
  let merged = loadLocalHistory();
  try{
    const res = await fetch("/api/history");
    if(res.ok){
      const server = await res.json();
      if(Array.isArray(server) && server.length){
        merged = server.map(x=>({
          text:x.text||x.input||"",
          reply:x.reply||"",
          label:x.label||"neutral",
          score:typeof x.score==="number"?x.score:0,
          suggestion:x.suggestion||"",
          timestamp:x.timestamp||(new Date()).toISOString()
        }));
      }
    }
  }catch(e){}
  saveLocalHistory(merged);
  renderHistory(merged);
  updateCharts(merged);
}

// ---- Render history ----
function renderHistory(items){
  historyEl.innerHTML="";
  if(!items||!items.length){ historyEl.textContent="No history yet."; return; }
  items.slice(0,200).forEach(it=>{
    const li=document.createElement("li");
    const t=(it.timestamp)?(new Date(it.timestamp)).toLocaleString():"";
    li.innerHTML=`<div style="font-size:13px;color:#666">${t} • <strong>${escapeHtml(it.label)}</strong></div>
                  <div style="margin-top:6px">${escapeHtml(it.text)}</div>
                  <div style="margin-top:6px;color:#555;font-size:13px">Reply: ${escapeHtml(it.reply||'')}</div>
                  <div style="margin-top:4px"><span class="suggestion-box ${getSuggestionLevel(it.score)}">💡 ${escapeHtml(it.suggestion||'')}</span></div>`;
    historyEl.appendChild(li);
  });
}

// ---- Charts ----
function updateCharts(items){
  const counts={positive:0,neutral:0,negative:0};
  (items||[]).forEach(it=>{ counts[it.label]!==undefined?counts[it.label]++:counts.neutral++; });

  // Doughnut
  const dCtx=document.getElementById("moodDoughnut").getContext("2d");
  if(!doughnutChart){
    doughnutChart=new Chart(dCtx,{
      type:"doughnut",
      data:{labels:["Positive","Neutral","Negative"],
        datasets:[{data:[counts.positive,counts.neutral,counts.negative],
        backgroundColor:["#43e97b","#ffa000","#e53935"]}]},
      options:{responsive:true,maintainAspectRatio:false}
    });
  }else{
    doughnutChart.data.datasets[0].data=[counts.positive,counts.neutral,counts.negative];
    doughnutChart.update();
  }

  // Line (7 days)
  const last7=[]; for(let i=6;i>=0;i--){ const d=new Date(); d.setDate(d.getDate()-i); last7.push(d); }
  const labels=last7.map(d=>d.toLocaleDateString()); const dayCounts=new Array(7).fill(0);
  (items||[]).forEach(it=>{
    const d=new Date(it.timestamp); const idx=labels.indexOf(d.toLocaleDateString());
    if(idx>=0) dayCounts[idx]++;
  });

  const lCtx=document.getElementById("moodLine").getContext("2d");
  if(!lineChart){
    lineChart=new Chart(lCtx,{
      type:"line",
      data:{labels,datasets:[{label:'Entries',data:dayCounts,borderColor:'#3a609c',
              backgroundColor:'rgba(58,96,156,0.08)',tension:0.25,fill:true}]},
      options:{responsive:true,maintainAspectRatio:false}
    });
  }else{
    lineChart.data.labels=labels; lineChart.data.datasets[0].data=dayCounts; lineChart.update();
  }
}

// ---- util ----
function escapeHtml(s){ if(!s) return ""; return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;"); }
