"use strict";

var baseAddMessage=addMessage;
var baseAddOrchestration=addOrchestration;
var baseFinishOrchestration=finishOrchestration;
var baseApplyLanguage=applyLanguage;
var baseEnterWorkspace=enterWorkspace;

function qualityText(quality){
  if(!quality)return "Answer quality not yet rated";
  if(quality.evidence_status==="grounded")return "Grounded in "+quality.source_count+" approved source"+(quality.source_count===1?"":"s");
  if(quality.evidence_status==="insufficient_evidence")return "Needs more approved knowledge";
  if(quality.evidence_status==="not_required")return "No company source required";
  return "Legacy answer — quality not measured";
}

function submitFeedback(messageId,rating,button){
  var comment="";
  if(rating==="not_helpful"){
    var response=window.prompt("What was missing or incorrect? This is optional.","");
    if(response===null)return;
    comment=response;
  }
  api("/api/messages/"+encodeURIComponent(messageId)+"/feedback",{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({rating:rating,comment:comment})
  }).then(function(){
    button.parentElement.querySelectorAll(".feedback-button").forEach(function(item){item.classList.toggle("selected",item.dataset.rating===rating)});
    showToast("Thank you. Your feedback was recorded for quality improvement.");
    if(state.user&&state.user.role==="owner"&&state.currentView==="dashboard")loadDashboard();
  }).catch(function(error){showToast(error.message)});
}

addMessage=function(role,content,meta){
  var wrapper=baseAddMessage(role,content,meta);
  if(role!=="assistant"||!meta)return wrapper;
  var body=wrapper.querySelector(".message-body");
  var quality=document.createElement("div");quality.className="answer-quality";
  var evidence=document.createElement("span");var evidenceStatus=meta.quality&&meta.quality.evidence_status||"unknown";
  evidence.className="evidence-badge "+evidenceStatus;evidence.textContent=qualityText(meta.quality);quality.appendChild(evidence);
  if(meta.messageId){
    var controls=document.createElement("div");controls.className="feedback-controls";controls.innerHTML="<span>Was this useful?</span>";
    [["helpful","&#128077;","Helpful"],["not_helpful","&#128078;","Not helpful"]].forEach(function(item){
      var button=document.createElement("button");button.type="button";button.className="feedback-button"+(meta.feedbackRating===item[0]?" selected":"");button.dataset.rating=item[0];button.innerHTML=item[1];button.title=item[2];button.setAttribute("aria-label",item[2]);button.addEventListener("click",function(){submitFeedback(meta.messageId,item[0],button)});controls.appendChild(button)
    });
    quality.appendChild(controls);
  }
  body.appendChild(quality);
  if(meta.messageId&&!meta.history)window.setTimeout(loadConversations,0);
  return wrapper;
};

function addRetryControl(card){
  var controls=card.querySelector(".orchestration-controls");
  if(!controls||controls.querySelector(".retry-execution"))return;
  var retry=document.createElement("button");retry.type="button";retry.className="execution-button retry-execution";retry.textContent="Retry";
  retry.addEventListener("click",function(){var input=byId("messageInput");input.value=card.dataset.prompt||"";autoResize(input);sendMessage()});
  controls.insertBefore(retry,controls.firstChild);
}

addOrchestration=function(message){
  var wrapper=baseAddOrchestration();wrapper.dataset.prompt=message||"";
  var head=wrapper.querySelector(".orchestration-head");var stateNode=head.querySelector(".orchestration-state");
  var controls=document.createElement("div");controls.className="orchestration-controls";
  var cancel=document.createElement("button");cancel.type="button";cancel.className="execution-button cancel-execution";cancel.textContent="Cancel";
  cancel.addEventListener("click",cancelCurrentExecution);controls.appendChild(cancel);controls.appendChild(stateNode);head.appendChild(controls);
  return wrapper;
};

finishOrchestration=function(card,failed){
  baseFinishOrchestration(card,failed);var cancel=card.querySelector(".cancel-execution");if(cancel)cancel.remove();if(failed)addRetryControl(card)
};

