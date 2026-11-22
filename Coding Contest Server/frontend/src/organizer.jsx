import {EcodeTransfer} from './EcodeTransfer';
import React,{useState,useEffect,useRef} from 'react';
import {api} from './workspace';
import {clock,postForm} from './common';

function BankPicker({cid,onDone}){
  const [bank,setBank]=useState(null),[err,fail]=useState(''),[selected,setSelected]=useState([]),[busy,wait]=useState(false),[replace,setReplace]=useState(false);
  useEffect(()=>{
    api('/api/organizer/bank').then(d=>setBank(d.questions)).catch(e=>fail(e.message));
  },[]);
  function toggle(id){
    setSelected(prev=>prev.includes(id)?prev.filter(x=>x!==id):[...prev,id]);
  }
  return <section className="card formgrid" style={{background:'#f8fafc',padding:'16px',borderRadius:'8px',border:'1px solid #e2e8f0'}}>
    <h2>Import from Question Bank / Previous Contests</h2>
    <p style={{fontSize:'0.9rem',color:'#555',margin:'4px 0 10px 0'}}>Select any questions previously uploaded or used in other rounds to add them to this contest.</p>
    {err&&<p role="alert" style={{color:'#9c2940'}}>{err}</p>}
    {bank===null?<p>Loading question bank…</p>:!bank.length?<p>No questions found in previous contests.</p>:(
      <div>
        <div style={{display:'flex',flexDirection:'column',gap:'8px',maxHeight:'280px',overflowY:'auto',margin:'10px 0'}}>
          {bank.map(q=>(
            <label key={q.id} style={{display:'flex',gap:'10px',alignItems:'flex-start',background:'#fff',padding:'10px',borderRadius:'6px',border:'1px solid #cbd5e1',cursor:'pointer'}}>
              <input type="checkbox" checked={selected.includes(q.id)} onChange={()=>toggle(q.id)}/>
              <div>
                <strong>{q.title}</strong> <small style={{color:'#64748b'}}>({q.externalId})</small>
                <div style={{fontSize:'0.85rem',color:'#64748b',marginTop:'2px'}}>
                  {q.difficulty} · {q.maxScore} pts · {q.testCount} tests · <em>Source: {q.fromContest}</em>
                </div>
              </div>
            </label>
          ))}
        </div>
        <label style={{display:'block',margin:'10px 0'}}><input type="checkbox" checked={replace} onChange={e=>setReplace(e.target.checked)}/> Replace existing question with matching ID if already in contest</label>
        <div className="actions">
          <button disabled={busy||!selected.length} onClick={async()=>{
            wait(true);
            try{
              await api('/api/organizer/'+cid+'/copy-bank',{problemIds:selected,replace});
              onDone();
            }catch(e){fail(e.message)}finally{wait(false)}
          }}>Add {selected.length} selected question{selected.length>1?'s':''}</button>
          <button type="button" className="secondary" onClick={onDone}>Cancel</button>
        </div>
      </div>
    )}
  </section>
}

