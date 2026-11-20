"use strict";
let state = null;
let view = 'pipeline';
let selected = null;
let lastSignature = '';
let toastTimer;
const content = document.getElementById('content');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label = value => String(value || '').replaceAll('_',' ');
const date = value => new Date(value * 1000).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const roleName = role => ({research:'Research',sales:'Sales',evaluator:'Evaluator',orchestrator:'Orchestrator'}[role] || role);
const badge = (text, style='') => `<span class="badge ${style}">${esc(text)}</span>`;
const taskFor = id => state.tasks.find(t => t.account_id === id && ['queued','running'].includes(t.status));
const head = (title, subtitle, action='') => `<div class="page-head"><div><div class="eyebrow">GTM OPERATIONS</div><h1>${title}</h1><p class="subtitle">${subtitle}</p></div>${action}</div>`;
const empty = (title, text) => `<div class="empty"><h2>${title}</h2><p>${text}</p></div>`;

function toast(message, error=false) {
  const el=document.getElementById('toast'); el.textContent=message; el.classList.toggle('error',error);el.hidden=false;
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.hidden=true,error?9000:4500);
}

async function api(path, data) {
  const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-GTM-Token':state.runtime.csrf_token},body:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw new Error(result.error || 'Request failed.');return result;
}

async function refresh(force=false) {
  try {
    const response=await fetch('/api/state');if(!response.ok)throw new Error('Unable to load the workspace.');
    const next=await response.json();const signature=JSON.stringify(next);
    state=next;
    if (!selected || !state.accounts.some(a=>a.id===selected))selected=state.accounts[0]?.id;
    renderChrome();
    const editing=content.contains(document.activeElement) && document.activeElement.closest('form');
    if(force || (signature!==lastSignature && !editing)){render();lastSignature=signature;}
  } catch(error) {if(!state)content.innerHTML=empty('Workspace unavailable',esc(error.message));}
}

function renderChrome() {
  document.getElementById('workspace-banner').innerHTML=state.demo
    ? '<strong>DEMO WORKSPACE</strong><span>Fictional accounts · Scripted agent responses · No API calls or outreach</span>'
    : `<strong>LOCAL WORKSPACE · SHADOW MODE</strong><span>${state.runtime.provider==='codex'?'Codex mode · Queue here, then ask Codex to run the team':state.runtime.ready?'Model configured · API access verified when a run succeeds':'Model not configured · Add credentials to run agents'} · No outreach</span>`;
  document.getElementById('pause-button').textContent=state.config.paused?'Resume team':'Pause team';
  document.querySelectorAll('[data-view]').forEach(el=>{el.classList.toggle('active',el.dataset.view===view);el.setAttribute('aria-current',el.dataset.view===view?'page':'false');});
}

function render() {
  content.innerHTML=({pipeline:renderPipeline,strategy:renderStrategy,learning:renderLearning,activity:renderActivity,settings:renderSettings}[view])();
}

function stats() {
  const active=state.tasks.filter(t=>['queued','running'].includes(t.status)).length;
  return `<div class="stats">${[
    ['Accounts',state.accounts.length,'In this workspace'],
    ['Evidence records',state.evidence.length,'Sources and observations'],
    ['Drafts to review',state.drafts.filter(d=>d.status==='needs_review').length,'Nothing has been sent'],
    ['Active tasks',active,state.config.paused?'Team paused':'Bounded, accountable work']
  ].map(([name,value,note])=>`<div class="stat"><div class="stat-top">${name}</div><div class="stat-value">${value}</div><div class="stat-note">${note}</div></div>`).join('')}</div>`;
}