function cancelOrchestration(card){
  var stateNode=card.querySelector(".orchestration-state");stateNode.className="orchestration-state cancelled";stateNode.textContent="CANCELLED";
  var cancel=card.querySelector(".cancel-execution");if(cancel)cancel.remove();
  card.querySelectorAll(".orchestration-step.running,.orchestration-step.queued").forEach(function(row){row.classList.remove("running","queued");row.classList.add("skipped");var status=row.querySelector(".step-status");if(status)status.textContent="Stopped"});
  addRetryControl(card);
}

function cancelCurrentExecution(){
  state.cancelRequested=true;
  if(state.activeSocket&&state.activeSocket.readyState===WebSocket.OPEN){state.activeSocket.send(JSON.stringify({type:"cancel"}))}
  var button=document.querySelector(".cancel-execution");if(button){button.disabled=true;button.textContent="Stopping…"}
}

streamChat=function(message,card){
  return new Promise(function(resolve,reject){
    var settled=false;state.cancelRequested=false;var protocol=location.protocol==="https:"?"wss:":"ws:";var socket=new WebSocket(protocol+"//"+location.host+"/api/chat/stream");state.activeSocket=socket;
    function cancelledError(){var error=new Error("Request cancelled");error.cancelled=true;return error}
    socket.onopen=function(){socket.send(JSON.stringify({message:message,conversation_id:state.conversationId,language:state.language}));if(state.cancelRequested)socket.send(JSON.stringify({type:"cancel"}))};
    socket.onmessage=function(event){var payload;try{payload=JSON.parse(event.data)}catch(_){return}
      if(payload.type==="plan")renderPlan(card,payload.steps||[]);
      else if(payload.type==="step")updateStep(card,payload);
      else if(payload.type==="complete"){settled=true;state.activeSocket=null;finishOrchestration(card,false);resolve(payload.result);socket.close()}
      else if(payload.type==="cancelled"){settled=true;state.activeSocket=null;reject(cancelledError());socket.close()}
      else if(payload.type==="error"){settled=true;state.activeSocket=null;finishOrchestration(card,true);reject(new Error(payload.detail||"Request failed"));socket.close()}
    };
    socket.onerror=function(){if(!settled){settled=true;state.activeSocket=null;reject(state.cancelRequested?cancelledError():new Error("Live orchestration connection unavailable"))}};
    socket.onclose=function(event){if(!settled&&event.code!==1000){settled=true;state.activeSocket=null;reject(state.cancelRequested?cancelledError():new Error("Live orchestration connection closed"))}}
  })
};

async function loadConversations(){
  if(!state.user)return;var list=byId("conversationList");
  try{
    var result=await api("/api/conversations");
    if(!result.conversations.length){list.innerHTML='<div class="conversation-empty">Your conversations will appear here.</div>';return}
    list.innerHTML="";
    result.conversations.forEach(function(conversation){
      var row=document.createElement("div");row.className="conversation-row"+(conversation.id===state.conversationId?" active":"");
      row.innerHTML='<button class="conversation-open" type="button" title="'+escapeHtml(conversation.title)+'">'+escapeHtml(conversation.title)+'</button><button class="conversation-control rename" type="button" title="Rename" aria-label="Rename">&#9998;</button><button class="conversation-control delete" type="button" title="Delete" aria-label="Delete">&times;</button>';
      row.querySelector(".conversation-open").addEventListener("click",function(){openConversation(conversation.id)});
      row.querySelector(".rename").addEventListener("click",function(){renameConversation(conversation)});
      row.querySelector(".delete").addEventListener("click",function(){deleteConversation(conversation)});
      list.appendChild(row)
    })
  }catch(error){list.innerHTML='<div class="conversation-empty">'+escapeHtml(error.message)+"</div>"}
}

