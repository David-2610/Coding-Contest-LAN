import {EcodeTransfer} from './EcodeTransfer';
import React, {useState} from 'react';
import {clock, postForm} from './common';
import {api} from './workspace';

export function Login() {
  const [method, select] = useState('ecode');
  const [message, report] = useState('');
  const [busy, pending] = useState(false);
  const student = method === 'ecode';
  async function submit(event) {
    event.preventDefault();
    pending(true);
    report('');
    try {
      const response = await postForm('/api/login', new FormData(event.currentTarget));
      location.assign(response.staff ? '/organizer/' : '/');
    } catch (error) { report(error.message); pending(false); }
  }
  return <section className="access"><aside className="access-intro"><span className="eyeline">Ecode Presents</span>
    <h1>CodeClash 1.0</h1><p>Competitive Programming Challenge · Organized by David Tembhare</p>
    <div className="terminal-art" aria-hidden="true"><span>ƒ</span><i>(</i>x<i>)</i></div></aside>
    <div className="access-form"><h2>Sign in</h2><form className="formgrid" onSubmit={submit}>
      <label>Enrollment number or organizer username<input name="username" autoComplete="username" required/></label>
      <label>Contest PIN or organizer password<input name="password" type="password" autoComplete="current-password" required/></label>
      <small>Students use the six-digit contest PIN from their E-Code profile.</small>
      {message&&<p role="alert">{message}</p>}<button disabled={busy}>{busy?'Signing in…':'Sign in'}</button>
      
    </form></div></section>
}

export function Lobby({session}) {
  const [filter,choose]=useState('All'), [error,report]=useState('');
  const [review,setReview]=useState(null),[agree,accept]=useState(false);
  React.useEffect(()=>{if(!session.contests.some(c=>c.acknowledged&&['Waiting Room','Scheduled'].includes(c.state)))return;
    const timer=setInterval(async()=>{try{const next=await api('/api/session');if(next.contests.some(c=>c.acknowledged&&c.state==='Live'&&session.contests.find(old=>old.id===c.id)?.state!=='Live'))location.reload()}catch{}},5000);
    return ()=>clearInterval(timer)},[session]);
  const [notice,setNotice]=useState('');
  React.useEffect(()=>{const waiting=session.contests.filter(c=>c.acknowledged&&['Scheduled','Waiting Room'].includes(c.state));
    let live=true;
    const timers=new Map();
    async function beat(c){try{const d=await api('/api/contests/'+c.id+'/heartbeat',{});if(live)setNotice(d.eligible?'':d.reason)}catch{}finally{if(live)timers.set(c.id,setTimeout(()=>beat(c),9000+Math.random()*2000))}}
    waiting.forEach(c=>timers.set(c.id,setTimeout(()=>beat(c),Math.random()*10000)));
    return ()=>{live=false;timers.forEach(clearTimeout)}},[session]);
  const events=session.contests.filter(c=>filter==='All'||c.state===filter);
  async function enter(c) {
    if(!session.user){location.assign('/login/');return}
    try { await api('/api/contests/'+c.id+'/enter',{agree}); location.assign(c.state==='Live'?'/contests/'+c.id+'/':'/'); }
    catch(e){report(e.message)}
  }
  return <><section className="lobby-hero"><div><span className="eyeline">E-Code / Contest LAN</span>
    <h1>Contest arena</h1><p>Enter a live round, check the schedule and follow the standings.</p></div>
    <div className="hero-stat"><strong>{session.contests.filter(c=>c.state==='Live').length}</strong><span>Live rounds</span></div></section>
    <section className="rounds"><h2>Contest schedule</h2><div className="switcher">{['All','Live','Upcoming','Ended'].map(f=><button key={f} aria-pressed={f===filter} onClick={()=>choose(f)}>{f}</button>)}</div></section>
    {error&&<p role="alert">{error}</p>}
    {notice&&<p role="alert">Disqualified · {notice}</p>}{review&&<section className="card formgrid"><h2>Contest instructions · {review.title}</h2><p>Stay on the official Wi-Fi and use your own Ecode enrollment and PIN. Once admitted, wait for the organizer to start the round. Refresh the schedule to enter.</p><p>Select a problem and language. Follow its input and output format and resource limits. Run checks the examples. Submit runs official cases until the first failure. You can revise and resubmit before the deadline. Full solves earn the assigned points, with total solve time breaking ties.</p><p>Use the built-in editor, problem statements and your own results. Without organizer permission, external resources, AI assistance, sharing code, using another account or interfering with the network are prohibited. Report connection issues to the organizer.</p><label><input type="checkbox" checked={agree} onChange={e=>accept(e.target.checked)}/> I have read and understood the contest instructions and agree to follow the rules.</label><button disabled={!agree} onClick={()=>enter(review)}>Acknowledge and continue</button></section>}
    <div className="schedule">{events.map(c=><article className="card contest-card" key={c.id}>
    {c.banner&&<img src={c.banner} alt={c.title} style={{width:'100%',borderRadius:'8px',marginBottom:'12px',objectFit:'cover',maxHeight:'160px'}}/>}
    <span className={'pill '+c.state}>{c.state}</span><h2>{c.title}</h2>
    {c.description&&<p style={{fontSize:'0.9rem',color:'#555',margin:'8px 0'}}>{c.description.length>180?c.description.slice(0,180)+'…':c.description}</p>}
    <dl className="dates"><dt>Starts</dt><dd>{clock(c.starts)}</dd><dt>Ends</dt><dd>{clock(c.ends)}</dd>
    {c.duration&&<><dt>Duration</dt><dd>{c.duration} mins</dd></>}
    {c.totalProblems>0&&<><dt>Problems</dt><dd>{c.totalProblems}</dd></>}
    </dl>
    <div className="actions">{['Live','Waiting Room','Scheduled'].includes(c.state)&&!session.staff&&<button disabled={c.acknowledged&&c.state!=='Live'} onClick={()=>c.acknowledged?enter(c):(setReview(c),accept(false))}>{c.acknowledged?(c.state==='Live'?'Open workspace':'Waiting for start'):'Read instructions'}</button>}<a href={'/leaderboard/'+c.id+'/'}>View standings →</a></div></article>)}</div>
    {!events.length&&<p className="card">No {filter==='All'?'scheduled':filter.toLowerCase()} contests.</p>}</>
}

