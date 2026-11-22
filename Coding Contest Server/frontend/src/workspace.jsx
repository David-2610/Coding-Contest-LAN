import React,{useState,useEffect,useRef} from 'react';
import {cpp} from '@codemirror/lang-cpp';
import {java} from '@codemirror/lang-java';
import {EditorView,basicSetup} from 'codemirror';
import {python} from '@codemirror/lang-python';
import {get,set} from 'idb-keyval';

export async function api(url,body){
 const token=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1];
 const res=await fetch(url,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':token},body:JSON.stringify(body)});
 if(!res.headers.get('content-type')?.includes('application/json'))throw Error('Session expired. Sign in again.');
 const data=await res.json();if(!res.ok)throw Error(data.error||'Request failed');return data;
}
function Editor({initial,onEdit,lang}){
 const host=useRef(null);
 useEffect(()=>{const editor=new EditorView({doc:initial,parent:host.current,extensions:[basicSetup,({python,cpp,java}[lang])(),EditorView.updateListener.of(update=>{if(update.docChanged)onEdit(update.state.doc.toString())})]});return()=>editor.destroy()},[]);
 return <div className="editor" ref={host}/>;
}
function Problem({w,p,lang,pickLanguage}){
 const key=[w.entry,w.contest,p.id,lang].join('/'),rev=useRef(p.revision),text=useRef(p.source),synced=useRef(p.source),saving=useRef(false),dirty=useRef(false);
 const [initial,init]=useState(null),[saved,saveTests]=useState([]),[sync,syncStatus]=useState('Synced'),[message,msg]=useState(''),[res,result]=useState(null),[busy,setBusy]=useState(false);
 const [history,showHistory]=useState([]);
 function refreshHistory(){api("/api/problems/"+p.id+"/history").then(d=>showHistory(d.submissions)).catch(e=>msg(e.message))}
 useEffect(refreshHistory,[]);
 async function flush(){
  if(saving.current||!dirty.current)return;
  saving.current=true;
  try{while(dirty.current){const value=text.current;dirty.current=false;
    const r=await api('/api/problems/'+p.id+'/draft',{source:value,revision:rev.current,language:lang});rev.current=r.revision;synced.current=value;
    await set(key+'/draft',{source:text.current,rev:rev.current});syncStatus(dirty.current?'Saving…':'Synced');
  }}catch(e){dirty.current=true;syncStatus(e.message)}finally{saving.current=false}
 }
 useEffect(()=>{let live=true;
  Promise.all([get(key+'/draft'),get(key+'/tests')]).then(([draft,tests])=>{if(!live)return;
   const value=draft?.rev>=p.revision?draft.source:p.source;if(draft?.rev>p.revision)rev.current=draft.rev;text.current=value;dirty.current=value!==p.source;init(value);saveTests(tests||[]);
  }).catch(()=>{if(live){init(p.source);syncStatus('Browser storage unavailable')}});
  const timer=setInterval(flush,850);return()=>{live=false;clearInterval(timer);flush()};
 },[]);
 function edit(value){text.current=value;dirty.current=true;syncStatus('Saving…');set(key+'/draft',{source:value,rev:rev.current}).catch(()=>syncStatus('Local draft unavailable'))}
 async function run(kind){
  setBusy(true);result(null);msg('Sending…');
  try{const token=Array.from(crypto.getRandomValues(new Uint8Array(18)),v=>v.toString(16).padStart(2,"0")).join("");const payload={source:text.current,token,tests:saved,language:lang};let response;
   try{response=await api('/api/problems/'+p.id+'/'+kind,payload)}catch(e){if(!(e instanceof TypeError))throw e;response=await api('/api/problems/'+p.id+'/'+kind,payload)}
   for(;;){const job=await api('/api/jobs/'+response.id);if(['done','error'].includes(job.state)){result(job.result);msg('');refreshHistory();break}msg(job.state==='queued'?'Queued':'Judging…');await new Promise(r=>setTimeout(r,450))}
  }catch(e){msg(e.message)}finally{setBusy(false)}
 }
 async function remember(row){
  const item={args:row.args,expected:row.expected};if(saved.some(x=>JSON.stringify(x)===JSON.stringify(item)))return;
  if(saved.length>=12){msg('My Tests holds up to 12 cases.');return}
  const list=[...saved,item];await set(key+'/tests',list);saveTests(list);
 }
 return <><div className="columns"><article className="card"><h1>{p.title}</h1><p>{p.statement}</p>{p.details?.difficulty&&<><p>{p.details.difficulty} · {p.details.topics.join(" / ")}</p><h2>Input and output</h2><p>{p.details.inputFormat}</p><p>{p.details.outputFormat}</p><p>{p.details.constraints.join(" · ")}</p><small>{p.details.execution.timeLimitMs} ms · {p.details.execution.memoryLimitMB} MB</small>{p.details.examples.map((e,i)=><div key={i}><pre>{e.input} → {e.output}</pre>{e.explanation}</div>)}</>}<h2>Examples</h2>{p.samples.map((c,i)=><div className="example" key={i}><code>{JSON.stringify(c.args.length===1?c.args[0]:c.args)}</code><span> → </span><code>{JSON.stringify(c.expected)}</code></div>)}<h2>My Tests <small>{saved.length}</small></h2>{saved.length===0?<p>Save a failed case from your results to rerun it here.</p>:saved.map((v,i)=><div className="example" key={i}><code>{JSON.stringify(v.args)} → {JSON.stringify(v.expected)}</code><button className="link" onClick={async()=>{const list=saved.filter((_,n)=>n!==i);await set(key+'/tests',list);saveTests(list)}}>Remove</button></div>)}</article>
 <section className="card"><div className="bar"><select aria-label="Language" value={lang} onChange={e=>pickLanguage(e.target.value)}><option value="python">Python</option><option value="cpp">C++17</option><option value="java">Java 21</option></select><small role="status">{sync}</small></div>{initial!==null&&<Editor lang={lang} initial={initial} onEdit={edit}/>}<div className="actions"><button className="secondary" disabled={busy||initial===null} onClick={()=>run('run')}>Run tests</button><button disabled={busy||initial===null} onClick={()=>run('submit')}>Submit solution</button></div></section></div>
 <section className="card result" aria-live="polite"><h2>Results</h2>{message||(!res&&'Run the examples or submit against the official suite.')}{res&&<><p><strong>{res.verdict}</strong>{res.total!=null&&' · '+res.passed+' / '+res.total+' passed'}</p>{res.skipped>0&&<p>{res.skipped} {res.skipped===1?'test':'tests'} skipped</p>}{res.diagnostic&&<pre>{res.diagnostic}</pre>}{res.cases.map(row=><div className="case" key={row.number}><b>Case {row.number}</b> {row.status}{row.status!=='Passed'&&row.args&&<><pre>{'Arguments: '+JSON.stringify(row.args)+'\nExpected: '+JSON.stringify(row.expected)+'\nActual: '+JSON.stringify(row.actual)}</pre><button className="secondary" onClick={()=>remember(row)}>Add to My Tests</button></>}</div>)}</>}</section><section className="card result"><h2>Official submissions</h2>{history.length===0?<p>No submissions yet.</p>:history.map(j=><div className="bar" key={j.id}><span>{new Date(j.received).toLocaleTimeString()} · {j.status}</span><button className="link" onClick={async()=>{try{const v=await api('/api/jobs/'+j.id);result(v.result);msg(v.result?'':v.state)}catch(e){msg(e.message)}}}>View result</button></div>)}</section></>
}
export function Workspace({cid}){
 const [w,load]=useState(null),[pid,choose]=useState(null),[error,fail]=useState(''),[lang,pick]=useState('python');
 useEffect(()=>{api('/api/workspace?contest='+cid).then(v=>{load(v);choose(v.problems[0]?.id)}).catch(e=>fail(e.message))},[cid]);
 const [topic,filter]=useState("");
 const [decision,record]=useState(null);
 const ready=Boolean(w);
 useEffect(()=>{if(!ready)return;let live=true,timer;
 async function ping(){try{const d=await api('/api/contests/'+cid+'/heartbeat',{});if(live)record(d)}catch{}finally{if(live)timer=setTimeout(ping,9000+Math.random()*2000)}}
 timer=setTimeout(ping,Math.random()*10000);return()=>{live=false;clearTimeout(timer)}},[cid,ready]);
 if(!w)return <p role="status">{error||'Opening workspace…'}</p>;
 const status=decision||w;
 if(status.eligible===false)return <section role="alert" style={{background:'#751a25',color:'white',padding:32}}><h1>Disqualified from CodeClash 1.0</h1><p>{status.reason}</p><p>Submissions are closed for your account. Contact the organizer for review.</p></section>;
 const p=w.problems.find(x=>x.id===pid);
 return <><div className="page-heading"><div><h1>{w.title}</h1><p>{w.name} · {w.enrollment}</p></div><a href={'/leaderboard/'+cid+'/'}>Leaderboard ↗</a></div><div className="bar"><select aria-label="Topic" value={topic} onChange={e=>{filter(e.target.value);choose(w.problems.find(x=>!e.target.value||x.details?.topics?.includes(e.target.value))?.id)}}><option value="">All topics</option>{[...new Set(w.problems.flatMap(x=>x.details?.topics||[]))].sort().map(t=><option key={t}>{t}</option>)}</select><select aria-label="Problem" value={pid||''} onChange={e=>choose(Number(e.target.value))}>{w.problems.filter(x=>!topic||x.details?.topics?.includes(topic)).map(x=><option key={x.id} value={x.id}>{x.title}</option>)}</select><small>Ends {new Date(w.ends).toLocaleString()}</small></div>{p?<Problem key={p.id+'/'+lang} w={w} p={{...p,...p.languages[lang]}} lang={lang} pickLanguage={pick}/>:<p>No published problems yet.</p>}</>
}