async function openConversation(id){
  try{
    var result=await api("/api/conversations/"+encodeURIComponent(id));var conversation=result.conversation;state.conversationId=conversation.id;
    byId("messages").innerHTML="";byId("welcomePanel").classList.add("hidden");showView("chat");
    conversation.messages.forEach(function(message){
      if(message.message_role==="user")addMessage("user",message.content);
      else{
        var metadata=message.metadata||{};addMessage("assistant",message.content,{route:{label:friendly(metadata.route||"Assistant")},model:metadata.model||"unknown",sources:metadata.sources||[],messageId:message.id,feedbackRating:message.feedback_rating,quality:{evidence_status:metadata.evidence_status||"unknown",source_count:metadata.source_count||0,latency_ms:metadata.latency_ms},history:true})
      }
    });
    loadConversations();scrollChat()
  }catch(error){showToast(error.message)}
}

async function renameConversation(conversation){
  var title=window.prompt("Rename conversation",conversation.title);if(title===null||!title.trim())return;
  try{await api("/api/conversations/"+encodeURIComponent(conversation.id),{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:title.trim()})});showToast("Conversation renamed.");loadConversations()}catch(error){showToast(error.message)}
}

async function deleteConversation(conversation){
  if(!window.confirm('Delete "'+conversation.title+'" and its messages?'))return;
  try{await api("/api/conversations/"+encodeURIComponent(conversation.id),{method:"DELETE"});if(state.conversationId===conversation.id){state.conversationId=null;byId("messages").innerHTML="";byId("welcomePanel").classList.remove("hidden")};showToast("Conversation deleted.");loadConversations()}catch(error){showToast(error.message)}
}

loadDocuments=async function(){
  var list=byId("documentsList");list.innerHTML="<p>Loading sources&hellip;</p>";
  try{
    var result=await api("/api/documents");if(!result.documents.length){list.innerHTML="<p>No accessible documents yet.</p>";return}
    list.innerHTML=result.documents.map(function(doc){var updated=doc.updated_at?new Date(doc.updated_at+(/[z+]$/i.test(doc.updated_at)?"":"Z")).toLocaleDateString():"Unknown date";return '<div class="document-row"><span class="doc-icon">D</span><div><strong>'+escapeHtml(doc.title)+"</strong><small>"+escapeHtml(doc.source)+'</small><div class="document-badges"><span class="index-pill">'+escapeHtml(friendly(doc.index_status))+"</span><small>"+escapeHtml(String(doc.chunk_count||0))+" chunks · Updated "+escapeHtml(updated)+'</small></div></div><span class="team-pill">'+escapeHtml(friendly(doc.team))+"</span></div>"}).join("")
  }catch(error){list.innerHTML="<p>"+escapeHtml(error.message)+"</p>"}
};

async function loadDashboard(){
  if(!state.user||state.user.role!=="owner")return;var target=byId("dashboardMetrics");target.innerHTML="<p>Loading quality metrics&hellip;</p>";
  try{
    var result=await api("/api/admin/dashboard");var metrics=result.metrics;var latency=metrics.average_latency_ms===null?"—":(metrics.average_latency_ms/1000).toFixed(1)+"s";var helpful=metrics.helpful_rate===null?"—":metrics.helpful_rate+"%";
    var cards=[[metrics.users,"Employees",metrics.approved_users+" approved"],[metrics.conversations,"Conversations",metrics.messages+" total messages"],[helpful,"Helpful answers",metrics.helpful+" positive · "+metrics.not_helpful+" negative"],[latency,"Average answer time",metrics.measured_latency_answers+" measured answers"],[metrics.insufficient_evidence_answers,"Needs knowledge","Correctly refused without evidence"],[metrics.pending_actions,"Pending actions","Sandbox confirmations only"]];
    target.innerHTML=cards.map(function(card){return '<div class="metric-card"><span>'+escapeHtml(card[1])+'</span><strong>'+escapeHtml(card[0])+'</strong><small>'+escapeHtml(card[2])+"</small></div>"}).join("");
    byId("routeMetrics").innerHTML=metrics.top_routes.map(function(item){return '<div class="route-row"><span>'+escapeHtml(friendly(item.route))+"</span><strong>"+escapeHtml(item.count)+"</strong></div>"}).join("")||"<p>No completed answers yet.</p>"
  }catch(error){target.innerHTML="<p>"+escapeHtml(error.message)+"</p>"}
}

