const state={reports:[],record:null,originalDigest:null,tampered:false};
const $=id=>document.getElementById(id);
const demoReports=[
 {name:"mcp-doctor",schema:"mcp-doctor/v1",ok:true,summary:"contract shape passed",details:["1 tool","1 resource","1 prompt"]},
 {name:"agent-proof",schema:"agent-proof/interop/v1",ok:true,summary:"observed evidence sealed",details:["source bytes bound","unknowns explicit"]}
];
async function digest(value){const bytes=new TextEncoder().encode(JSON.stringify(value));const hash=await crypto.subtle.digest("SHA-256",bytes);return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,"0")).join("")}
function renderReports(){
 $("reports").innerHTML=state.reports.map(r=>`<article class="report"><div class="report-top"><span class="report-name">${r.name}</span><span class="report-result ${r.ok?"":"fail"}">${r.ok?"PASS":"FAIL"}</span></div><div class="report-schema">${r.schema} · ${r.summary}</div><div class="report-schema">${r.details.join(" · ")}</div></article>`).join("");
 $("specialist-count").textContent=state.reports.length;$("specialist-state").textContent=state.reports.length?"Bounded synthetic reports loaded":"Waiting for fixtures";$("input-badge").textContent=state.reports.length?"LOADED":"EMPTY";$("compose").disabled=!state.reports.length;
}
async function compose(){
 const record={schema:"forgeyard-compose/v1",task_id:"workbench-demo",repository:"synthetic-fixture",request:"review specialist reports",status:state.reports.every(r=>r.ok)?"ready_for_review":"blocked",evidence:state.reports.map(r=>({name:r.name,status:r.ok?"pass":"fail",detail:`schema=${r.schema}; ok=${r.ok}`,revision:"workbench-demo"})),boundary:"integrity is separate from outcome"};
 state.originalDigest=await digest(record);state.record=record;state.tampered=false;renderRecord();
}
function renderRecord(){const r=state.record;$("record").textContent=r?JSON.stringify({...r,sha256:state.originalDigest},null,2):"Load the demo to create a bounded record.";$("decision").textContent=r?(r.status==="ready_for_review"?"READY":"BLOCKED"):"—";$("decision-detail").textContent=r?(r.status==="ready_for_review"?"All supplied evidence passed":"A specialist report failed"):"No record composed";$("integrity").textContent=state.tampered?"REFUSED":r?"SEALED":"—";$("integrity-detail").textContent=state.tampered?"Record bytes changed after sealing":r?`sha256 ${state.originalDigest.slice(0,16)}…`:"No digest calculated";$("record-badge").textContent=r?(r.status==="ready_for_review"?"REVIEWABLE":"BLOCKED"):"NOT READY";$("record-badge").className=`badge ${r?(r.status==="ready_for_review"?"ok":"bad"):""}`;$("tamper").disabled=!r}
$("load-demo").addEventListener("click",()=>{state.reports=demoReports.map(r=>({...r,details:[...r.details]}));state.record=null;state.tampered=false;renderReports();renderRecord()});$("compose").addEventListener("click",compose);$("tamper").addEventListener("click",()=>{if(!state.record)return;state.tampered=true;$("record").textContent=JSON.stringify({...state.record,request:"tampered request",sha256:state.originalDigest},null,2);renderRecord()});$("reset").addEventListener("click",()=>{state.reports=[];state.record=null;state.tampered=false;renderReports();renderRecord()});renderReports();renderRecord();
