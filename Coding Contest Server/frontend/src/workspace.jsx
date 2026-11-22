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
 useEffect(()=>{
   const editor=new EditorView({
     doc:initial,
     parent:host.current,
     extensions:[
       basicSetup,
       ({python,cpp,java}[lang])(),
       EditorView.theme({
         "&": {height: "100%", fontSize: "14px", backgroundColor: "#ffffff", color: "#1f2937"},
         ".cm-scroller": {overflow: "auto", fontFamily: "'JetBrains Mono', Consolas, monospace"},
         ".cm-gutters": {backgroundColor: "#f9fafb", color: "#9ca3af", borderRight: "1px solid #e5e7eb"}
       }, {dark: false}),
       EditorView.updateListener.of(update=>{if(update.docChanged)onEdit(update.state.doc.toString())})
     ]
   });
   return()=>editor.destroy();
 },[lang]);
 return <div className="lc-editor-wrapper" ref={host}/>;
}

function ProblemView({w,p,lang,pickLanguage}){
 const key=[w.entry,w.contest,p.id,lang].join('/'),rev=useRef(p.revision),text=useRef(p.source),synced=useRef(p.source),saving=useRef(false),dirty=useRef(false);
 const [initial,init]=useState(null),[sync,syncStatus]=useState('Saved'),[message,msg]=useState(''),[res,result]=useState(null),[busy,setBusy]=useState(false);
 const [history,showHistory]=useState([]),[descTab,setDescTab]=useState('Description'),[consoleTab,setConsoleTab]=useState('Testcase'),[activeCase,setActiveCase]=useState(0);
 const [customCases, setCustomCases] = useState(() => (p.samples && p.samples.length > 0) ? JSON.parse(JSON.stringify(p.samples)) : [{args: p.signature?.params ? p.signature.params.map(()=>0) : [0], expected: 0, sample: true}]);

 function refreshHistory(){api("/api/problems/"+p.id+"/history").then(d=>showHistory(d.submissions||[])).catch(e=>msg(e.message))}
 useEffect(refreshHistory,[]);

 async function flush(){
  if(saving.current||!dirty.current)return;
  saving.current=true;
  try{while(dirty.current){const value=text.current;dirty.current=false;
    const r=await api('/api/problems/'+p.id+'/draft',{source:value,revision:rev.current,language:lang});rev.current=r.revision;synced.current=value;
    await set(key+'/draft',{source:text.current,rev:rev.current});syncStatus(dirty.current?'Saving…':'Saved');
  }}catch(e){dirty.current=true;syncStatus(e.message)}finally{saving.current=false}
 }

 useEffect(()=>{let live=true;
  get(key+'/draft').then(draft=>{if(!live)return;
   const value=draft?.rev>=p.revision?draft.source:p.source;if(draft?.rev>p.revision)rev.current=draft.rev;text.current=value;dirty.current=value!==p.source;init(value);
  }).catch(()=>{if(live){init(p.source);syncStatus('Saved')}});
  const timer=setInterval(flush,850);return()=>{live=false;clearInterval(timer);flush()};
 },[p.id,lang]);

 function edit(value){text.current=value;dirty.current=true;syncStatus('Saving…');set(key+'/draft',{source:value,rev:rev.current}).catch(()=>{})}

 async function run(kind){
  setBusy(true);result(null);msg('Pending…');setConsoleTab('Result');
  try{const token=Array.from(crypto.getRandomValues(new Uint8Array(18)),v=>v.toString(16).padStart(2,"0")).join("");
   const payload={source:text.current,token,language:lang,tests:kind==='run'?customCases:undefined};let response;
   response=await api('/api/problems/'+p.id+'/'+kind,payload);
   for(;;){const job=await api('/api/jobs/'+response.id);if(['done','error'].includes(job.state)){result(job.result);msg('');refreshHistory();break}msg(job.state==='queued'?'Queued…':'Judging…');await new Promise(r=>setTimeout(r,450))}
  }catch(e){msg(e.message)}finally{setBusy(false)}
 }

 const samples = p.samples || [];
 const details = p.details || {};

 return <div className="lc-main">
  {/* Left Panel: Problem Statement / Submissions */}
  <div className="lc-panel">
   <div className="lc-panel-tabs">
    <button className={'lc-tab '+(descTab==='Description'?'active':'')} onClick={()=>setDescTab('Description')}>📄 Description</button>
    <button className={'lc-tab '+(descTab==='Submissions'?'active':'')} onClick={()=>setDescTab('Submissions')}>🕒 Submissions ({history.length})</button>
   </div>
   <div className="lc-panel-content">
    {descTab==='Description' ? (
     <div>
      <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'12px'}}>
       <h1 style={{fontSize:'1.35rem',fontWeight:700,margin:0}}>{p.external_id ? `${p.external_id}. ` : ''}{p.title}</h1>
       {details.difficulty&&<span className={'lc-difficulty '+details.difficulty}>{details.difficulty}</span>}
      </div>

      {details.topics&&details.topics.length>0&&(
       <div style={{marginBottom:'16px'}}>
        {details.topics.map(t=><span key={t} className="lc-tag">{t}</span>)}
       </div>
      )}

      <div style={{fontSize:'0.95rem',lineHeight:1.7,color:'#262626',whiteSpace:'pre-line',marginBottom:'20px'}}>
       {p.statement}
      </div>

      {/* Examples in LeetCode Box Style */}
      {details.examples && details.examples.length>0 ? (
       <div>
        <h3 style={{fontSize:'1rem',color:'#111827',margin:'16px 0 8px 0'}}>Examples</h3>
        {details.examples.map((ex,idx)=>(
         <div key={idx} className="lc-example-box">
          <div><strong style={{color:'#9ca3af'}}>Example {idx+1}:</strong></div>
          <div style={{marginTop:'4px'}}><strong>Input:</strong> <code>{ex.input}</code></div>
          <div><strong>Output:</strong> <code>{ex.output}</code></div>
          {ex.explanation&&<div style={{color:'#9ca3af',marginTop:'4px'}}><strong>Explanation:</strong> {ex.explanation}</div>}
         </div>
        ))}
       </div>
      ) : samples.length>0 ? (
       <div>
        <h3 style={{fontSize:'1rem',color:'#111827',margin:'16px 0 8px 0'}}>Example Testcases</h3>
        {samples.map((c,idx)=>(
         <div key={idx} className="lc-example-box">
          <div><strong style={{color:'#9ca3af'}}>Example {idx+1}:</strong></div>
          <div><strong>Input:</strong> <code>{JSON.stringify(c.args.length===1?c.args[0]:c.args)}</code></div>
          <div><strong>Output:</strong> <code>{JSON.stringify(c.expected)}</code></div>
         </div>
        ))}
       </div>
      ) : null}

      {/* Constraints */}
      {details.constraints && details.constraints.length>0 && (
       <div style={{marginTop:'20px'}}>
        <h3 style={{fontSize:'1rem',color:'#111827',marginBottom:'8px'}}>Constraints:</h3>
        <ul style={{paddingLeft:'20px',color:'#374151',lineHeight:1.8}}>
         {details.constraints.map((c,idx)=><li key={idx}><code>{c}</code></li>)}
        </ul>
       </div>
      )}
     </div>
    ) : (
     <div>
      <h3 style={{fontSize:'1.1rem',color:'#111827',margin:'0 0 14px 0'}}>Submissions History</h3>
      {history.length===0?<p style={{color:'#9ca3af'}}>No submissions recorded yet for this question.</p>:(
       <table style={{width:'100%',borderCollapse:'collapse',fontSize:'0.9rem'}}>
        <thead>
         <tr style={{borderBottom:'1px solid #e5e7eb',color:'#9ca3af',textAlign:'left'}}>
          <th style={{padding:'8px'}}>Time</th>
          <th style={{padding:'8px'}}>Status</th>
          <th style={{padding:'8px'}}>Action</th>
         </tr>
        </thead>
        <tbody>
         {history.map(j=>(
          <tr key={j.id} style={{borderBottom:'1px solid #f3f4f6'}}>
           <td style={{padding:'10px 8px',color:'#9ca3af'}}>{new Date(j.received).toLocaleTimeString()}</td>
           <td style={{padding:'10px 8px'}}>
            <span style={{fontWeight:600,color:j.status==='Accepted'?'#2cbb5d':j.status==='Passed'?'#2cbb5d':'#ef4444'}}>
             {j.status}
            </span>
           </td>
           <td style={{padding:'10px 8px'}}>
            <button className="lc-btn-run" style={{padding:'3px 10px',fontSize:'0.75rem'}} onClick={async()=>{
              try{
                const v=await api('/api/jobs/'+j.id);
                result(v.result);
                setConsoleTab('Result');
              }catch(e){msg(e.message)}
            }}>Inspect</button>
           </td>
          </tr>
         ))}
        </tbody>
       </table>
      )}
     </div>
    )}
   </div>
  </div>

  {/* Right Panel: Code Editor + Console & Results */}
  <div className="lc-right-pane">
   <div className="lc-editor-card">
    <div className="lc-editor-toolbar">
     <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
      <select className="lc-select" value={lang} onChange={e=>pickLanguage(e.target.value)}>
       <option value="python">Python 3</option>
       <option value="cpp">C++ 17</option>
       <option value="java">Java 21</option>
      </select>
      <span style={{fontSize:'0.8rem',color:'#888'}}>● {sync}</span>
     </div>
    </div>
    {initial!==null&&<Editor key={p.id+'/'+lang} lang={lang} initial={initial} onEdit={edit}/>}
   </div>

   {/* Bottom Testcase & Execution Console */}
   <div className="lc-console">
    <div className="lc-panel-tabs">
     <button className={'lc-tab '+(consoleTab==='Testcase'?'active':'')} onClick={()=>setConsoleTab('Testcase')}>🧪 Testcase</button>
     <button className={'lc-tab '+(consoleTab==='Result'?'active':'')} onClick={()=>setConsoleTab('Result')}>📊 Test Result</button>
    </div>
    <div className="lc-console-content">
     {consoleTab==='Testcase' ? (
      <div>
       <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px',flexWrap:'wrap',gap:'8px'}}>
        <div className="lc-case-nav" style={{margin:0,flexWrap:'wrap',gap:'6px'}}>
         {customCases.map((_,idx)=>(
          <button key={idx} className={'lc-case-btn '+(activeCase===idx?'active':'')} onClick={()=>setActiveCase(idx)}>
           Case {idx+1}
          </button>
         ))}
         {customCases.length < 12 && (
          <button 
           className="lc-case-btn" 
           title="Add new test case"
           onClick={() => {
             const defaultArgs = p.signature?.params ? p.signature.params.map(()=>0) : [0];
             const next = [...customCases, {args: defaultArgs, expected: 0, sample: true}];
             setCustomCases(next);
             setActiveCase(next.length - 1);
           }}
           style={{fontWeight:700,color:'#2563eb'}}
          >
           +
          </button>
         )}
        </div>
        {customCases.length > 1 && (
         <button 
           className="link" 
           style={{fontSize:'0.8rem',color:'#dc2626',padding:'2px 6px'}}
           onClick={() => {
             const next = customCases.filter((_, i) => i !== activeCase);
             setCustomCases(next);
             setActiveCase(Math.max(0, activeCase - 1));
           }}
         >
           🗑 Remove Case
         </button>
        )}
       </div>

       {customCases[activeCase] && (
        <div style={{background:'#f9fafb',padding:'12px',borderRadius:'6px',border:'1px solid #e5e7eb',fontSize:'0.88rem'}}>
         <div style={{color:'#64748b',fontWeight:600,marginBottom:'4px'}}>Input:</div>
         <textarea
           rows={2}
           value={typeof customCases[activeCase].args === 'string' ? customCases[activeCase].args : JSON.stringify(customCases[activeCase].args.length === 1 ? customCases[activeCase].args[0] : customCases[activeCase].args)}
           onChange={e => {
             try {
               const parsed = JSON.parse(e.target.value);
               const args = Array.isArray(parsed) && p.signature?.params?.length !== 1 ? parsed : [parsed];
               const next = [...customCases];
               next[activeCase] = {...next[activeCase], args};
               setCustomCases(next);
             } catch(err) {}
           }}
           style={{width:'100%',margin:'0 0 10px 0',color:'#111827',background:'#ffffff',border:'1px solid #cbd5e1',padding:'8px',borderRadius:'4px',fontFamily:'monospace',fontSize:'0.85rem'}}
         />
         <div style={{color:'#64748b',fontWeight:600,marginBottom:'4px'}}>Expected Output:</div>
         <textarea
           rows={1}
           value={typeof customCases[activeCase].expected === 'string' ? customCases[activeCase].expected : JSON.stringify(customCases[activeCase].expected)}
           onChange={e => {
             try {
               const expected = JSON.parse(e.target.value);
               const next = [...customCases];
               next[activeCase] = {...next[activeCase], expected};
               setCustomCases(next);
             } catch(err) {}
           }}
           style={{width:'100%',margin:0,color:'#16a34a',background:'#ffffff',border:'1px solid #cbd5e1',padding:'8px',borderRadius:'4px',fontFamily:'monospace',fontSize:'0.85rem'}}
         />
        </div>
       )}
      </div>
     ) : (
      <div>
       {message && <div style={{color:'#ffa116',fontWeight:600}}>{message}</div>}
       {!message && !res && <p style={{color:'#888'}}>Run your code against example testcases or submit your solution.</p>}
       {res && (
        <div>
         <div style={{display:'flex',alignItems:'center',gap:'12px',marginBottom:'12px'}}>
          <span className={'lc-verdict-tag '+res.verdict}>{res.verdict}</span>
          {res.total!=null && <span style={{color:'#9ca3af',fontSize:'0.9rem'}}>{res.passed} / {res.total} testcases passed</span>}
         </div>
         {res.diagnostic && (
          <pre style={{background:'#2d1d1f',border:'1px solid #7f1d1d',color:'#fca5a5',padding:'10px',borderRadius:'6px',fontSize:'0.85rem',whiteSpace:'pre-wrap'}}>
           {res.diagnostic}
          </pre>
         )}
         {res.cases && res.cases.map(row=>(
          <div key={row.number} style={{background:'#f9fafb',padding:'12px',borderRadius:'8px',border:row.status==='Passed'?'1px solid #e5e7eb':'1px solid #fecaca',marginBottom:'10px',fontSize:'0.88rem'}}>
           <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
            <div>
             <strong>Case {row.number}</strong>
             {row.status!=='Passed' && <span style={{marginLeft:'8px',fontSize:'0.75rem',padding:'2px 8px',borderRadius:'4px',background:'#fee2e2',color:'#b91c1c',fontWeight:600}}>Failed Case</span>}
            </div>
            <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
             <span style={{color:row.status==='Passed'?'#16a34a':'#dc2626',fontWeight:700}}>{row.status}</span>
             {row.args && (
              <button 
               className="link" 
               style={{fontSize:'0.8rem',fontWeight:600,color:'#2563eb',padding:'2px 6px'}}
               onClick={() => {
                 const exists = customCases.some(c => JSON.stringify(c.args) === JSON.stringify(row.args));
                 if (!exists) {
                   const next = [...customCases, {args: row.args, expected: row.expected, sample: true}];
                   setCustomCases(next);
                   setActiveCase(next.length - 1);
                 } else {
                   const idx = customCases.findIndex(c => JSON.stringify(c.args) === JSON.stringify(row.args));
                   if (idx !== -1) setActiveCase(idx);
                 }
                 setConsoleTab('Testcase');
               }}
              >
               ➕ Add to Testcases
              </button>
             )}
            </div>
           </div>
           {row.args && (
            <div style={{display:'flex',flexDirection:'column',gap:'6px',fontSize:'0.84rem'}}>
             <div>
              <span style={{color:'#64748b',fontWeight:600}}>Input:</span>
              <pre style={{margin:'2px 0 0 0',background:'#fff',padding:'6px 10px',borderRadius:'4px',border:'1px solid #e2e8f0',overflowX:'auto',color:'#0f172a'}}>{JSON.stringify(row.args.length===1?row.args[0]:row.args)}</pre>
             </div>
             {row.actual !== undefined && (
              <div>
               <span style={{color:'#64748b',fontWeight:600}}>Output:</span>
               <pre style={{margin:'2px 0 0 0',background:'#fff',padding:'6px 10px',borderRadius:'4px',border:'1px solid #e2e8f0',overflowX:'auto',color:row.status==='Passed'?'#16a34a':'#dc2626'}}>{JSON.stringify(row.actual)}</pre>
             </div>
             )}
             {row.expected !== undefined && (
              <div>
               <span style={{color:'#64748b',fontWeight:600}}>Expected:</span>
               <pre style={{margin:'2px 0 0 0',background:'#fff',padding:'6px 10px',borderRadius:'4px',border:'1px solid #e2e8f0',overflowX:'auto',color:'#16a34a'}}>{JSON.stringify(row.expected)}</pre>
              </div>
             )}
            </div>
           )}
          </div>
         ))}
        </div>
       )}
      </div>
     )}
    </div>
    <div className="lc-footer">
     <button className="lc-btn-run" disabled={busy||initial===null} onClick={()=>run('run')}>
      {busy&&consoleTab==='Result'?'Executing…':'▶ Run'}
     </button>
     <button className="lc-btn-submit" disabled={busy||initial===null} onClick={()=>run('submit')}>
      Submit
     </button>
    </div>
   </div>
  </div>
 </div>;
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

 if(!w)return <div style={{padding:'40px',textAlign:'center',color:'#9ca3af'}}>{error||'Loading workspace…'}</div>;
 const status=decision||w;
 if(status.eligible===false)return <section role="alert" style={{background:'#751a25',color:'white',padding:32}}><h1>Disqualified from CodeClash 1.0</h1><p>{status.reason}</p><p>Submissions are closed for your account. Contact the organizer for review.</p></section>;

 const p=w.problems.find(x=>x.id===pid);

 return <div className="lc-layout">
  <div className="lc-header">
   <div className="lc-header-left">
    <a href="/" style={{color:'#ffa116',fontWeight:700,textDecoration:'none',fontSize:'1.1rem'}}>⚡ CodeClash</a>
    <span style={{color:'#666'}}>|</span>
    <select className="lc-select" value={pid||''} onChange={e=>choose(Number(e.target.value))}>
     {w.problems.map((x,idx)=><option key={x.id} value={x.id}>{idx+1}. {x.title}</option>)}
    </select>
    {p&&p.details?.difficulty&&<span className={'lc-difficulty '+p.details.difficulty}>{p.details.difficulty}</span>}
   </div>
   <div className="lc-header-right">
    <span style={{fontSize:'0.85rem',color:'#9ca3af'}}>{w.name} ({w.enrollment})</span>
    <a href={'/leaderboard/'+cid+'/'} target="_blank" rel="noreferrer" className="lc-btn-run" style={{textDecoration:'none'}}>Leaderboard ↗</a>
   </div>
  </div>
  {p?<ProblemView key={p.id+'/'+lang} w={w} p={{...p,...p.languages[lang]}} lang={lang} pickLanguage={pick}/>:<div style={{padding:'40px',textAlign:'center',color:'#9ca3af'}}>No published problems in this contest yet.</div>}
 </div>;
}