export function Roster(){
  const [rows,setRows]=useState(null),[query,search]=useState(''),[error,report]=useState('');
  React.useEffect(()=>{api('/api/organizer/roster').then(data=>setRows(data.students)).catch(e=>report(e.message))},[]);
  const filtered=(rows||[]).filter(r=>Object.values(r).some(v=>v.toLowerCase().includes(query.trim().toLowerCase())));
  return <><div className="page-heading"><div><span className="eyeline">Organizer</span><h1>Student roster</h1><p>Registered E-Code students available for offline sign-in.</p></div></div>
    <EcodeTransfer url="/api/organizer/roster/refresh" onComplete={()=>api("/api/organizer/roster").then(d=>{setRows(d.students);report("")}).catch(e=>report(e.message))}/>
    <section className="card panel"><label className="roster-search">Search roster <input type="search" value={query} placeholder="Name, enrollment, handle or batch" onChange={e=>search(e.target.value)}/></label>
    {error?<p role="alert">{error}</p>:rows===null?<p>Loading roster…</p>:<><p>{filtered.length} of {rows.length} students</p><table><thead><tr>{['Name','Enrollment','Handle','Batch'].map(h=><th scope="col" key={h}>{h}</th>)}</tr></thead><tbody>{filtered.map(r=><tr key={r.enrollment}><td>{r.full_name}</td><td>{r.enrollment}</td><td>{r.user__username}</td><td>{r.ecode_batch}</td></tr>)}</tbody></table>{!filtered.length&&<p>{rows.length?'No matching students.':'Import the E-Code roster on the server before the contest.'}</p>}</>}</section></>
}

export function GlobalBoard(){
  const [batches,setBatches]=useState([{key:'all',name:'All Batches (Global)'}]),[batch,select]=useState('all'),[page,turn]=useState(1);
  const [data,show]=useState(null),[error,report]=useState(''),[attempt,retry]=useState(0);
  React.useEffect(()=>{
    api('/api/ecode/leaderboards?list=1').then(r=>{
      if(Array.isArray(r.data)){
        const list=[{key:'all',name:'All Batches (Global)'}];
        const seen=new Set(['all']);
        for(const item of r.data){
          if(!item) continue;
          let k='', n='';
          if(typeof item==='object'){
            k=String(item.batchKey??item.key??item.batch??item.id??'');
            n=String(item.batchName??item.name??item.title??k);
          }else{
            k=String(item);
            n=k==='all'?'All Batches (Global)':(k.startsWith('20')?`Batch ${k}`:k);
          }
          if(k && !seen.has(k)){
            seen.add(k);
            list.push({key:k, name:n});
          }
        }
        setBatches(list);
      }
    }).catch(()=>{});
  },[attempt]);
  React.useEffect(()=>{
    let current=true;show(null);report('');
    api('/api/ecode/leaderboards?batch='+encodeURIComponent(batch)+'&page='+page).then(r=>{
      if(!Array.isArray(r.data?.rankings))throw Error('Unexpected ranking data.');
      if(current)show(r.data);
    }).catch(e=>{if(current)report(e.message)});
    return ()=>{current=false};
  },[batch,page,attempt]);
  return <><div className="page-heading"><div><span className="eyeline">E-Code online</span><h1>Global rankings</h1><p>Published results across contests, grouped by academic batch.</p></div></div>
  <section className="card panel"><label style={{display:'flex',alignItems:'center',gap:'10px',fontWeight:600,marginBottom:'16px'}}>Batch <select value={batch} onChange={e=>{select(e.target.value);turn(1)}} style={{padding:'6px 12px',borderRadius:'6px',border:'1px solid #cbd5e1',fontSize:'0.92rem'}}>{batches.map(b=><option value={b.key} key={b.key}>{b.name}</option>)}</select></label>
  {error?<><p role="alert" style={{color:'#9c2940'}}>{error}</p><button onClick={()=>retry(attempt+1)}>Retry</button></>:!data?<p>Loading rankings…</p>:<>
  <p style={{color:'#475569',fontWeight:600}}>{data.totalParticipants??0} participants</p><table><thead><tr><th>Rank</th><th>Contestant</th><th>Score</th></tr></thead><tbody>{data.rankings.map((r,i)=><tr key={i}><td><strong>#{r.rank??(page-1)*50+i+1}</strong></td><td>{r.fullName||r.username||'—'}</td><td><strong>{r.totalScore??r.score??'—'}</strong></td></tr>)}</tbody></table>
  {!data.rankings.length&&<p style={{padding:'20px 0',textAlign:'center',color:'#64748b'}}>No published results for {batches.find(b=>b.key===batch)?.name||batch} yet.</p>}{(data.totalParticipants>50||page>1)&&<div className="actions"><button disabled={page===1} onClick={()=>turn(page-1)}>Previous</button><span>Page {page}</span><button disabled={page*50>=(data.totalParticipants||0)} onClick={()=>turn(page+1)}>Next</button></div>}</>}</section></>
}