function renderPipeline() {
  const account=state.accounts.find(a=>a.id===selected);
  return head('Pipeline','Turn account evidence into the next right conversation.','<button class="button" data-action="add-account">＋ Add account</button>')+stats()+
    (!state.config.segment?`<div class="panel spaced"><div class="panel-head"><span>Choose a target segment for drafts and strategy. Company research is available before that.</span><button class="button small secondary" data-view="settings">Business setup</button></div></div><br>`:'')+
    `<div class="pipeline-layout"><div><section class="panel"><div class="panel-head"><h2>Account workspace</h2><small>${state.accounts.length} accounts</small></div>${state.accounts.map(a=>`<button class="account-row ${a.id===selected?'selected':''}" data-account="${a.id}" aria-pressed="${a.id===selected}"><span class="company-mark">${esc(a.name.slice(0,2).toUpperCase())}</span><span class="account-info"><strong>${esc(a.name)}</strong><small>${esc(a.segment || 'Segment unassigned')}</small></span>${badge(a.suppressed?'Suppressed':taskFor(a.id)?'Working':label(a.stage),a.suppressed?'warn':a.stage==='drafted'?'green':'')}<span class="account-arrow" aria-hidden="true">›</span></button>`).join('') || empty('Your pipeline starts here','Add a company and the evidence that makes it relevant.')} </section><section class="panel spaced"><div class="panel-head"><h2>Recent tasks</h2><small>Durable queue</small></div><div class="side-note">${state.tasks.slice(0,5).map(t=>`<div class="task-item"><div><p>${esc(label(t.kind))}</p>${t.error?`<div class="task-error">${esc(t.error)}</div>`:''}</div>${badge(label(t.status),t.status==='failed'?'warn':'')}</div>`).join('') || '<p>No tasks yet. Select an account to start its review.</p>'}</div></section></div><section class="panel">${account?accountDetail(account):empty('Select an account','Research, drafts, and evidence stay together in one history.')}</section></div>`+teamStrip();
}

function accountDetail(a) {
  const evidence=state.evidence.filter(e=>e.account_id===a.id);
  const draft=state.drafts.find(d=>d.account_id===a.id);
  const task=taskFor(a.id);
  const runs=state.agent_runs.filter(r=>r.task_id===(draft?.task_id || task?.id));
  const evaluator=runs.find(r=>r.role==='evaluator');
  const stale=draft && (draft.account_version!==a.version || draft.config_version!==state.config.version);
  return `<div class="detail-header"><div class="detail-title"><span class="company-mark">${esc(a.name.slice(0,2).toUpperCase())}</span><div><h2>${esc(a.name)}</h2><small>${esc(a.domain)} · ${a.is_demo?'Fictional account':'Local record'}</small></div></div>${badge('Owner: '+a.owner)}</div><div class="workflow"><div class="workflow-step done"><span class="step-number">01</span>Evidence</div><div class="workflow-step ${draft?'done':''}"><span class="step-number">02</span>Draft</div><div class="workflow-step"><span class="step-number">03</span>Review</div></div><div class="detail-section"><div class="section-label"><span>ACCOUNT EVIDENCE</span><button class="text-button" data-action="add-evidence">＋ Add source</button></div>${evidence.slice(0,6).map(e=>`<div class="evidence-item"><p>${esc(e.claim)}</p><div class="source">${esc(label(e.kind))} · ${esc(e.source)}<br>${esc(e.id)}</div></div>`).join('')}<div class="detail-actions"><button class="button small" data-action="review" ${a.suppressed||task||state.config.paused?'disabled':''}>${task?'Account work in progress…':draft?'Run new review':'Run account review'}</button>${!a.suppressed?'<button class="button small danger" data-action="suppress">Suppress account</button>':badge('Suppressed','warn')}</div><p class="hint spaced">${state.demo?'Scripted demo: research → draft → evaluation.':state.runtime.provider==='codex'?'Separate Codex agents: research → draft → evaluation. Queue a task here, then ask Codex to execute it.':'Three bounded model calls: research → draft → evaluation. Reviews use accepted account evidence. Run public research below to propose new findings.'}</p></div>${researchDetail(a)}<div class="detail-section"><div class="section-label"><span>LATEST OUTREACH DRAFT</span>${draft?badge(stale?'Inputs changed':label(draft.status),stale||draft.status==='blocked'?'warn':''):''}</div>${draft?`<div class="draft-body">${esc(draft.body)}</div><div class="detail-actions"><button class="button secondary small" data-action="check-draft" data-id="${draft.id}">Check action readiness</button></div><p class="source">Sources: ${esc(draft.evidence_ids.join(', '))}</p>`:'<p class="hint">The sales agent will prepare a draft after reviewing the account evidence. All drafts remain local.</p>'}</div>${evaluator?`<div class="detail-section"><div class="section-label">EVALUATOR NOTES</div><p class="draft-body">${esc(evaluator.output.content)}</p></div>`:''}`;
}

