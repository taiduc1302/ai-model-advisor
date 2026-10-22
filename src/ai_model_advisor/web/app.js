"use strict";
const $ = id => document.getElementById(id);
const task = $("task"), submit = $("submit"), error = $("form-error");
let current = null;
const example = "Audit my Python repository, investigate why integration tests fail, implement a safe fix, and verify the test suite.";
function line(container,text){const li=document.createElement("li");li.textContent=text;container.appendChild(li)}
function fill(id,items){const node=$(id);node.replaceChildren();for(const value of items)line(node,value)}
function details(record){if(!record)return null;return record.label+" · "+record.effort+" reasoning · "+record.execution_mode.replaceAll("_"," ")}
function render(response){
 const d=response.decision;current=d;$("empty").hidden=true;$("results").hidden=false;
 const p=d.primary;$("primary-name").textContent=p.label;$("primary-provider").textContent=p.provider.toUpperCase()+"  /  "+p.model_id;
 const chips=$("primary-chips");chips.replaceChildren();for(const text of [p.effort+" reasoning",p.execution_mode.replaceAll("_"," ")]){const n=document.createElement("span");n.className="chip";n.textContent=text;chips.appendChild(n)}
 $("primary-reason").textContent=(p.reasons||[]).slice(0,2).join(" ")||"Selected from the current model registry and workload profile.";
 $("primary-score").textContent="Routing score "+Number(p.score).toFixed(1);
 $("primary-confidence").textContent="Heuristic confidence "+Math.round(Number(p.confidence)*100)+"%";
 $("fallback-name").textContent=d.cheaper_fallback?.label||"No qualified fallback";
 $("fallback-sub").textContent=details(d.cheaper_fallback)||"No lower-priced model met the permitted quality-score gap.";
 $("escalation-name").textContent=d.escalation?.label||"Raise effort / review";
 $("escalation-sub").textContent=details(d.escalation)||"Follow the escalation instructions below.";
 fill("triggers",d.escalation_triggers||[]);fill("evidence",d.personal_evidence||[]);fill("notes",d.decision_notes||[]);
 $("analysis-date").textContent="REGISTRY · "+d.registry_as_of;
 $("results").scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
}
function showError(message){error.textContent=message;error.hidden=false}
task.addEventListener("input",()=>{$("char-count").textContent=task.value.length.toLocaleString()+" / 6,000";error.hidden=true});
$("example").addEventListener("click",()=>{task.value=example;task.dispatchEvent(new Event("input"));task.focus()});
submit.addEventListener("click",async()=>{
 const value=task.value.trim();
 if(!value){showError("Tell us what you need help with first.");task.focus();return}
 error.hidden=true;submit.disabled=true;submit.textContent="Finding your best configuration…";
 try{
  const priority=document.querySelector('input[name="priority"]:checked').value;
  const response=await fetch("/api/decide",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task:value,provider:$("provider").value,priority})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||"Recommendation unavailable.");
  render(data);
 }catch(e){showError(e.message||"Something went wrong. Try again.")}
 finally{submit.disabled=false;submit.replaceChildren();submit.textContent="✦  Find best configuration  →"}
});
$("copy").addEventListener("click",async()=>{
 if(!current)return;
 const p=current.primary;
 const text=["AI MODEL ADVISOR — RECOMMENDATION","Task: "+current.task,"Primary: "+p.label+" ("+p.model_id+")","Provider: "+p.provider,"Effort: "+p.effort,"Execution: "+p.execution_mode,"Fallback: "+(details(current.cheaper_fallback)||"None"),"Escalation: "+(details(current.escalation)||"Manual review"),"Evidence: "+current.personal_evidence.join(" ")].join("\n");
 try{await navigator.clipboard.writeText(text);$("copy").textContent="✓ Copied";setTimeout(()=>$("copy").textContent="⧉ Copy recommendation",1900)}catch{showError("Clipboard unavailable. You can select and copy the result manually.")}
});
fetch("/api/meta").then(r=>r.json()).then(d=>{$("version").textContent="v"+d.version;$("registry-status").textContent=d.current_models+" current models · "+d.registry_as_of}).catch(()=>{$("registry-status").textContent="Local registry"});
