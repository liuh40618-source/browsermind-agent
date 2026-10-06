'use strict';
const $ = selector => document.querySelector(selector);
const labels = {idle:'就绪',running:'研究中',waiting:'等待确认',done:'已完成',partial:'部分完成',cancelled:'已停止',error:'执行出错',failed:'未完成'};
const stageNames = {plan:'规划',browse:'浏览',parse:'解析',reflect:'校验',analyze:'报告',system:'系统'};
const examples = [
  '对比 Dify 与 n8n 的核心能力、部署方式和定价，给出适用场景与来源链接。',
  '调研 5 个值得关注的开源 Agent 框架，对比维护活跃度、核心能力与使用限制，标注来源。',
  '调研 AI 浏览器近一年的发展趋势，整理代表产品、技术路线与主要限制，提供来源链接。'
];
let ws=null, wsReady=false, running=false, regenerating=false, currentId=null, currentReport='';
let currentPages=[], logs=0, timer=null, startedAt=0, connectTimer=null;
let keyStatus=null, presets={}, authRequired=false, authToken='';
let historyOffset=0, historyRequest=0, searchTimer=null, historyReport=null, confirmAction=null;
try { authToken=sessionStorage.getItem('bm-auth')||''; } catch(e) {}
function icons(){ window.lucide?.createIcons(); }
function esc(value){ return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function now(){ return new Date().toTimeString().slice(0,8); }
function formatDuration(seconds){ const n=Math.max(0,Number(seconds)||0); return `${String(Math.floor(n/60)).padStart(2,'0')}:${String(Math.floor(n%60)).padStart(2,'0')}`; }
function toast(message){ const el=document.createElement('div');el.className='toast';el.textContent=message;$('#toasts').append(el);setTimeout(()=>el.remove(),4500); }
async function api(path, options={}){
  const headers=new Headers(options.headers);
  if(authToken) headers.set('X-Auth-Token',authToken);
  if(options.body) headers.set('Content-Type','application/json');
  let response;
  try { response=await fetch(path,{...options,headers,signal:options.signal||AbortSignal.timeout(15000)}); }
  catch(e){ throw new Error(e.name==='TimeoutError'?'请求超时，请重试':'无法连接服务，请检查服务是否启动'); }
  const data=await response.json().catch(()=>({}));
  if(response.status===401){authRequired=true;$('#auth-field').hidden=false;throw new Error('访问令牌缺失或错误，请在设置中连接');}
  if(!response.ok){const detail=data.detail||data.error;throw new Error(typeof detail==='string'?detail:`请求失败 (${response.status})`);}
  return data;
}
function switchView(view){
  for(const name of ['work','gallery']){
    $(`#view-${name}`).hidden=name!==view;
    $(`#tab-${name}`).classList.toggle('active',name===view);
    if(name===view) $(`#tab-${name}`).setAttribute('aria-current','page'); else $(`#tab-${name}`).removeAttribute('aria-current');
  }
  if(view==='gallery') loadGallery(0);
}
function taskChanged(){
  $('#task-count').textContent=`${$('#task-input').value.length} 字`;
  try{localStorage.setItem('bm-draft',$('#task-input').value);}catch(e){}
}
function useExample(index){ if(running)return;$('#task-input').value=examples[index];taskChanged();$('#task-input').focus(); }
function setStatus(status,text){ $('#status-pill').className=`badge ${status}`;$('#status-pill').textContent=text||labels[status]||status;$('#activity-status').textContent=text||labels[status]||status; }
function setRunning(value){
  running=value;$('#run-btn').disabled=value||regenerating;$('#task-input').disabled=value;
  $('#stop-btn').hidden=!value;$('#stop-btn').disabled=!wsReady;
  $('#progress').hidden=!value;$('#regen-btn').disabled=value||regenerating;
  document.querySelectorAll('#chips button').forEach(button=>button.disabled=value);
  clearInterval(timer);
  if(value){startedAt=Date.now();$('#duration').textContent='00:00';timer=setInterval(()=>{$('#duration').textContent=formatDuration((Date.now()-startedAt)/1000);},1000);}
}
function closeSocket(){const old=ws;ws=null;wsReady=false;clearTimeout(connectTimer);if(old)old.close();}
function resetRunUI(){
  currentId=null;currentReport='';currentPages=[];logs=0;
  $('#stepper').innerHTML='<li class="muted-empty">正在制定计划</li>';$('#plan-count').textContent='0 / 0';
  $('#timeline').replaceChildren();$('#log-count').textContent='0 条';
  $('#report').hidden=true;$('#report').replaceChildren();$('#report-empty').hidden=false;
  $('#report-actions').hidden=true;$('#report-meta').textContent='等待研究结果';$('#sources').hidden=true;
  $('#decision').hidden=true;$('#instruct').hidden=true;$('#followup').hidden=true;
  $('#stop-btn').innerHTML='<i data-lucide="square"></i>停止';
  document.querySelectorAll('[data-stage]').forEach(el=>el.classList.remove('lit','active'));
  icons();
}
async function runTask(){
  if(running||regenerating)return;
  const task=$('#task-input').value.trim();
  if(!task){toast('请输入研究任务');$('#task-input').focus();return;}
  if(task.length>12000){toast('任务不能超过 12000 字符');return;}
  if(!keyStatus?.has_api_key){await refreshConnection();if(!keyStatus?.has_api_key){openSettings();return;}}
  // Ignore callbacks from older sessions after starting a new task.
  closeSocket();resetRunUI();setRunning(true);setStatus('running','连接中');
  const socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/agent/stream`);ws=socket;
  connectTimer=setTimeout(()=>{if(ws===socket&&!wsReady){toast('连接超时，请重试');closeSocket();setRunning(false);setStatus('error','连接超时');}},15000);
  socket.onopen=()=>{if(ws!==socket)return;clearTimeout(connectTimer);wsReady=true;$('#stop-btn').disabled=false;setStatus('running');socket.send(JSON.stringify({task,token:authToken}));};
  socket.onmessage=event=>{if(ws!==socket)return;try{handleMsg(JSON.parse(event.data));}catch(e){toast('执行消息格式异常');console.error(e);}};
  socket.onerror=()=>{if(ws===socket)toast('连接异常，请检查服务状态');};
  socket.onclose=()=>{if(ws!==socket)return;clearTimeout(connectTimer);wsReady=false;$('#followup').hidden=true;$('#decision').hidden=true;if(running){setRunning(false);setStatus('error','连接已断开');toast('连接已断开，本次执行已停止');}else{$('#activity-status').textContent='会话已结束';}};
}
function stopTask(){
  if(!running)return;
  if(!wsReady){closeSocket();setRunning(false);setStatus('cancelled');return;}
  if(send({type:'cancel'})){ $('#stop-btn').disabled=true;setStatus('running','正在停止');$('#decision').hidden=true;toast('正在停止当前请求'); }
}
function send(message){if(!ws||ws.readyState!==WebSocket.OPEN){toast('会话已结束，请重新开始研究');return false;}ws.send(JSON.stringify(message));return true;}
function handleMsg(message){
  const {type,data}=message;
  if(type==='plan'||type==='plan_steps')renderPlan(data);
  else if(type==='log')addLog(data||{});
  else if(type==='reflection')addLog({agent:'Reflection',action:'完成度评估',detail:`完成度 ${data?.score??0}% · ${data?.reason||''}`,time:now()});
  else if(type==='done')finishRun(data||{});
  else if(type==='error'){
    const text=message.message||data?.message||'未知错误';addLog({agent:'System',action:'执行出错',detail:text,time:now()});
    closeSocket();setRunning(false);setStatus('error');$('#decision').hidden=true;$('#followup').hidden=true;toast(text);
  }
}
function renderPlan(value){
  const steps=Array.isArray(value)?value:(value?.steps||[]);
  if(!steps.length)return;
  $('#stepper').innerHTML=steps.map((step,index)=>{
    const s=typeof step==='string'?{goal:step}:step;
    const status=s.status==='done'?'done':s.status==='running'?'run':'';
    const title=s.name||s.goal||s.title||s.description||`步骤 ${index+1}`;
    return `<li class="step ${status}"><span class="num">${status==='done'?'<i data-lucide="check"></i>':index+1}</span><span class="txt">${esc(title)}${s.name&&s.goal&&s.name!==s.goal?`<small>${esc(s.goal)}</small>`:''}</span></li>`;
  }).join('');
  $('#plan-count').textContent=`${steps.filter(s=>s.status==='done').length} / ${steps.length}`;icons();
}
function addLog(log){
  const box=$('#timeline');const stick=box.scrollHeight-box.scrollTop-box.clientHeight<100;
  $('#activity-empty')?.remove();
  const stage=({Planner:'plan',Browser:'browse',Parser:'parse',Reflection:'reflect',Analyst:'analyze',Agent:'browse'})[log.agent]||'system';
  let detail=log.detail??'';if(typeof detail!=='string')detail=JSON.stringify(detail,null,2);
  const node=document.createElement('div');node.className='tl-node';
  const body=detail.length>260?`<details><summary>${esc(detail.slice(0,100))}</summary><div class="tl-detail">${esc(detail)}</div></details>`:`<div class="tl-detail">${esc(detail)}</div>`;
  node.innerHTML=`<span class="tl-dot ${stage}"></span><div class="tl-top"><span>${esc(log.agent||'System')} / ${stageNames[stage]}</span><time class="tl-time">${esc(log.time||now())}</time></div><div class="tl-action">${esc(log.action||'执行记录')}</div>${body}`;
  box.append(node);logs++;$('#log-count').textContent=`${logs} 条`;
  if(box.children.length>500)box.firstElementChild.remove();
  if(running&&stage!=='system'){
    document.querySelectorAll('[data-stage]').forEach(el=>el.classList.toggle('active',el.dataset.stage===stage));
    $(`[data-stage="${stage}"]`)?.classList.add('lit');
    if($('#decision').hidden)setStatus('running',`${stageNames[stage]}中`);
  }
  if(log.action==='等待用户决策'){try{showDecision(JSON.parse(detail));}catch(e){}}
  if(log.action==='用户决策超时'){$('#decision').hidden=true;setStatus('running');}
  if(stick)scrollToLatest();
}
function scrollToLatest(){const box=$('#timeline');box.scrollTop=box.scrollHeight;}
function showDecision(data){if(!running)return;$('#decision').hidden=false;$('#decision-reason').textContent=data.reason||'当前阶段已结束';$('#decision-score').textContent=`${data.score??0}%`;setStatus('waiting');}
function decide(choice){if(send({type:'decision',decision:choice})){$('#decision').hidden=true;$('#instruct').hidden=true;setStatus('running');}}
function showInstruct(){$('#instruct').hidden=false;$('#instruct-input').focus();}
function sendInstruct(){
  const text=$('#instruct-input').value.trim();if(!text)return;
  if(send({type:'instruction',text})){ $('#instruct-input').value='';decide('continue');addLog({agent:'User',action:'调整方向',detail:text,time:now()}); }
}
function sendFollow(){
  if(running||regenerating)return;
  const text=$('#follow-input').value.trim();if(!text)return;
  if(send({type:'instruction',text})){
    $('#follow-input').value='';$('#followup').hidden=true;$('#decision').hidden=true;
    setRunning(true);setStatus('running');$('#stop-btn').disabled=false;
    $('#report-meta').textContent='上一轮报告 · 正在追加研究';
    renderPlan([{goal:'正在制定追加研究计划',status:'running'}]);addLog({agent:'User',action:'追加研究',detail:text,time:now()});
  }
}
function finishRun(data){
  setRunning(false);$('#decision').hidden=true;$('#instruct').hidden=true;
  currentId=data.id??null;currentReport=data.final_report||'';currentPages=Array.isArray(data.visited_pages)?data.visited_pages:[];
  const status=labels[data.status]?data.status:'error';setStatus(status);
  $('#duration').textContent=formatDuration(data.duration_seconds);
  $('#followup').hidden=!wsReady||['cancelled','error','failed'].includes(status);
  document.querySelectorAll('[data-stage]').forEach(el=>el.classList.remove('active'));
  // Keep the server's actual step states, including unfinished steps.
  if(data.plan_steps)renderPlan(data.plan_steps);
  renderReport(currentReport);
  $('#report-meta').textContent=`${labels[status]} · ${currentPages.length} 个访问页面 · ${formatDuration(data.duration_seconds)}`;
  toast(labels[status]);
}
function renderMarkdown(markdown){
  if(!window.marked||!window.DOMPurify)return `<pre>${esc(markdown)}</pre>`;
  return DOMPurify.sanitize(marked.parse(markdown||''),{FORBID_TAGS:['img','iframe','form','input','button','style']});
}
function renderReport(markdown){
  $('#report').innerHTML=renderMarkdown(markdown);$('#report').hidden=!markdown;$('#report-empty').hidden=!!markdown;$('#report-actions').hidden=!markdown;
  $('#source-list').replaceChildren();
  for(const value of [...new Set(currentPages)]){
    try{const url=new URL(value);if(!['http:','https:'].includes(url.protocol))continue;const a=document.createElement('a');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent=url.hostname+url.pathname;$('#source-list').append(a);}catch(e){}
  }
  $('#sources').hidden=!$('#source-list').children.length;
  $('#report').querySelectorAll('a').forEach(a=>{a.target='_blank';a.rel='noopener noreferrer';});
}
async function regenerateReport(){
  if(!currentId||running||regenerating)return;
  const id=currentId;regenerating=true;$('#regen-btn').disabled=true;$('#regen-btn').classList.add('spinning');$('#run-btn').disabled=true;
  $('#followup').querySelector('button').disabled=true;
  try{const data=await api('/api/report/regenerate',{method:'POST',body:JSON.stringify({task_id:id}),signal:AbortSignal.timeout(180000)});if(currentId===id){currentReport=data.final_report||'';renderReport(currentReport);toast('报告已重新生成');}}
  catch(e){toast(e.message);}finally{regenerating=false;$('#regen-btn').disabled=running;$('#regen-btn').classList.remove('spinning');$('#run-btn').disabled=running;$('#followup').querySelector('button').disabled=false;}
}
async function copyReport(){try{await navigator.clipboard.writeText(currentReport);toast('报告已复制');}catch(e){toast('复制失败，可使用下载按钮');}}
function download(markdown,id){if(!markdown)return;const url=URL.createObjectURL(new Blob([markdown],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`browsermind-report-${id||Date.now()}.md`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function downloadReport(){download(currentReport,currentId);}
function downloadHistoryReport(){download(historyReport?.final_report,historyReport?.id);}
function scheduleHistorySearch(){clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadGallery(0),250);}
async function loadGallery(offset=0){
  const request=++historyRequest;historyOffset=Math.max(0,offset);
  $('#gallery').innerHTML='<div class="history-message">正在读取任务记录</div>';$('#prev-page').disabled=true;$('#next-page').disabled=true;
  const params=new URLSearchParams({limit:20,offset:historyOffset,q:$('#history-search').value.trim(),status:$('#history-status').value,summary:true});
  try{
    const data=await api(`/api/tasks?${params}`);if(request!==historyRequest)return;
    if(!data.tasks.length&&historyOffset>0){loadGallery(Math.max(0,historyOffset-20));return;}
    $('#hist-count').textContent=`${data.total} 条记录`;
    $('#gallery').innerHTML=data.tasks.map(task=>{
      const status=labels[task.status]?task.status:'idle';
      const excerpt=(task.report_excerpt||task.final_report||'暂无报告').replace(/[#>*`]/g,' ').replace(/\s+/g,' ').slice(0,160);
      return `<div class="history-row"><button class="history-open" onclick="openReport(${Number(task.id)})"><span class="history-title">${esc(task.task.split('\n')[0])}</span><span class="history-excerpt">${esc(excerpt)}</span>${task.parent_id?`<small>追问自 #${Number(task.parent_id)}</small>`:''}</button><span class="badge ${status}">${labels[status]}</span><time>${esc((task.created_at||'').slice(0,16).replace('T',' '))}</time><span class="history-duration">${formatDuration(task.duration_seconds)}</span><button class="icon-btn danger-text" title="删除任务" aria-label="删除任务 ${Number(task.id)}" onclick="deleteRecord(${Number(task.id)})"><i data-lucide="trash-2"></i></button></div>`;
    }).join('')||'<div class="history-message">暂无匹配的任务记录</div>';
    $('#page-label').textContent=data.total?`${historyOffset+1} - ${Math.min(historyOffset+20,data.total)} / ${data.total}`:'0 条记录';
    $('#prev-page').disabled=historyOffset===0;$('#next-page').disabled=historyOffset+20>=data.total;icons();
  }catch(e){if(request!==historyRequest)return;$('#gallery').innerHTML=`<div class="history-message">${esc(e.message)}<br><button class="text-btn" onclick="loadGallery(historyOffset)">重新加载</button></div>`;$('#page-label').textContent='';}
}
async function openReport(id){
  try{const data=await api(`/api/tasks/${id}`);historyReport=data;$('#drawer-title').textContent=data.task.split('\n')[0];$('#drawer-meta').textContent=`#${data.id} · ${labels[data.status]||data.status} · ${formatDuration(data.duration_seconds)}`;$('#drawer-report').innerHTML=renderMarkdown(data.final_report||'暂无报告内容');if(!$('#drawer').open)$('#drawer').showModal();}catch(e){toast(e.message);}
}
function closeDrawer(){$('#drawer').close();}
function openConfirm(message,action){confirmAction=action;$('#confirm-msg').textContent=message;$('#confirm-mask').showModal();}
function closeConfirm(){confirmAction=null;$('#confirm-mask').close();}
async function doConfirm(){const action=confirmAction;closeConfirm();try{await action?.();}catch(e){toast(e.message);}}
function deleteRecord(id){openConfirm('删除这条任务及其报告？此操作不可撤销。',async()=>{await api(`/api/tasks/${id}`,{method:'DELETE'});toast('任务已删除');loadGallery(historyOffset);});}
function confirmClearAll(){openConfirm('清空全部任务历史和报告？此操作不可撤销。',async()=>{const data=await api('/api/tasks',{method:'DELETE'});toast(`已删除 ${data.deleted} 条任务`);loadGallery(0);});}
async function refreshConnection(){
  try{
    const health=await api('/api/health');authRequired=health.auth_required;$('#auth-field').hidden=!authRequired;
    keyStatus=await api('/api/settings');$('#model-name').textContent=keyStatus.llm_model||'未配置模型';$('#model-name').title=keyStatus.llm_model||'';
    $('#connection').textContent=health.browser==='ready'?'服务已连接':'浏览器未就绪';$('#connection').classList.toggle('ready',health.browser==='ready');
    $('#apibanner').hidden=!!keyStatus.has_api_key;$('#api-message').textContent='当前模型尚未配置 API Key';return true;
  }catch(e){keyStatus=null;$('#connection').textContent=authRequired?'等待验证':'服务未连接';$('#connection').classList.remove('ready');$('#model-name').textContent='模型未连接';$('#apibanner').hidden=false;$('#api-message').textContent=e.message;return false;}
}
function updateModelOptions(){const provider=$('#set-provider').value;$('#model-options').innerHTML=(presets[provider]?.models||[]).map(model=>`<option value="${esc(model)}"></option>`).join('');$('#key-state').textContent=keyStatus?.providers_with_keys?.includes(provider)?'已配置':'未配置';}
function onProviderChange(){const preset=presets[$('#set-provider').value];$('#set-model').value=preset?.models?.[0]||'';$('#set-base').value=preset?.base_url||'';$('#set-key').value='';updateModelOptions();}
function settingsError(message){$('#settings-error').hidden=!message;$('#settings-error').textContent=message;}
async function openSettings(){
  if(!$('#settings').open)$('#settings').showModal();settingsError('');$('#set-key').value='';$('#set-tavily').value='';$('#set-token').value=authToken;
  $('#save-settings').disabled=true;
  try{
    presets=await api('/api/settings/presets');keyStatus=await api('/api/settings');
    $('#set-provider').value=keyStatus.llm_provider;$('#set-model').value=keyStatus.llm_model;$('#set-base').value=keyStatus.llm_base_url||'';updateModelOptions();
  }catch(e){settingsError(e.message);}finally{$('#save-settings').disabled=false;$('#auth-field').hidden=!authRequired;}
}
function closeSettings(){$('#settings').close();$('#set-key').value='';$('#set-tavily').value='';$('#set-token').value='';}
async function saveSettings(){
  if(running||regenerating){settingsError('研究进行中，结束后可切换模型');return;}
  const body={llm_provider:$('#set-provider').value,llm_model:$('#set-model').value.trim(),llm_base_url:$('#set-base').value.trim()};
  for(const [field,id] of [['llm_api_key','set-key'],['tavily_api_key','set-tavily']]){const value=$(`#${id}`).value.trim();if(value)body[field]=value;}
  $('#save-settings').disabled=true;settingsError('');
  try{await api('/api/settings',{method:'POST',body:JSON.stringify(body)});closeSettings();await refreshConnection();toast('设置已保存');}catch(e){settingsError(e.message);}finally{$('#save-settings').disabled=false;}
}
function resetSettings(){if(running||regenerating){settingsError('研究进行中，结束后可恢复默认');return;}openConfirm('清除界面保存的模型配置，恢复环境配置？',async()=>{await api('/api/settings/reset',{method:'POST'});await refreshConnection();await openSettings();toast('已恢复默认配置');});}
async function connectAuth(){authToken=$('#set-token').value.trim();try{sessionStorage.setItem('bm-auth',authToken);}catch(e){}if(await refreshConnection())await openSettings();else settingsError('访问令牌验证失败');}
function applyTheme(theme){document.documentElement.dataset.theme=theme;$('#theme-btn').innerHTML=`<i data-lucide="${theme==='dark'?'sun':'moon'}"></i>`;$('#theme-btn').setAttribute('aria-pressed',String(theme==='dark'));try{localStorage.setItem('bm-theme',theme);}catch(e){}icons();}
function toggleTheme(){applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');}
for(const dialog of document.querySelectorAll('dialog')){dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});}
$('#settings').addEventListener('close',()=>{$('#set-key').value='';$('#set-tavily').value='';$('#set-token').value='';});
$('#confirm-mask').addEventListener('close',()=>{confirmAction=null;});
$('#task-input').addEventListener('input',taskChanged);
$('#task-input').addEventListener('keydown',event=>{if(!event.isComposing&&(event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();runTask();}});
window.addEventListener('beforeunload',event=>{if(running){event.preventDefault();event.returnValue='';}});
try{$('#task-input').value=localStorage.getItem('bm-draft')||'';}catch(e){}
taskChanged();applyTheme(document.documentElement.dataset.theme);refreshConnection();