function sourceLink(source) {
  try {
    const url=new URL(source.url);
    if(!['https:','http:'].includes(url.protocol))return esc(source.title);
    return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${esc(source.title || source.url)}</a>`;
  } catch {return esc(source.title || 'Unsupported URL');}
}

function citedReport(report) {
  let cursor=0;let output='';
  const chars=Array.from(report.content);
  const sources=new Map(report.sources.map(s=>[s.id,s]));
  for(const citation of [...report.citations].sort((a,b)=>a.start-b.start)) {
    if(citation.start<cursor || citation.end>chars.length)continue;
    output+=esc(chars.slice(cursor,citation.start).join(''));
    const source=sources.get(citation.source_id);
    output+=source?sourceLink({...source,title:chars.slice(citation.start,citation.end).join('')}):esc(chars.slice(citation.start,citation.end).join(''));
    cursor=citation.end;
  }
  return output+esc(chars.slice(cursor).join(''));
}

function researchDetail(a) {
  const task=state.tasks.find(t=>t.account_id===a.id && t.kind==='account_research');
  const runs=state.agent_runs.filter(r=>r.task_id===task?.id);
  const report=runs.find(r=>r.role==='research_search')?.output;
  const extracted=runs.find(r=>r.role==='research_extract')?.output;
  const evaluator=runs.find(r=>r.role==='evaluator')?.output;
  const findings=state.research_findings.filter(f=>f.task_id===task?.id);
  const disabled=state.demo || !state.runtime.ready || a.suppressed || taskFor(a.id) || state.config.paused;
  return `<div class="detail-section"><div class="section-label"><span>PUBLIC RESEARCH</span>${task?badge(label(task.status)):''}</div>
    <form id="research-form"><label>Public research focus<textarea name="question" required maxlength="2000" rows="3">Confirm the company identity, operational workflows and current software. Find a specific workflow hypothesis relevant to the configured offer and list what still needs customer validation.</textarea></label>
    <button class="button small secondary" type="submit" ${disabled?'disabled':''}>Research company</button></form>
    <p class="hint spaced">${state.demo?'Open the real workspace to research public companies.':state.runtime.provider==='codex'?'Separate Codex agents collect sources, extract findings and evaluate them. Queued tasks wait for Codex; no API key is needed. Only the company identity and public focus go to the collector.':'Up to 3 model requests and 3 web tool calls. Only company name, domain and this focus go to the search stage. Keep private details out of the focus.'}</p>
    ${task?.error?`<p class="task-error">${esc(task.error)}</p>`:''}
    ${report?`<details class="spaced"><summary>Search report and ${report.sources.length} sources</summary><div class="draft-body">${citedReport(report)}</div><ul>${report.sources.map(s=>`<li>${sourceLink(s)}<div class="source">${s.cited?'Cited':'Consulted'} · Collected ${date(s.retrieved_at)}</div></li>`).join('')}</ul></details>`:''}
    ${extracted?`<p class="spaced">${esc(extracted.summary)}</p><ul class="hint">${extracted.uncertainties.map(u=>`<li>${esc(u)}</li>`).join('')}</ul>`:''}
    ${evaluator?`<details class="spaced"><summary>Evaluator review · ${esc(label(evaluator.recommendation))}</summary><p class="draft-body">${esc(evaluator.content)}</p></details>`:''}
    ${findings.map(f=>`<div class="evidence-item">${badge(label(f.kind))} ${badge(label(f.status),f.status==='blocked'?'warn':'')}<p>${esc(f.claim)}</p><div class="source">Source date: ${esc(f.source_date)} · ${(report?.sources || []).filter(s=>f.source_ids.includes(s.id)).map(sourceLink).join(' · ')}</div>${f.status==='pending'?`<div class="detail-actions"><button class="button secondary small" data-action="accept-finding" data-id="${f.id}" ${a.suppressed||state.config.paused?'disabled':''}>Accept into evidence</button><button class="text-button" data-action="reject-finding" data-id="${f.id}" ${a.suppressed?'disabled':''}>Reject</button></div>`:''}</div>`).join('')}
    ${findings.length?'<p class="hint spaced">Accept after checking the linked source. Acceptance preserves the observation or hypothesis label and invalidates older drafts; it does not prove a sales opportunity.</p>':''}</div>`;
}

function teamStrip() {
  return `<div class="team-strip">${[['O','Orchestrator','Coordinates the work'],['R','Research','Checks account evidence'],['S','Sales','Prepares conversations'],['E','Evaluator','Challenges assumptions']].map(([initial,name,desc])=>`<div class="agent-chip"><span class="agent-avatar">${initial}</span><div><strong>${name}</strong><small>${desc}</small></div></div>`).join('')}</div>`;
}

function renderStrategy() {
  const active=state.tasks.some(t=>t.kind==='strategy' && ['queued','running'].includes(t.status));
  return head('Strategy room','Independent proposals. Useful disagreements. A decision you can inspect.')+
    `<div class="strategy-layout"><div class="stack"><section class="panel"><form id="strategy-form" class="settings-form"><label>What should the team work out?<textarea name="question" rows="2" required maxlength="2000" placeholder="e.g. Which workflow should our first message focus on?"></textarea></label><div class="form-actions"><span class="hint">${state.demo?'Scripted demonstration':state.runtime.provider==='codex'?'Four separate Codex agents':'Four bounded model calls'} · No automatic execution</span><button class="button" type="submit" ${active||state.config.paused?'disabled':''}>${active?'Discussion in progress…':'Start discussion'}</button></div></form></section>${state.discussions.map(d=>renderDiscussion(d)).join('') || `<section class="panel">${empty('Give the team a question','Research and Sales propose independently. The Evaluator challenges both. The Orchestrator records a decision.')}</section>`}</div><aside class="panel side-note"><h3>How the room works</h3><ol><li>Research proposes from evidence.</li><li>Sales offers an independent view.</li><li>Evaluator challenges assumptions.</li><li>Orchestrator decides what to test.</li></ol><p class="spaced">Agreement is a hypothesis. Customer outcomes validate a strategy.</p><div class="connection-row spaced">Discussion limit <span>4 role turns</span></div><div class="connection-row">Playbook promotion <span>Not enabled</span></div></aside></div>`;
}

function renderDiscussion(d) {
  const runs=state.agent_runs.filter(r=>r.task_id===d.task_id).sort((a,b)=>a.created_at-b.created_at);
  const experiment=state.experiments.find(e=>e.discussion_id===d.id);
  return `<section class="panel discussion"><div class="discussion-top"><div><h2>${esc(d.question)}</h2><p class="hint">${date(d.created_at)} · ${state.demo?'Scripted demo':runs.some(r=>r.provider==='codex')?'Separate Codex agent executions':'Model-assisted discussion'}</p></div>${badge(label(d.recommendation),'green')}</div>${runs.filter(r=>r.role!=='orchestrator').map(r=>`<div class="turn"><span class="agent-avatar">${r.role[0].toUpperCase()}</span><div><div class="turn-meta"><strong>${roleName(r.role)}</strong><small>${r.role==='evaluator'?'Challenge round':'Independent proposal'}${r.provider==='codex'?' · Codex':''}</small></div><p>${esc(r.output.content)}</p><div class="source">Evidence: ${esc(r.output.evidence_ids.join(', '))}</div></div></div>`).join('')}<div class="decision"><strong>ORCHESTRATOR DECISION</strong><p>${esc(d.decision)}</p>${d.recommendation==='test'?`<button class="button small secondary" data-action="experiment" data-id="${d.id}" ${experiment?'disabled':''}>${experiment?'Experiment brief saved':'Create experiment brief'}</button>`:''}</div></section>`;
}

function renderLearning() {
  return head('Learning','Keep hypotheses separate from proven playbooks.')+`<div class="strategy-layout"><div class="stack">${state.experiments.map(e=>`<section class="panel experiment">${badge('Draft experiment','warn')}<h2>${esc(e.title)}</h2><p>${esc(e.hypothesis)}</p><div class="experiment-meta"><div><small>PRIMARY METRIC</small><strong>${esc(e.primary_metric)}</strong></div><div><small>LIVE ASSIGNMENTS</small><strong>Not started</strong></div></div><p class="hint spaced">Before launch: define the audience, baseline, changed variable, allocation, observation window, budget, and decision rules. Live enrollment and statistical evaluation are not implemented yet.</p></section>`).join('') || `<section class="panel">${empty('Start with a testable idea','Open a strategy discussion, then save its proposed experiment here. No playbook has been promoted.')}</section>`}</div><aside class="panel side-note"><h3>Evidence before change</h3><ol><li>Observe a pattern.</li><li>Write a falsifiable hypothesis.</li><li>Compare against a baseline.</li><li>Wait for mature outcomes.</li><li>Adopt, reject, or stay inconclusive.</li></ol><p class="spaced">This first release stores experiment briefs. It does not fabricate conversion data or claim strategy improvements.</p></aside></div>`;
}

function renderActivity() {
  return head('Activity','A durable record of tasks, decisions, and interventions.')+`<section class="panel"><div class="table-wrap"><table><thead><tr><th>EVENT</th><th>CONTEXT</th><th>TIME</th></tr></thead><tbody>${state.events.map(e=>{const account=state.accounts.find(a=>a.id===e.account_id);return `<tr><td>${esc(e.kind)}</td><td>${account?esc(account.name)+'<br>':''}<span class="hint">${esc(eventSummary(e))}</span></td><td><time>${date(e.created_at)}</time></td></tr>`;}).join('') || '<tr><td colspan="3">No recorded activity yet.</td></tr>'}</tbody></table></div></section>`;
}

function eventSummary(e) {
  const d=e.detail;
  if(d.reason)return d.reason;
  if(d.role)return `${roleName(d.role)} · ${d.provider || 'Codex'}${d.usage?.execution==='codex'?' · Agent '+d.usage.agent_id+' · usage unavailable':d.usage?' · '+(d.usage.input_tokens+d.usage.output_tokens)+' tokens':''}`;
  if(d.reasons)return d.reasons.join(' ');
  if(d.kind)return label(d.kind);
  if(d.name)return d.name;
  if(d.version)return `Configuration version ${d.version}`;
  return Object.entries(d).map(([k,v])=>`${label(k)}: ${v}`).join(' · ') || 'Recorded in this workspace';
}

function renderSettings() {
  const c=state.config;
  return head('Business setup','Give the team a clear offer, audience, and source of truth.')+`<div class="settings-layout"><section class="panel"><form id="settings-form" class="settings-form" data-version="${c.version}"><label>Business name<input name="business_name" required maxlength="3000" value="${esc(c.business_name)}"></label><label>Offer<textarea name="offer" required maxlength="3000" rows="3">${esc(c.offer)}</textarea></label><label>Target customer segment<textarea name="segment" required maxlength="3000" rows="2" placeholder="Industry, geography, operational workflow, and buyer.">${esc(c.segment)}</textarea></label><label>Approved factual claims <span class="hint">· one per line</span><textarea name="approved_claims" required rows="4">${esc(c.approved_claims.join('\n'))}</textarea></label><label>Qualification rubric<textarea name="qualification_rubric" rows="3" maxlength="5000" placeholder="What evidence makes an opportunity qualified?">${esc(c.qualification_rubric)}</textarea></label><div class="form-actions"><span class="hint">Version ${c.version} · Changes invalidate older task inputs.</span><button class="button" type="submit">Save configuration</button></div></form></section><div class="stack"><section class="panel side-note"><h3>Your operating setup</h3><div class="connection-row">CRM <span>Built-in account workspace</span></div><div class="connection-row">Model <span>${esc(state.runtime.model || 'Not configured')}</span></div><div class="connection-row">Provider <span>${state.demo?'Scripted demo':esc(state.runtime.provider)}</span></div><div class="connection-row">Outreach <span>Unavailable</span></div><div class="connection-row">Email review <span>Required</span></div><div class="connection-row">Data <span>Local SQLite</span></div></section><section class="panel side-note"><h3>Agent execution</h3><p>Default: <code>python3 -m gtm_agents serve --executor codex</code>. Queue work here, then ask Codex to run pending GTM tasks. Separate agent sessions save outputs into this workspace. Codex usage limits apply; there is no automatic background dispatcher.</p><p class="spaced">For the optional API worker, use <code>--executor api</code>.</p><p>In your terminal, set <code>OPENAI_API_KEY</code> and <code>GTM_MODEL</code>, then start without <code>--demo</code>. Or use <code>--env-file .env</code>. Run <code>python3 -m gtm_agents doctor --env-file .env --live</code> to verify access with one small paid request. Credentials stay on the server.</p><p class="spaced">Account reviews use up to 3 calls; strategy discussions use 4. Research uses up to 3 model requests and 3 web tool calls. Only the selected evidence packet and configured business context are sent to the model when you run a task.</p></section></div></div>`;
}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.view){view=button.dataset.view;renderChrome();render();return;}
  if(button.dataset.account){selected=button.dataset.account;render();return;}
  if(button.dataset.close){document.getElementById(button.dataset.close).close();return;}
  if(button.dataset.action==='add-account'){document.getElementById('account-dialog').showModal();return;}
  if(button.dataset.action==='add-evidence'){document.getElementById('evidence-dialog').showModal();return;}
  if(button.id==='pause-button'){
    try{await api('pause',{paused:!state.config.paused});await refresh(true);}catch(e){toast(e.message,true);}return;
  }
  const action=button.dataset.action;if(!action)return;
  button.disabled=true;
  try {
    if(action==='review'){await api('tasks',{kind:'account_review',account_id:selected,request_key:crypto.randomUUID()});toast('Account review queued.');}
    if(action==='accept-finding' || action==='reject-finding'){await api('research-findings',{finding_id:button.dataset.id,decision:action==='accept-finding'?'accepted':'rejected'});toast('Finding reviewed.');}
    if(action==='suppress'){await api('suppress',{account_id:selected});toast('Account suppressed. Pending work was canceled.');}
    if(action==='experiment'){await api('experiments',{discussion_id:button.dataset.id});toast('Experiment brief saved to Learning.');}
    if(action==='check-draft'){
      const result=await api('check-draft',{draft_id:button.dataset.id});
      document.getElementById('policy-result').innerHTML=badge('Not eligible for sending','warn')+`<ul class="error-list">${result.reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`;
      document.getElementById('policy-dialog').showModal();
    }
    await refresh(true);
  }catch(error){toast(error.message,true);}finally{button.disabled=false;}
});

document.addEventListener('submit',async event=>{
  const form=event.target;if(!['account-form','evidence-form','strategy-form','settings-form','research-form'].includes(form.id))return;
  event.preventDefault();const button=form.querySelector('button[type="submit"]');button.disabled=true;
  const data=Object.fromEntries(new FormData(form));
  try {
    if(form.id==='account-form'){const result=await api('accounts',data);selected=result.id;document.getElementById('account-dialog').close();form.reset();toast('Account added with its first evidence record.');}
    if(form.id==='evidence-form'){await api('evidence',{...data,account_id:selected});document.getElementById('evidence-dialog').close();form.reset();toast('Evidence saved. Older drafts may need a new review.');}
    if(form.id==='research-form'){await api('tasks',{kind:'account_research',account_id:selected,question:data.question,request_key:crypto.randomUUID()});toast('Public research queued.');}
    if(form.id==='strategy-form'){await api('tasks',{kind:'strategy',question:data.question,request_key:crypto.randomUUID()});form.reset();toast('Strategy discussion queued.');}
    if(form.id==='settings-form'){await api('config',{...data,approved_claims:data.approved_claims.split('\n').map(s=>s.trim()).filter(Boolean),version:Number(form.dataset.version)});toast('Business configuration saved.');}
    await refresh(true);
  }catch(error){toast(error.message,true);}finally{button.disabled=false;}
});

refresh(true);
setInterval(()=>refresh(),2000);