function Author({cid,onDone}){
 const [items,set]=useState(null),[err,fail]=useState(''),[replace,toggle]=useState(false),[busy,wait]=useState(false);
 return <section className="card formgrid" style={{background:'#f8fafc',padding:'16px',borderRadius:'8px',border:'1px solid #e2e8f0'}}>
 <h2>Add / Import Questions (Single or Multiple)</h2>
 <div style={{display:'flex',gap:'12px',marginBottom:'10px'}}>
   <a href="/static/question-example.json" download style={{fontWeight:'bold'}}>⬇ Download example JSON</a>
   <a href="/static/question-schema.json" download style={{color:'#666'}}>Download schema</a>
 </div>
 <p style={{fontSize:'0.9rem',color:'#555',margin:'4px 0 12px 0'}}>
   Upload a single question JSON object or an array of multiple question objects <code>[...]</code> to insert all at once.
 </p>
 <input type="file" aria-label="Question JSON" accept=".json" onChange={async e=>{
   set(null);fail('');
   try{
     const file=e.target.files[0];
     if(!file)return;
     if(file.size>1000000)throw Error("Maximum file size is 1 MB.");
     const parsed=JSON.parse(await file.text());
     const list = Array.isArray(parsed) ? parsed : [parsed];
     if(!list.length) throw Error("JSON contains no problems.");
     for(const d of list){
       if(typeof d.title!=="string"||!Array.isArray(d.testCases)||!Array.isArray(d.examples)){
         throw Error("Each question must contain title, examples and testCases.");
       }
     }
     set(list);
   }catch(e){fail(e.message)}
 }}/>
 {items&&<div style={{marginTop:'12px',background:'#fff',padding:'12px',borderRadius:'6px',border:'1px solid #cbd5e1'}}>
   <h3>{items.length === 1 ? items[0].title : `${items.length} Questions Ready to Insert`}</h3>
   <ul style={{margin:'8px 0 12px 20px',padding:0}}>
     {items.map((doc,idx)=>(
       <li key={idx}>
         <strong>{doc.title}</strong> <small style={{color:'#64748b'}}>({doc.id || 'No ID'})</small> · {doc.difficulty || 'Normal'} · {doc.scoring?.maxScore ?? 100} pts
         ({doc.testCases?.filter(t=>t?.visibility==="public").length} public, {doc.testCases?.filter(t=>t?.visibility==="hidden").length} hidden tests)
       </li>
     ))}
   </ul>
   <label style={{display:'block',margin:'10px 0'}}><input type="checkbox" checked={replace} onChange={e=>toggle(e.target.checked)}/> Replace existing question(s) with matching IDs if already added</label>
   <div className="actions">
     <button disabled={busy} onClick={async()=>{
       wait(true);
       try{
         await api('/api/organizer/'+cid+'/problems'+(replace?'?replace=1':''), items.length === 1 ? items[0] : items);
         onDone();
       }catch(e){fail(e.message)}finally{wait(false)}
     }}>Confirm import ({items.length} question{items.length>1?'s':''})</button>
     <button type="button" className="secondary" onClick={onDone}>Cancel</button>
   </div>
 </div>}
 {err&&<p role="alert" style={{color:'#9c2940'}}>{err}</p>}
 {!items&&<button type="button" className="secondary" style={{marginTop:'10px'}} onClick={onDone}>Cancel</button>}
 </section>
}
function JobRow({j}){
 const [source,show]=useState(null);
 return <details onToggle={async e=>{if(e.target.open&&source===null){try{show((await api('/api/organizer/jobs/'+j.id)).source)}catch(err){show(err.message)}}}}><summary>{j.entry__display} · {j.problem__title} · {j.language} · {j.verdict}</summary><pre>{source??'Loading…'}</pre></details>
}