var systemActions={};

function renderServiceStatusCard(id,service){
  var card=byId(id);var stateLabel="Stopped";var className="offline";
  if(service.running&&service.managed){stateLabel="Running"+(service.pid?" / PID "+service.pid:"");className="online"}
  else if(service.running){stateLabel="Needs attention"+(service.pid?" / PID "+service.pid:"");className="warning"}
  card.className="service-status-card "+className;
  card.querySelector("strong").textContent=stateLabel;
  card.querySelector("small").textContent=service.detail||"Status unavailable";
}

async function loadSystemStatus(){
  if(!state.user||state.user.role!=="owner")return;
  var message=byId("systemStatusMessage");message.textContent="Checking the managed RAG servicesâ€¦";
  try{
    var result=await api("/api/admin/system");
    systemActions={};(result.actions||[]).forEach(function(action){systemActions[action.id]=action});
    renderServiceStatusCard("applicationServiceStatus",result.application);
    renderServiceStatusCard("modelServiceStatus",result.model_server);
    var available=result.supported&&result.enabled&&result.configured;var control=byId("serviceControlAvailability");
    control.className="service-status-card "+(available?"online":"warning");
    control.querySelector("strong").textContent=available?"Ready":!result.supported?"RAG host only":!result.enabled?"Disabled":"Key not configured";
    control.querySelector("small").textContent=available?"Owner login plus service-control key required":"Use the SSH commands below or update the server configuration";
    document.querySelectorAll("[data-system-action]").forEach(function(button){button.disabled=!available});
    if(result.recovery&&result.supported){byId("systemRecoveryCommand").textContent=result.recovery.start;byId("systemRecoveryStatusCommand").textContent="Status: "+result.recovery.status}
    message.className="system-status-message "+(available?"ready":"notice");
    message.textContent=available?"Controls are ready. Status reflects only validated project-managed PIDs.":!result.supported?"Web service controls are intentionally unavailable in the local Windows copy. They become active on the Linux RAG host.":"Web controls are not enabled. SSH recovery commands remain available.";
  }catch(error){
    document.querySelectorAll("[data-system-action]").forEach(function(button){button.disabled=true});
    message.className="system-status-message error";message.textContent=error.message
  }
}

function openSystemAction(actionId){
  var action=systemActions[actionId];if(!action){showToast("Refresh service status before choosing an action.");return}
  var form=byId("systemControlForm");form.dataset.action=actionId;
  byId("systemActionTitle").textContent=action.label;byId("systemActionImpact").textContent=action.impact;
  byId("systemConfirmationPhrase").textContent=action.confirmation;byId("systemConfirmation").value="";byId("systemAdminKey").value="";byId("systemControlError").textContent="";
  byId("submitSystemControl").classList.toggle("danger-button",actionId.indexOf("stop")===0||actionId==="stop_all");
  byId("systemControlDialog").showModal();byId("systemConfirmation").focus()
}

function waitForSystemRecovery(attempt){
  if(attempt>24){showToast("The restart is taking longer than expected. Use the SSH status command if needed.");return}
  window.setTimeout(async function(){
    try{await api("/api/health");location.reload()}
    catch(_){waitForSystemRecovery(attempt+1)}
  },3000)
}

async function submitSystemAction(event){
  event.preventDefault();var form=byId("systemControlForm");var actionId=form.dataset.action;var action=systemActions[actionId];if(!action)return;
  var key=byId("systemAdminKey").value;var confirmation=byId("systemConfirmation").value;byId("systemAdminKey").value="";
  var submit=byId("submitSystemControl");submit.disabled=true;byId("systemControlError").textContent="";
  try{
    var result=await api("/api/admin/system/"+encodeURIComponent(actionId),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({admin_key:key,confirmation:confirmation})});
    key="";byId("systemConfirmation").value="";byId("systemControlDialog").close();showToast(result.message);
    if(actionId==="restart_app"||actionId==="restart_all"){byId("systemStatusMessage").textContent="Restart in progress. This page will reconnect automatically.";waitForSystemRecovery(0)}
    else if(actionId==="stop_all"){byId("systemStatusMessage").className="system-status-message error";byId("systemStatusMessage").textContent="Stopping all services. Use the SSH start command below to restore this page."}
    else{window.setTimeout(loadSystemStatus,4000)}
  }catch(error){key="";byId("systemControlError").textContent=error.message}
  finally{submit.disabled=false}
}

