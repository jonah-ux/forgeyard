const state={reports:[],record:null,originalDigest:null,tampered:false,scenario:"passing",metrics:null};
const $=id=>document.getElementById(id);
let passingReports=[];let adversarialReports=[];

async function digest(value){const bytes=new TextEncoder().encode(JSON.stringify(value));const hash=await crypto.subtle.digest("SHA-256",bytes);return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,"0")).join("")}
async function loadReports(scenario){
  if(!passingReports.length||!adversarialReports.length){
    const responses=await Promise.all([fetch("fixtures/specialists.json"),fetch("fixtures/adversarial.json")]);
    if(responses.some(response=>!response.ok))throw new Error("workbench fixture could not be loaded");
    const [fixture,adversarial]=await Promise.all(responses.map(response=>response.json()));
    if(fixture.schema!=="forgeyard-workbench-fixture/v1"||!Array.isArray(fixture.reports))throw new Error("invalid workbench fixture");
    if(adversarial.schema!=="forgeyard-workbench-adversarial/v1"||!Array.isArray(adversarial.reports))throw new Error("invalid adversarial fixture");
    passingReports=fixture.reports;adversarialReports=adversarial.reports;
  }
  const reports=scenario==="passing"?passingReports:scenario==="adversarial"?adversarialReports:[...passingReports,{name:"mcp-doctor-drift",schema:"mcp-doctor/v1",ok:false,summary:"baseline drift refused",details:["MCP010","description changed"]}];
  state.reports=reports.map(r=>({...r,details:[...r.details]}));state.scenario=scenario;state.record=null;state.tampered=false;renderReports();renderRecord()
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
  $("metrics-badge").textContent=metrics?"CURRENT":"UNKNOWN";
  $("metrics-badge").className=`badge ${metrics?"ok":"bad"}`;
  if(!metrics){
    $("metrics-list").innerHTML='<div class="empty">No current receipt is available.</div>';
    $("metrics-meta").textContent="Unknown stays unknown until the benchmark is rerun.";
    return;
  }
  $("metrics-list").innerHTML=metrics.metrics.map(metric=>`<article class="metric-card" data-direction="${metric.direction}"><div class="metric-top"><span class="metric-label">${metric.label}</span><span class="metric-direction">${metric.direction==="lower"?"LOWER IS BETTER":"CEILING"}</span></div><div class="metric-values"><div><small>BASELINE</small><strong>${metric.value}<em>${metric.unit}</em></strong></div><span class="metric-arrow">→</span><div><small>3× TARGET</small><strong>${metric.target}<em>${metric.unit}</em></strong></div></div><p>${metric.note}</p></article>`).join("");
  $("metrics-meta").textContent=`${metrics.protocol} · ${metrics.environment} · n=${metrics.sample_count} · ${metrics.guardrail} · receipt ${metrics.receipt}`;
}
function renderLaunch(){
 const phase=state.tampered?"reset":state.record?"tamper":state.reports.length?"compose":"load";
 const labels={load:["WAITING","Load a passing scenario to light up the review loop."],compose:["REPORTS READY","Compose the bounded decision when the inputs look right."],tamper:["SEALED","Simulate tamper to see the digest refuse changed bytes."],reset:["REFUSED","The displayed record changed. Reset and start a clean review."]};
 $("launch-state").textContent=labels[phase][0];$("launch-hint").textContent=labels[phase][1];
 document.querySelectorAll("[data-phase-action]").forEach(button=>{const action=button.dataset.phaseAction;button.setAttribute("aria-current",String(action===phase));button.disabled=action==="compose"&&!state.reports.length||action==="tamper"&&!state.record;});
}
function renderReports(){
 $("reports").innerHTML=state.reports.map((r,index)=>`<article class="report ${r.ok?"":"fail"}"><div class="report-top"><span class="report-name"><span class="report-index">${String(index+1).padStart(2,"0")}</span>${r.name}</span><span class="report-result ${r.ok?"":"fail"}">${r.ok?"PASS":"FAIL"}</span></div><div class="report-schema"><span class="schema-pill">${r.schema}</span> ${r.summary}</div><div class="report-schema report-details">${r.details.join(" · ")}</div></article>`).join("");
 $("specialist-count").textContent=state.reports.length;
 const label=state.scenario==="passing"?"Passing":state.scenario==="adversarial"?"Adversarial":"Failing";
 $("specialist-state").textContent=state.reports.length?`${label} synthetic scenario loaded`:"Waiting for fixtures";
 $("input-badge").textContent=state.reports.length?(state.scenario==="passing"?"PASSING":"REFUSAL"):"EMPTY";
 $("input-badge").className=`badge ${state.scenario==="passing"&&state.reports.length?"ok":state.reports.length?"bad":""}`;
 $("compose").disabled=!state.reports.length;
 renderLaunch();
}
async function compose(){
 const record={schema:"forgeyard-compose/v1",task_id:`workbench-${state.scenario}`,repository:"synthetic-fixture",request:"review specialist reports",status:state.reports.every(r=>r.ok)?"ready_for_review":"blocked",evidence:state.reports.map(r=>({name:r.name,status:r.ok?"pass":"fail",detail:`schema=${r.schema}; ok=${r.ok}`,revision:"workbench-demo"})),boundary:"integrity is separate from outcome"};
 state.originalDigest=await digest(record);state.record=record;state.tampered=false;renderRecord();
}
function renderRecord(){
 const r=state.record;
 $("record").textContent=r?JSON.stringify({...r,sha256:state.originalDigest},null,2):"Load a scenario to create a bounded record.";
 $("decision").textContent=r?(r.status==="ready_for_review"?"READY":"BLOCKED"):"—";
 $("decision-detail").textContent=r?(r.status==="ready_for_review"?"All supplied evidence passed":"A specialist report failed closed"):"No record composed";
 $("integrity").textContent=state.tampered?"REFUSED":r?"SEALED":"—";
 $("integrity-detail").textContent=state.tampered?"Record bytes changed after sealing":r?`sha256 ${state.originalDigest.slice(0,16)}…`:"No digest calculated";
 $("record-badge").textContent=r?(r.status==="ready_for_review"?"REVIEWABLE":"BLOCKED"):"NOT READY";
 $("record-badge").className=`badge ${r?(r.status==="ready_for_review"?"ok":"bad"):""}`;
 $("record-foot-text").textContent=state.tampered?"Digest no longer matches the displayed record.":r?(r.status==="ready_for_review"?"Record sealed; every supplied signal passed.":"Record sealed with a failed specialist signal."):"No record has been sealed yet.";
 $("record-foot-mark").style.background=state.tampered?"var(--red)":r?"var(--cyan)":"var(--muted)";
 const tone=r?(state.tampered||r.status!=="ready_for_review"?"bad":"ok"):"neutral";
 ["specialist-count","decision","integrity"].forEach(id=>$(id).closest(".status-card").dataset.tone=tone);
 $("tamper").disabled=!r;$("export").disabled=!r;
 renderLaunch();
 renderLab();
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
function exportRecord(){if(!state.record)return;const blob=new Blob([JSON.stringify({...state.record,sha256:state.originalDigest},null,2)+"\n"],{type:"application/json"});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download=`${state.record.task_id}.json`;link.click();URL.revokeObjectURL(link.href)}
$("load-demo").addEventListener("click",()=>loadReports("passing").catch(error=>alert(error.message)));
$("load-failure").addEventListener("click",()=>loadReports("failing").catch(error=>alert(error.message)));
$("load-adversarial").addEventListener("click",()=>loadReports("adversarial").catch(error=>alert(error.message)));
$("compose").addEventListener("click",compose);$("export").addEventListener("click",exportRecord);
$("tamper").addEventListener("click",()=>{if(!state.record)return;state.tampered=true;$("record").textContent=JSON.stringify({...state.record,request:"tampered request",sha256:state.originalDigest},null,2);renderRecord()});
$("reset").addEventListener("click",()=>{state.reports=[];state.record=null;state.tampered=false;renderReports();renderRecord()});
document.querySelectorAll("[data-phase-action]").forEach(button=>button.addEventListener("click",()=>{const action=button.dataset.phaseAction;if(action==="load")$("load-demo").click();else if(action==="compose")$("compose").click();else if(action==="tamper")$("tamper").click();else $("reset").click()}));
renderReports();renderRecord();renderMetrics();loadMetrics().catch(()=>renderMetrics());
