const state={reports:[],record:null,originalDigest:null,observedDigest:null,tampered:false,scenario:"passing",metrics:null,fixtureSource:"files",revision:0};
const $=id=>document.getElementById(id);
let passingReports=[];let adversarialReports=[];
const embeddedPassing=[{name:"context-integrity",schema:"context-integrity/v1",ok:true,summary:"scope and freshness admission passed",details:["citation bound","unknowns explicit"]},{name:"agent-proof",schema:"agent-proof/interop/v1",ok:true,summary:"observed evidence sealed",details:["source bytes bound","unknowns explicit"]},{name:"atlas-receipt",schema:"atlas-receipt/v1",ok:true,summary:"approval-gated lifecycle replayed",details:["restart-safe receipt","approval boundary observed"]}];
const embeddedAdversarial=[{name:"mcp-doctor-drift",schema:"mcp-doctor/v1",ok:false,summary:"baseline drift refused",details:["MCP010","description changed"]},{name:"agent-trace",schema:"agent-trace/inspect/v1",ok:false,summary:"raw detail refused",details:["redaction boundary","unknowns explicit"]}];

async function digest(value){const bytes=new TextEncoder().encode(JSON.stringify(value));const hash=await crypto.subtle.digest("SHA-256",bytes);return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,"0")).join("")}
async function loadReports(scenario){
  const revision=++state.revision;
  state.reports=[];state.record=null;state.originalDigest=null;state.observedDigest=null;state.tampered=false;state.scenario=scenario;renderReports();renderRecord();
  if(!passingReports.length||!adversarialReports.length){
    try{
      const responses=await Promise.all([fetch("fixtures/specialists.json"),fetch("fixtures/adversarial.json")]);
      if(responses.some(response=>!response.ok))throw new Error("workbench fixture could not be loaded");
      const [fixture,adversarial]=await Promise.all(responses.map(response=>response.json()));
      if(fixture.schema!=="forgeyard-workbench-fixture/v1"||!Array.isArray(fixture.reports))throw new Error("invalid workbench fixture");
      if(adversarial.schema!=="forgeyard-workbench-adversarial/v1"||!Array.isArray(adversarial.reports))throw new Error("invalid adversarial fixture");
      if(revision!==state.revision)return;
      passingReports=fixture.reports;adversarialReports=adversarial.reports;state.fixtureSource="files";
    }catch(error){
      if(revision!==state.revision)return;
      passingReports=embeddedPassing.map(report=>({...report,details:[...report.details]}));adversarialReports=embeddedAdversarial.map(report=>({...report,details:[...report.details]}));state.fixtureSource="embedded";
    }
  }
  const reports=scenario==="passing"?passingReports:scenario==="adversarial"?adversarialReports:[...passingReports,{name:"mcp-doctor-drift",schema:"mcp-doctor/v1",ok:false,summary:"baseline drift refused",details:["MCP010","description changed"]}];
  if(revision!==state.revision)return;
  state.reports=reports.map(r=>({...r,details:[...r.details]}));renderReports();renderRecord()
}
async function loadMetrics(){
  const response=await fetch("fixtures/metrics.json");
  if(!response.ok)throw new Error("workbench metrics could not be loaded");
  const metrics=await response.json();
  if(metrics.schema!=="forgeyard-workbench-metrics/v1"||!Array.isArray(metrics.metrics))throw new Error("invalid workbench metrics");
  state.metrics=metrics;renderMetrics();
}
function renderMetrics(){
  const metrics=state.metrics;
  $("metrics-badge").textContent=metrics?"SNAPSHOT":"UNKNOWN";
  $("metrics-badge").className=`badge ${metrics?"":"bad"}`;
  if(!metrics){
    $("metrics-list").innerHTML='<div class="empty">No current receipt is available.</div>';
    $("metrics-meta").textContent="Unknown stays unknown until the benchmark is rerun.";
    return;
  }
  $("metrics-list").innerHTML=metrics.metrics.map(metric=>`<article class="metric-card" data-direction="${metric.direction}"><div class="metric-top"><span class="metric-label">${metric.label}</span><span class="metric-direction">${metric.direction==="lower"?"LOWER IS BETTER":"CEILING"}</span></div><div class="metric-values"><div><small>BASELINE</small><strong>${metric.value}<em>${metric.unit}</em></strong></div><span class="metric-arrow">→</span><div><small>3× TARGET</small><strong>${metric.target}<em>${metric.unit}</em></strong></div></div><p>${metric.note}</p></article>`).join("");
  $("metrics-meta").textContent=`Measured ${metrics.measured_at} · ${metrics.protocol} · ${metrics.environment} · n=${metrics.sample_count} · ${metrics.guardrail} · receipt ${metrics.receipt}`;
}
function renderGuide(){
 let guide={progress:"0 / 3",hint:"Choose a scenario to inspect its bounded signals."};
 if(state.tampered)guide={progress:"3 / 3",hint:"SHA-256 refused the changed request. Compare the two digests below, then reset."};
 else if(state.record)guide={progress:"2 / 3",hint:"The receipt is sealed. Change its request to test whether the digest holds."};
 else if(state.reports.length)guide={progress:"1 / 3",hint:"Signals loaded. Compose the record to seal a ready or blocked decision."};
 if(state.fixtureSource==="embedded"&&state.reports.length)guide.hint+=" Embedded fallback fixture is active.";
 $("guide-progress").textContent=guide.progress;$("guide-hint").textContent=guide.hint;
 $("copy-route").disabled=!state.reports.length;
 ["load-demo","load-failure","load-adversarial"].forEach((id,index)=>$(id).setAttribute("aria-pressed",String(state.reports.length>0&&state.scenario===["passing","failing","adversarial"][index])));
}
function renderReports(){
 $("reports").innerHTML=state.reports.length?state.reports.map((r,index)=>`<article class="report ${r.ok?"":"fail"}"><div class="report-top"><span class="report-name"><span class="report-index">${String(index+1).padStart(2,"0")}</span>${r.name}</span><span class="report-result ${r.ok?"":"fail"}">${r.ok?"PASS":"FAIL"}</span></div><div class="report-schema"><span class="schema-pill">${r.schema}</span> ${r.summary}</div><div class="report-schema report-details">${r.details.join(" · ")}</div></article>`).join(""):'<div class="empty">Load a synthetic case to inspect the specialist signals.</div>';
 $("specialist-count").textContent=state.reports.length;
 const label=state.scenario==="passing"?"Passing":state.scenario==="adversarial"?"Adversarial":"Failing";
 $("specialist-state").textContent=state.reports.length?`${label} synthetic scenario loaded`:"Waiting for fixtures";
 $("input-badge").textContent=state.reports.length?(state.scenario==="passing"?"PASSING":"REFUSAL"):"EMPTY";
 $("input-badge").className=`badge ${state.scenario==="passing"&&state.reports.length?"ok":state.reports.length?"bad":""}`;
 $("compose").disabled=!state.reports.length;
 renderGuide();
}
async function compose(){
 if(!state.reports.length||state.tampered)return;
 const revision=++state.revision;
 const record={schema:"forgeyard-compose/v1",task_id:`workbench-${state.scenario}`,repository:"synthetic-fixture",request:"review specialist reports",status:state.reports.every(r=>r.ok)?"ready_for_review":"blocked",evidence:state.reports.map(r=>({name:r.name,status:r.ok?"pass":"fail",detail:`schema=${r.schema}; ok=${r.ok}`,revision:"workbench-demo"})),boundary:"integrity is separate from outcome"};
 const sealed=await digest(record);
 if(revision!==state.revision)return;
 state.originalDigest=sealed;state.observedDigest=sealed;state.record=record;state.tampered=false;renderRecord();
}
function renderRecord(){
 const r=state.record;
 $("record").textContent=r?JSON.stringify({...r,sha256:state.originalDigest},null,2):"Load a scenario to create a bounded record.";
 $("decision").textContent=state.tampered?"REFUSED":r?(r.status==="ready_for_review"?"READY":"BLOCKED"):"—";
 $("decision-detail").textContent=state.tampered?"Changed receipt requires a new review":r?(r.status==="ready_for_review"?"All supplied evidence passed":"A specialist report failed closed"):"No record composed";
 $("integrity").textContent=state.tampered?"REFUSED":r?"SEALED":"—";
 $("integrity-detail").textContent=state.tampered?"Record bytes changed after sealing":r?`sha256 ${state.originalDigest.slice(0,16)}…`:"No digest calculated";
 $("record-badge").textContent=state.tampered?"REFUSED":r?(r.status==="ready_for_review"?"REVIEWABLE":"BLOCKED"):"NOT READY";
 $("record-badge").className=`badge ${r?(!state.tampered&&r.status==="ready_for_review"?"ok":"bad"):""}`;
 $("digest-comparison").hidden=!r;
 $("sealed-digest").textContent=r?state.originalDigest:"";
 $("observed-digest").textContent=r?state.observedDigest:"";
 $("observed-digest").className=state.tampered?"digest-mismatch":"";
 $("record-foot-text").textContent=state.tampered?"Refused receipt: changed payload does not match the sealed digest. Reset to review again.":r?"SHA-256 covers the compact JSON payload, excluding its sha256 field.":"No record has been sealed yet.";
 $("record-foot-mark").style.background=state.tampered?"var(--red)":r?"var(--cyan)":"var(--muted)";
 $("specialist-count").closest(".status-card").dataset.tone=state.reports.length?(state.reports.every(report=>report.ok)?"ok":"bad"):"neutral";
 $("decision").closest(".status-card").dataset.tone=r?(!state.tampered&&r.status==="ready_for_review"?"ok":"bad"):"neutral";
 $("integrity").closest(".status-card").dataset.tone=r?(state.tampered?"bad":"ok"):"neutral";
 $("compose").disabled=!state.reports.length||state.tampered;
 $("tamper").disabled=!r||state.tampered;$("export").disabled=!r;
 $("export").textContent=state.tampered?"Export refused JSON":"Export JSON";
 $("copy-receipt").textContent=state.tampered?"Copy refused receipt":"Copy receipt";
 renderReceipt();
 renderGuide();
 renderLab();
}
function renderReceipt(){
 const chips=$("receipt-chips");
 if(!chips)return;
 const r=state.record;
 if(!r){chips.innerHTML='<span class="receipt-chip">NO RECEIPT</span>';$('copy-receipt').disabled=true;$("copy-status").textContent="";return;}
 const decision=state.tampered?"REFUSED":r.status==="ready_for_review"?"READY":"BLOCKED";
 const decisionTone=decision==="READY"?"ok":"bad";
 const integrity=state.tampered?"DIGEST MISMATCH":"SEALED";
 chips.innerHTML=`<span class="receipt-chip ${decisionTone}">${decision}</span><span class="receipt-chip">${r.evidence.length} SIGNALS</span><span class="receipt-chip">${integrity}</span><span class="receipt-chip">${r.schema}</span>`;
 $("copy-receipt").disabled=false;
}
function receiptText(){return JSON.stringify({...state.record,sha256:state.originalDigest},null,2)+"\n"}
async function copyReceipt(){
 if(!state.record)return;
 let copied=false;
 try{await navigator.clipboard.writeText(receiptText());copied=true}catch{}
 if(!copied){
  const area=document.createElement("textarea");area.value=receiptText();area.setAttribute("readonly","");area.style.position="fixed";area.style.opacity="0";document.body.appendChild(area);area.select();try{copied=document.execCommand("copy")}catch{}area.remove();
 }
 $("copy-status").textContent=copied?"COPIED":"COPY UNAVAILABLE";
 window.setTimeout(()=>$("copy-status").textContent="",2200);
}
function routeUrl(){
 const url=new URL(window.location.href);url.searchParams.set("scenario",state.scenario||"passing");
 if(state.record)url.searchParams.set("compose","1");else url.searchParams.delete("compose");
 if(state.tampered)url.searchParams.set("tamper","1");else url.searchParams.delete("tamper");
 return url.toString();
}
async function copyRoute(){
 const value=routeUrl();let copied=false;
 try{await navigator.clipboard.writeText(value);copied=true}catch{}
 if(!copied){
  const area=document.createElement("textarea");area.value=value;area.setAttribute("readonly","");area.style.position="fixed";area.style.opacity="0";document.body.appendChild(area);area.select();try{copied=document.execCommand("copy")}catch{}area.remove();
 }
 $("route-status").textContent=copied?"COPIED":"COPY UNAVAILABLE";window.setTimeout(()=>$("route-status").textContent="",2200);
}
async function bootFromLocation(){
 const scenario=new URLSearchParams(window.location.search).get("scenario");
 if(!["passing","failing","adversarial"].includes(scenario))return;
 const loading=loadReports(scenario);
 let revision=state.revision;
 await loading;
 if(revision!==state.revision)return;
 const params=new URLSearchParams(window.location.search);
 if(params.get("compose")==="1"||params.get("tamper")==="1"){
  const composing=compose();revision=state.revision;await composing;
  if(revision!==state.revision)return;
 }
 if(params.get("tamper")==="1")await tamperRecord();
}
function renderLab(){
 const card=$("lab-card");
 if(!card)return;
 let stateName="standby";let stateLabel="STANDBY";let core="0";let headline="Waiting for a synthetic scenario";let caption="Load a case to wake the evidence field.";
 if(state.tampered){
  stateName="refused";stateLabel="BYTE REFUSAL";core="!";headline="The seal caught a changed byte";caption="The displayed request no longer matches its original digest.";
 }else if(state.record){
  const ready=state.record.status==="ready_for_review";
  stateName=ready?"ready":"blocked";stateLabel=ready?"READY TO REVIEW":"FAIL CLOSED";core=String(state.reports.length);headline=ready?"Every supplied signal cleared":"A specialist signal stopped the record";caption=ready?"Reviewable evidence is sealed; outcome and integrity stay separate.":"The record stays blocked until the failed signal is resolved.";
 }else if(state.reports.length){
  const passing=state.scenario==="passing";
  stateName="armed";stateLabel=passing?"SIGNAL LOCK":"FAULT PATH";core=String(state.reports.length);headline=passing?"The evidence field is armed":"A refusal path is waiting";caption=passing?"Compose to seal the passing synthetic record.":"Compose to see the boundary hold under a failing fixture.";
 }
 card.dataset.state=stateName;
 $("lab-state").textContent=stateLabel;$("lab-core").textContent=core;$("lab-readout").textContent=headline;$("lab-caption").textContent=caption;
}
function exportRecord(){if(!state.record)return;const blob=new Blob([receiptText()],{type:"application/json"});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download=`${state.record.task_id}${state.tampered?"-refused":""}.json`;link.click();URL.revokeObjectURL(link.href)}
async function tamperRecord(){
 if(!state.record)return;
 const revision=++state.revision;
 const changed={...state.record,request:"tampered request"};
 const observed=await digest(changed);
 if(revision!==state.revision)return;
 state.record=changed;state.observedDigest=observed;state.tampered=observed!==state.originalDigest;renderRecord();
}
$("load-demo").addEventListener("click",()=>loadReports("passing").catch(error=>alert(error.message)));
$("load-failure").addEventListener("click",()=>loadReports("failing").catch(error=>alert(error.message)));
$("load-adversarial").addEventListener("click",()=>loadReports("adversarial").catch(error=>alert(error.message)));
$("compose").addEventListener("click",compose);$("export").addEventListener("click",exportRecord);$("copy-receipt").addEventListener("click",copyReceipt);
$("tamper").addEventListener("click",tamperRecord);
$("copy-route").addEventListener("click",copyRoute);
$("reset").addEventListener("click",()=>{state.revision++;state.scenario="passing";state.reports=[];state.record=null;state.originalDigest=null;state.observedDigest=null;state.tampered=false;renderReports();renderRecord()});
renderReports();renderRecord();renderMetrics();loadMetrics().catch(()=>renderMetrics());bootFromLocation().catch(error=>{console.warn(error.message)});