showView=function(view,languageOnly){
  state.currentView=view;
  if(!languageOnly){document.querySelectorAll(".view").forEach(function(node){node.classList.add("hidden")});var target=byId(view+"View");if(!target)return;target.classList.remove("hidden");document.querySelectorAll(".nav-item").forEach(function(node){node.classList.toggle("active",node.dataset.view===view)})}
  var titles={chat:[t("eyebrow"),t("title")],knowledge:["KNOWLEDGE","Approved sources and team memory"],dashboard:["QUALITY & ADOPTION","Is the assistant useful, grounded and improving?"],people:["ACCESS CONTROL","People and department permissions"],audit:["AUDIT","Traceable activity and control evidence"],system:["RAG OPERATIONS","Start, stop and recover project services"]};
  byId("viewEyebrow").textContent=titles[view][0];byId("viewTitle").textContent=titles[view][1];
  if(!languageOnly){if(view==="knowledge")loadDocuments();if(view==="dashboard")loadDashboard();if(view==="people")loadUsers();if(view==="audit")loadAudit();if(view==="system")loadSystemStatus()}
};

applyLanguage=function(language){baseApplyLanguage(language);var labels={English:"RECENT",Hindi:"हाल की बातचीत",Hinglish:"RECENT CHATS"};byId("recentLabel").textContent=labels[state.language]||"RECENT"};
enterWorkspace=async function(){await baseEnterWorkspace();await loadConversations()};

function openProfileDialog(){
  if(!state.user)return;var profile=state.user.profile||{};byId("profileRoleTitle").value=state.user.role_title||"";byId("profileResponsibilities").value=profile.responsibilities||"";byId("profileRecurringTasks").value=profile.recurring_tasks||"";byId("profileToolsUsed").value=profile.tools_used||"";byId("profileAutomationGoals").value=profile.automation_goals||"";byId("profileError").textContent="";byId("profileDialog").showModal()
}

async function logoutSession(){await api("/api/logout",{method:"POST"});location.reload()}

function bindEnhancements(){
  byId("refreshConversations").addEventListener("click",loadConversations);
  byId("refreshDashboard").addEventListener("click",loadDashboard);
  byId("closeProfile").addEventListener("click",function(){byId("profileDialog").close()});
  byId("profileLogout").addEventListener("click",logoutSession);
  byId("refreshSystem").addEventListener("click",loadSystemStatus);
  document.querySelectorAll("[data-system-action]").forEach(function(button){button.addEventListener("click",function(){openSystemAction(button.dataset.systemAction)})});
  byId("closeSystemControl").addEventListener("click",function(){byId("systemAdminKey").value="";byId("systemControlDialog").close()});
  byId("cancelSystemControl").addEventListener("click",function(){byId("systemAdminKey").value="";byId("systemControlDialog").close()});
  byId("systemControlForm").addEventListener("submit",submitSystemAction);
  byId("profileForm").addEventListener("submit",async function(event){
    event.preventDefault();byId("profileError").textContent="";
    try{var result=await api("/api/profile",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({role_title:byId("profileRoleTitle").value,responsibilities:byId("profileResponsibilities").value,recurring_tasks:byId("profileRecurringTasks").value,tools_used:byId("profileToolsUsed").value,automation_goals:byId("profileAutomationGoals").value})});state.user=result.user;hydrateProfile();byId("profileDialog").close();showToast("Employee memory updated.")}catch(error){byId("profileError").textContent=error.message}
  });
  byId("newChatButton").addEventListener("click",loadConversations);
  window.setTimeout(function(){if(state.user)loadConversations()},300)
}

bindEnhancements();