function EcodeIntegration({cid, contest, onRefresh}) {
  const [fetching, setFetching] = useState(false);
  const [readiness, setReadiness] = useState(null);
  const [preview, setPreview] = useState(null);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [force, setForce] = useState(false);
  const [targetCid, setTargetCid] = useState('');

  useEffect(() => {
    if (cid) {
      api('/api/organizer/contest/' + cid + '/readiness').then(setReadiness).catch(()=>{});
    }
  }, [cid]);

  async function handleFetchContest() {
    setFetching(true);
    setErr('');
    setMsg('');
    try {
      const res = await api('/api/organizer/contest/fetch', {
        contestId: targetCid.trim() || undefined,
        force: force
      });
      setMsg(`Successfully fetched '${res.contest.title}' (E-Code ID: ${res.contest.ecodeContestId})`);
      onRefresh?.();
      setTimeout(() => location.reload(), 1500);
    } catch(e) {
      setErr(e.message);
    } finally {
      setFetching(false);
    }
  }

  async function handleLoadPreview() {
    setErr('');
    try {
      const res = await api('/api/organizer/contest/' + cid + '/sync-preview');
      setPreview(res);
    } catch(e) {
      setErr(e.message);
    }
  }

  return (
    <div style={{display:'flex', flexDirection:'column', gap:'16px'}}>
      <h2>E-Code Cloud Integration & Offline Readiness</h2>
      
      <section style={{background:'#f8fafc', padding:'16px', borderRadius:'8px', border:'1px solid #e2e8f0'}}>
        <h3>Official E-Code Contest Configuration</h3>
        {contest?.ecodeContestId ? (
          <div>
            <p><strong>Official Contest ID:</strong> <code style={{background:'#e2e8f0', padding:'2px 6px', borderRadius:'4px'}}>{contest.ecodeContestId}</code></p>
            <p><strong>Title:</strong> {contest.title}</p>
            {contest.duration && <p><strong>Duration:</strong> {contest.duration} minutes</p>}
            {contest.totalProblems > 0 && <p><strong>Expected Problems:</strong> {contest.totalProblems}</p>}
            {contest.batchTarget && <p><strong>Target Batch:</strong> {contest.batchTarget}</p>}
            {contest.banner && (
              <div style={{margin:'10px 0'}}>
                <img src={contest.banner} alt="Contest banner" style={{maxHeight:'120px', borderRadius:'6px', border:'1px solid #ccc', objectFit:'cover'}}/>
              </div>
            )}
            <p><strong>Sync Status:</strong> <span className={'pill ' + (contest.syncStatus || 'READY')}>{contest.syncStatus || 'READY'}</span></p>
            {contest.syncedAt && <p><strong>Synced At:</strong> {clock(contest.syncedAt)}</p>}
          </div>
        ) : (
          <p style={{color:'#666'}}>No official E-Code contest details fetched yet for this local event.</p>
        )}

        <div style={{marginTop:'12px', display:'flex', gap:'10px', alignItems:'center', flexWrap:'wrap'}}>
          <input 
            type="text" 
            placeholder="Optional specific Contest ID" 
            value={targetCid} 
            onChange={e => setTargetCid(e.target.value)}
            style={{maxWidth:'240px'}}
          />
          <label style={{display:'inline-flex', alignItems:'center', gap:'6px', cursor:'pointer', fontSize:'0.9rem'}}>
            <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)}/>
            Force update if exists
          </label>
          <button disabled={fetching} onClick={handleFetchContest}>
            {fetching ? 'Fetching from E-Code…' : 'Fetch Active Contest from E-Code'}
          </button>
        </div>
      </section>

      {readiness && (
        <section style={{background:'#f8fafc', padding:'16px', borderRadius:'8px', border:'1px solid #e2e8f0'}}>
          <h3>Offline LAN Contest Readiness</h3>
          <ul style={{listStyle:'none', padding:0, margin:'10px 0'}}>
            <li style={{margin:'6px 0'}}>
              {readiness.checks.ecodeLinked ? '✅' : '❌'} <strong>E-Code Contest Linked:</strong> {readiness.checks.ecodeLinked ? `Official ID: ${readiness.contest.ecodeContestId}` : 'Not linked yet'}
            </li>
            <li style={{margin:'6px 0'}}>
              {readiness.checks.problemsConfigured ? '✅' : '⚠️'} <strong>Problems Configured:</strong> {readiness.checks.problemCounts.configured} configured {readiness.checks.problemCounts.expected > 0 ? `(expected ${readiness.checks.problemCounts.expected})` : ''}
            </li>
            <li style={{margin:'6px 0'}}>
              {readiness.checks.rosterImported ? '✅' : '❌'} <strong>Roster Imported:</strong> {readiness.checks.rosterCount} students available offline
            </li>
            <li style={{margin:'6px 0'}}>
              {readiness.checks.judgeActive ? '✅' : '❌'} <strong>Judge Worker:</strong> {readiness.checks.judgeActive ? 'Active and listening' : 'Inactive'}
            </li>
          </ul>
          <p>
            <strong>Status:</strong> {readiness.checks.offlineReady ? 
              <span style={{color:'#087a65', fontWeight:'bold'}}> Ready for offline LAN contest!</span> : 
              <span style={{color:'#b04c28', fontWeight:'bold'}}> Attention needed before starting contest</span>
            }
          </p>
        </section>
      )}

      <section style={{background:'#f8fafc', padding:'16px', borderRadius:'8px', border:'1px solid #e2e8f0'}}>
        <h3>Post-Contest Results Synchronization</h3>
        <p>After the contest ends and standings are finalized, you can preview the JSON payload and sync to E-Code.</p>
        
        <div style={{display:'flex', gap:'10px', marginTop:'10px', flexWrap:'wrap'}}>
          <button type="button" className="secondary" onClick={handleLoadPreview}>Preview Sync Payload</button>
          {preview && (
            <button type="button" onClick={() => {
              const blob = new Blob([JSON.stringify(preview.payload, null, 2)], {type:'application/json'});
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `sync-payload-${preview.payload.contestId}.json`;
              a.click();
            }}>Download Payload JSON</button>
          )}
        </div>

        {preview && (
          <div style={{marginTop:'12px'}}>
            <h4>Payload Preview ({preview.payload.participants?.length || 0} participants, {preview.payload.problems?.length || 0} problems)</h4>
            {preview.warnings?.map((w, i) => <p key={i} style={{color:'#98651a'}}>⚠️ {w}</p>)}
            <pre style={{maxHeight:'220px', overflow:'auto', background:'#1e293b', color:'#f8fafc', padding:'10px', borderRadius:'4px', fontSize:'12px'}}>
              {JSON.stringify(preview.payload, null, 2)}
            </pre>
          </div>
        )}
      </section>

      {err && <p role="alert" style={{color:'#9c2940'}}>{err}</p>}
      {msg && <p role="status" style={{color:'#087a65'}}>{msg}</p>}
    </div>
  );
}

function BankManager(){
  const [bank,setBank]=useState(null),[err,fail]=useState(""),[busy,wait]=useState(false),[uploading,setUploading]=useState(false),[msg,setMsg]=useState("");
  const [filter,setFilter]=useState("");
  function load(){api("/api/organizer/bank").then(d=>setBank(d.questions)).catch(e=>fail(e.message));}
  useEffect(()=>{load()},[]);
  const filtered=(bank||[]).filter(q=>!filter||(q.title+q.externalId+q.fromContest).toLowerCase().includes(filter.toLowerCase()));
  return <div style={{display:"flex",flexDirection:"column",gap:"16px"}}>
    <div className="bar">
      <div>
        <h2>Master Question Bank ({bank?bank.length:"…"})</h2>
        <p style={{margin:"4px 0",color:"#64748b"}}>Upload bulk questions here. Questions added here can be imported into any contest with one click.</p>
      </div>
      <div style={{display:"flex",gap:"8px"}}>
        <a href="/static/question-example.json" download className="button secondary">⬇ LeetCode Format Example</a>
        <button onClick={()=>setUploading(!uploading)}>{uploading?"Close Upload":"+ Bulk Upload Questions"}</button>
      </div>
    </div>
    {msg&&<div className="alert" role="status" style={{background:"#ecfdf5",color:"#065f46"}}>{msg}</div>}
    {err&&<p role="alert" style={{color:"#9c2940"}}>{err}</p>}
    {uploading&&<div style={{background:"#f8fafc",border:"1px solid #cbd5e1",borderRadius:"8px",padding:"16px"}}>
      <h3>Upload Bulk Question JSON (LeetCode Format)</h3>
      <p style={{fontSize:"0.9rem",color:"#64748b"}}>Upload a JSON array <code>[...]</code> of questions matching the LeetCode format.</p>
      <input type="file" accept=".json" onChange={async e=>{
        const file=e.target.files[0];if(!file)return;
        try{
          const data=JSON.parse(await file.text());
          const list=Array.isArray(data)?data:[data];
          wait(true);setMsg("");fail("");
          const res=await api("/api/organizer/bank/upload", list);
          setMsg("Successfully added " + res.count + " question(s) to Question Bank!");
          setUploading(false);
          load();
        }catch(e){fail(e.message)}finally{wait(false)}
      }}/>
    </div>}
    <div>
      <input placeholder="Filter questions by title or ID..." value={filter} onChange={e=>setFilter(e.target.value)} style={{maxWidth:"360px",marginBottom:"12px"}}/>
      {bank===null?<p>Loading bank…</p>:!filtered.length?<p>No questions found in bank.</p>:(
        <div style={{display:"grid",gap:"10px",maxHeight:"500px",overflowY:"auto"}}>
          {filtered.map(q=><div key={q.id} style={{background:"#fff",padding:"14px",borderRadius:"8px",border:"1px solid #e2e8f0",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
            <div>
              <div style={{display:"flex",gap:"8px",alignItems:"center"}}>
                <strong>{q.title}</strong>
                <span className="pill" style={{background:"#f1f5f9",color:"#475569"}}>{q.externalId}</span>
                <span className="pill" style={{background:q.difficulty==="Easy"?"#dcfce7":q.difficulty==="Medium"?"#fef9c3":"#fee2e2",color:"#1e293b"}}>{q.difficulty}</span>
              </div>
              <div style={{fontSize:"0.85rem",color:"#64748b",marginTop:"4px"}}>
                Function: <code>{q.function||"solve"}</code> · {q.maxScore} pts · {q.testCount} tests · <em>Source: {q.fromContest}</em>
              </div>
            </div>
          </div>)}
        </div>
      )}
    </div>
  </div>;
}

function Decision({row,done}){
 const [open,toggle]=useState(false),[err,fail]=useState('');
 return open?<form onSubmit={async e=>{e.preventDefault();try{await postForm('/api/organizer/entries/'+row.id+'/eligibility',new FormData(e.target));toggle(false);done()}catch(e){fail(e.message)}}}><input type="hidden" name="action" value={row.eligible?'disqualify':'reinstate'}/><input aria-label="Decision reason" name="reason" required maxLength={800} placeholder="Decision reason"/><button>Confirm</button><button type="button" className="link" onClick={()=>toggle(false)}>Cancel</button>{err}</form>:<button className="link" onClick={()=>toggle(true)}>{row.eligible?'Disqualify':'Reinstate'}</button>
}
export function Organizer({session}){
 const [cid,pick]=useState(Number(new URLSearchParams(location.search).get('contest'))||session.contests[0]?.id),[data,load]=useState(null),[tab,select]=useState('Participants'),[notice,notify]=useState(''),[err,fail]=useState(''),[form,setForm]=useState('');const cursor=useRef(null);
 useEffect(()=>{cursor.current=null;notify('');load(null);if(!cid)return;let live=true;
  const poll=async()=>{try{const d=await api('/api/organizer/'+cid);if(!live)return;const alerts=d.events.filter(v=>v.kind==='Heartbeat lost'&&cursor.current!==null&&v.id>cursor.current);if(alerts.length)notify(alerts.map(v=>v.entry__display).join(', ')+' · workspace heartbeat lost');cursor.current=d.events[0]?.id||0;load(d);fail('')}catch(e){if(live)fail(e.message)}};poll();const t=setInterval(poll,4000);return()=>{live=false;clearInterval(t)}},[cid,form]);
 const [query,search]=useState(''),[status,filter]=useState('All'),[order,sort]=useState('name');
 const visible=(data?.rows||[]).filter(r=>[r.name,r.enrollment,r.username].join(' ').toLowerCase().includes(query.toLowerCase())&&(status==='All'||(status==='Disqualified'?!r.eligible:r.presence===status))).sort((a,b)=>order==='name'?a.name.localeCompare(b.name):b.submits-a.submits);
 const contest=session.contests.find(x=>x.id===cid);
 const metrics=[['Registered entries',data?.rows.length,'#5a4abc'],['Online in workspace',data?.rows.filter(v=>v.presence==='Online').length,'#087a65'],['Unstable',data?.rows.filter(v=>v.presence==='Unstable').length,'#98651a'],['Disqualified',data?.rows.filter(v=>!v.eligible).length,'#9c2940'],['Disconnected',data?.rows.filter(v=>v.presence==='Disconnected').length,'#b04c28'],['Reconnected participants',data?.rows.filter(v=>v.reconnects>0).length,'#126a62'],['Active judge jobs',data?.activeJobs,'#485480'],['Official submissions',data?.submissions,'#34689e']];
 return <><div className="page-heading"><div><h1>Contest control</h1><p>Registration, judging and connection activity.</p></div><button onClick={()=>{select('E-Code Cloud');setForm('')}}>Fetch from E-Code</button></div><section className="contestbar"><div><label htmlFor="event">Selected contest</label><select id="event" value={cid||''} onChange={e=>{pick(+e.target.value);setForm('')}}>{session.contests.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select></div>{contest&&<div style={{display:'flex',gap:'8px',alignItems:'center'}}>{({"Draft":"Scheduled","Scheduled":"Waiting Room","Waiting Room":"Active","Live":"Ended"})[contest.state]&&<button onClick={async()=>{const f=new FormData();f.set("stage",({"Draft":"Scheduled","Scheduled":"Waiting Room","Waiting Room":"Active","Live":"Ended"})[contest.state]);try{await postForm("/api/organizer/"+cid+"/stage",f);location.reload()}catch(e){fail(e.message)}}}>{{"Draft":"Schedule","Scheduled":"Open waiting room","Waiting Room":"Start round","Live":"End round"}[contest.state]}</button>}{(contest.state==="Ended"||new Date(contest.ends)<=new Date())&&<button className="secondary" onClick={async()=>{if(!window.confirm("Restart this contest and return it to Waiting Room with fresh duration?"))return;const f=new FormData();f.set("stage","Waiting Room");try{await postForm("/api/organizer/"+cid+"/stage",f);location.reload()}catch(e){fail(e.message)}}}>Restart contest</button>}<span className={'pill '+contest.state}>{contest.state}</span><small>Ends {clock(contest.ends)}</small></div>}</section>
 {err&&<p role="alert">{err}</p>}{notice&&<div className="alert" role="alert">{notice}<button onClick={()=>notify('')} className="link">Dismiss</button></div>}
 <section className="metrics">{metrics.map(([label,n,color])=><div key={label} style={{'--accent':color}}><span>{label}</span><strong>{n??'—'}</strong></div>)}</section>
 <div className="tabs" role="tablist">{['Participants','Connection events','Problems','Question Bank','Standings','Submissions','E-Code Cloud'].map(t=><button role="tab" aria-selected={tab===t} key={t} onClick={()=>{select(t);setForm('')}}>{t}</button>)}</div>
 {data&&<section className="card panel">
 {tab==='Participants'&&<><h2>Contest roster</h2><div className="actions"><input aria-label="Search entries" placeholder="Name, username or enrollment" value={query} onChange={e=>search(e.target.value)}/><select aria-label="Connection filter" value={status} onChange={e=>filter(e.target.value)}>{['All','Online','Unstable','Disconnected','Unknown','Disqualified'].map(s=><option key={s}>{s}</option>)}</select><select aria-label="Sort entries" value={order} onChange={e=>sort(e.target.value)}><option value="name">Name</option><option value="submits">Most submissions</option></select></div><table><thead><tr>{['Participant','Enrollment','Workspace','Missed (est.)','Observed duration','Reconnects','Last seen','Submissions','Eligibility'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{visible.map(r=><tr key={r.id}><td>{r.name}<small>{r.username}</small></td><td>{r.enrollment}</td><td><span className={'pill '+r.presence}>{r.presence}</span></td><td>{r.missed??"—"}</td><td>{r.connectedSeconds==null?"—":r.connectedSeconds+" s"}</td><td>{r.reconnects}</td><td>{r.last?clock(r.last):'—'}</td><td>{r.submits}</td><td>{!r.eligible&&<strong>Disqualified </strong>}{data.final?(r.eligible?"Eligible":"Disqualified"):<Decision row={r} done={()=>api("/api/organizer/"+cid).then(load)}/>}</td></tr>)}</tbody></table>{!data.rows.length&&<p>Entries appear when a candidate enters this contest.</p>}</>}
 {tab==='Connection events'&&<><h2>Connection activity</h2><p>Workspaces check in every 10 seconds. A 40-second gap triggers an alert. Closing the tab or device sleep can also cause a gap.</p>{data.events.map(e=><div className="event" key={e.id}><span className={'dot '+(e.kind==='Connected'?'good':'bad')}/><b>{e.entry__display}</b><span>{e.kind}</span><time>{clock(e.at)}</time></div>)}{!data.events.length&&<p>No workspace events yet.</p>}</>}
 {tab==='Question Bank'&&<BankManager/>}
  {tab==='Problems'&&<><div className="bar"><h2>Problem set ({data.problems.length})</h2><div style={{display:'flex',gap:'8px'}}><button className="secondary" onClick={()=>setForm(form==='bank'?'':'bank')}>Import from Question Bank</button><button onClick={()=>setForm(form==='problem'?'':'problem')}>Add problem</button></div></div>{form==='bank'?<BankPicker cid={cid} onDone={()=>setForm('')}/>:form==='problem'?<Author cid={cid} onDone={()=>setForm('')}/>:data.problems.map(p=><div className="event" key={p.id}><b>{p.title}</b><span>{p.published?'Published':'Draft'}</span></div>)}{!data.problems.length&&!form&&<p style={{padding:'12px 0',color:'#64748b'}}>No problems added yet. Click &quot;Import from Question Bank&quot; to reuse questions from previous contests, or &quot;Add problem&quot; to import a question JSON file.</p>}</>}
 {tab==='Standings'&&<><div className="bar"><h2>Live standings</h2><a href={'/leaderboard/'+cid+'/'}>Open projector ↗</a></div>{data.scores.map((s,i)=><div className="event" key={i}><b>#{s.rank} {s.name}</b><span>{s.score??s.solved} points · {s.solved} solved</span><time>{s.seconds}s</time></div>)}{data.final&&<EcodeTransfer key={cid} publish url={"/api/organizer/"+cid+"/publish"}/>} {data.final&&<a href={'/organizer-export/'+cid}>Download final JSON</a>}</>}
 {tab==='Submissions'&&<><h2>Recent submissions</h2>{data.jobs.map(j=><JobRow key={j.id} j={j}/>)}{!data.jobs.length&&<p>No official submissions or archived drafts yet.</p>}</>}
 {tab==='E-Code Cloud'&&<EcodeIntegration cid={cid} contest={contest} onRefresh={()=>location.reload()}/>}
 </section>}</>
}
