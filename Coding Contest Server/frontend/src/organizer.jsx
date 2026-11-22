import {EcodeTransfer} from './EcodeTransfer';
import React, {useState, useEffect, useRef} from 'react';
import {api} from './workspace';
import {clock, postForm} from './common';

function BankPicker({cid, onDone}) {
  const [bank, setBank] = useState(null), [err, fail] = useState(''), [selected, setSelected] = useState([]), [busy, wait] = useState(false), [replace, setReplace] = useState(false);
  useEffect(() => {
    api('/api/organizer/bank').then(d => setBank(d.questions)).catch(e => fail(e.message));
  }, []);
  function toggle(id) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }
  return (
    <section className="card formgrid" style={{background:'#f8fafc', padding:'16px', borderRadius:'8px', border:'1px solid #e2e8f0', margin:'12px 0'}}>
      <h2>Import from Master Question Bank</h2>
      <p style={{fontSize:'0.9rem', color:'#555', margin:'4px 0 10px 0'}}>Select any questions previously uploaded to add them to this contest.</p>
      {err && <p role="alert" style={{color:'#9c2940'}}>{err}</p>}
      {bank === null ? <p>Loading question bank…</p> : !bank.length ? <p>No questions found in bank.</p> : (
        <div>
          <div style={{display:'flex', flexDirection:'column', gap:'8px', maxHeight:'280px', overflowY:'auto', margin:'10px 0'}}>
            {bank.map(q => (
              <label key={q.id} style={{display:'flex', gap:'10px', alignItems:'flex-start', background:'#fff', padding:'10px', borderRadius:'6px', border:'1px solid #cbd5e1', cursor:'pointer'}}>
                <input type="checkbox" checked={selected.includes(q.id)} onChange={() => toggle(q.id)}/>
                <div>
                  <strong>{q.title}</strong> <small style={{color:'#64748b'}}>({q.externalId})</small>
                  <div style={{fontSize:'0.85rem', color:'#64748b', marginTop:'2px'}}>
                    {q.difficulty} · {q.maxScore} pts · {q.testCount} tests · <em>Source: {q.fromContest}</em>
                  </div>
                </div>
              </label>
            ))}
          </div>
          <label style={{display:'block', margin:'10px 0'}}>
            <input type="checkbox" checked={replace} onChange={e => setReplace(e.target.checked)}/> Replace existing question with matching ID if already in contest
          </label>
          <div className="actions" style={{display:'flex', gap:'8px'}}>
            <button disabled={busy || !selected.length} onClick={async () => {
              wait(true);
              try {
                await api('/api/organizer/' + cid + '/copy-bank', {problemIds: selected, replace});
                onDone();
              } catch(e) { fail(e.message); } finally { wait(false); }
            }}>Add {selected.length} selected question{selected.length > 1 ? 's' : ''}</button>
            <button type="button" className="secondary" onClick={onDone}>Cancel</button>
          </div>
        </div>
      )}
    </section>
  );
}

function Author({cid, onDone}) {
  const [items, set] = useState(null), [err, fail] = useState(''), [replace, toggle] = useState(false), [busy, wait] = useState(false);
  return (
    <section className="card formgrid" style={{background:'#f8fafc', padding:'16px', borderRadius:'8px', border:'1px solid #e2e8f0', margin:'12px 0'}}>
      <h2>Add / Import Questions (Single or Multiple)</h2>
      <div style={{display:'flex', gap:'12px', marginBottom:'10px'}}>
        <a href="/static/question-example.json" download style={{fontWeight:'bold'}}>⬇ Download example JSON</a>
        <a href="/static/question-schema.json" download style={{color:'#666'}}>Download schema</a>
      </div>
      <p style={{fontSize:'0.9rem', color:'#555', margin:'4px 0 12px 0'}}>
        Upload a single question JSON object or an array of multiple question objects <code>[...]</code> to insert all at once.
      </p>
      <input type="file" aria-label="Question JSON" accept=".json" onChange={async e => {
        set(null); fail('');
        try {
          const file = e.target.files[0];
          if(!file) return;
          if(file.size > 1000000) throw Error("Maximum file size is 1 MB.");
          const parsed = JSON.parse(await file.text());
          const list = Array.isArray(parsed) ? parsed : [parsed];
          if(!list.length) throw Error("JSON contains no problems.");
          for(const d of list) {
            if(typeof d.title !== "string" || !Array.isArray(d.testCases) || !Array.isArray(d.examples)) {
              throw Error("Each question must contain title, examples and testCases.");
            }
          }
          set(list);
        } catch(e) { fail(e.message); }
      }}/>
      {items && (
        <div style={{marginTop:'12px', background:'#fff', padding:'12px', borderRadius:'6px', border:'1px solid #cbd5e1'}}>
          <h3>{items.length === 1 ? items[0].title : `${items.length} Questions Ready to Insert`}</h3>
          <ul style={{margin:'8px 0 12px 20px', padding:0}}>
            {items.map((doc, idx) => (
              <li key={idx}>
                <strong>{doc.title}</strong> <small style={{color:'#64748b'}}>({doc.id || 'No ID'})</small> · {doc.difficulty || 'Normal'} · {doc.scoring?.maxScore ?? 100} pts
                ({doc.testCases?.filter(t => t?.visibility === "public").length} public, {doc.testCases?.filter(t => t?.visibility === "hidden").length} hidden tests)
              </li>
            ))}
          </ul>
          <label style={{display:'block', margin:'10px 0'}}>
            <input type="checkbox" checked={replace} onChange={e => toggle(e.target.checked)}/> Replace existing question(s) with matching IDs if already added
          </label>
          <div className="actions" style={{display:'flex', gap:'8px'}}>
            <button disabled={busy} onClick={async () => {
              wait(true);
              try {
                await api('/api/organizer/' + cid + '/problems' + (replace ? '?replace=1' : ''), items.length === 1 ? items[0] : items);
                onDone();
              } catch(e) { fail(e.message); } finally { wait(false); }
            }}>Confirm import ({items.length} question{items.length > 1 ? 's' : ''})</button>
            <button type="button" className="secondary" onClick={onDone}>Cancel</button>
          </div>
        </div>
      )}
      {err && <p role="alert" style={{color:'#9c2940'}}>{err}</p>}
      {!items && <button type="button" className="secondary" style={{marginTop:'10px'}} onClick={onDone}>Cancel</button>}
    </section>
  );
}

function JobRow({j}) {
  const [source, show] = useState(null);
  return (
    <details onToggle={async e => {
      if(e.target.open && source === null) {
        try { show((await api('/api/organizer/jobs/' + j.id)).source); } catch(err) { show(err.message); }
      }
    }}>
      <summary>{j.entry__display} · {j.problem__title} · {j.language} · {j.verdict}</summary>
      <pre>{source ?? 'Loading…'}</pre>
    </details>
  );
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
      setTimeout(() => location.reload(), 1200);
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
      <h2>E-Code Cloud Integration & Readiness</h2>
      
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
        <p>Preview JSON payload and synchronize finalized standings back to the E-Code cloud server.</p>
        
        <div style={{display:'flex', gap:'10px', marginTop:'10px', flexWrap:'wrap', alignItems:'center'}}>
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
          <EcodeTransfer url={'/api/organizer/' + cid + '/publish'} publish onComplete={() => setMsg('Standings successfully published to E-Code!')}/>
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

function BankManager() {
  const [bank, setBank] = useState(null), [err, fail] = useState(""), [busy, wait] = useState(false), [uploading, setUploading] = useState(false), [msg, setMsg] = useState("");
  const [filter, setFilter] = useState("");
  function load() { api("/api/organizer/bank").then(d => setBank(d.questions)).catch(e => fail(e.message)); }
  useEffect(() => { load(); }, []);
  const filtered = (bank || []).filter(q => !filter || (q.title + q.externalId + q.fromContest).toLowerCase().includes(filter.toLowerCase()));
  return (
    <div style={{display:"flex", flexDirection:"column", gap:"16px"}}>
      <div className="bar">
        <div>
          <h2>Master Question Bank ({bank ? bank.length : "…"})</h2>
          <p style={{margin:"4px 0", color:"#64748b"}}>
            Permanent repository of questions with test cases and type signatures. Questions are never deleted when contests are removed, and remain completely hidden from students until imported.
          </p>
        </div>
        <div style={{display:"flex", gap:"8px"}}>
          <a href="/static/question-example.json" download className="button secondary">⬇ LeetCode Example</a>
          <button onClick={() => setUploading(!uploading)}>{uploading ? "Close Upload" : "+ Bulk Upload Questions"}</button>
        </div>
      </div>
      {msg && <div className="alert" role="status" style={{background:"#ecfdf5", color:"#065f46"}}>{msg}</div>}
      {err && <p role="alert" style={{color:"#9c2940"}}>{err}</p>}
      {uploading && (
        <div style={{background:"#f8fafc", border:"1px solid #cbd5e1", borderRadius:"8px", padding:"16px"}}>
          <h3>Upload Bulk Question JSON (LeetCode Format)</h3>
          <p style={{fontSize:"0.9rem", color:"#64748b"}}>Upload a JSON array <code>[...]</code> of questions matching the LeetCode format.</p>
          <input type="file" accept=".json" onChange={async e => {
            const file = e.target.files[0]; if(!file) return;
            try {
              const data = JSON.parse(await file.text());
              const list = Array.isArray(data) ? data : [data];
              wait(true); setMsg(""); fail("");
              const res = await api("/api/organizer/bank/upload", list);
              setMsg("Successfully added " + res.count + " question(s) to Question Bank!");
              setUploading(false);
              load();
            } catch(e) { fail(e.message); } finally { wait(false); }
          }}/>
        </div>
      )}
      <div>
        <input placeholder="Filter questions by title or ID..." value={filter} onChange={e => setFilter(e.target.value)} style={{maxWidth:"360px", marginBottom:"12px"}}/>
        {bank === null ? <p>Loading bank…</p> : !filtered.length ? <p>No questions found in bank.</p> : (
          <div style={{display:"grid", gap:"10px", maxHeight:"500px", overflowY:"auto"}}>
            {filtered.map(q => (
              <div key={q.id} style={{background:"#fff", padding:"14px", borderRadius:"8px", border:"1px solid #e2e8f0", display:"flex", justifyContent:"space-between", alignItems:"center"}}>
                <div>
                  <div style={{display:"flex", gap:"8px", alignItems:"center"}}>
                    <strong>{q.title}</strong>
                    <span className="pill" style={{background:"#f1f5f9", color:"#475569"}}>{q.externalId}</span>
                    <span className="pill" style={{background:q.difficulty === "Easy" ? "#dcfce7" : q.difficulty === "Medium" ? "#fef9c3" : "#fee2e2", color:"#1e293b"}}>{q.difficulty}</span>
                  </div>
                  <div style={{fontSize:"0.85rem", color:"#64748b", marginTop:"4px"}}>
                    Function: <code>{q.function || "solve"}</code> · {q.maxScore} pts · {q.testCount} tests · <em>Source: {q.fromContest}</em>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ConnectionMonitor({rows, events}) {
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState('All');
  const [search, setSearch] = useState('');

  const filtered = rows.filter(r => {
    const matchesSearch = (r.name + ' ' + r.enrollment).toLowerCase().includes(search.toLowerCase());
    if(!matchesSearch) return false;
    if(filter === 'All') return true;
    if(filter === 'Online') return r.presence === 'Online';
    if(filter === 'Disconnected') return r.presence === 'Disconnected';
    if(filter === 'Unstable') return r.presence === 'Unstable';
    return true;
  });

  const participantEvents = selected ? events.filter(e => e.entry__id === selected.id || e.entry__display === selected.name) : [];

  return (
    <div>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', flexWrap:'wrap', gap:'12px', marginBottom:'16px'}}>
        <div>
          <h2 style={{margin:'0 0 4px 0'}}>Live Member Connection Status</h2>
          <p style={{margin:0, fontSize:'0.88rem', color:'#64748b'}}>
            Color-coded live connectivity status. Click any candidate card to inspect exact disconnects and timestamp logs.
          </p>
        </div>
        <div style={{display:'flex', gap:'8px'}}>
          <input
            placeholder="Search candidate..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{padding:'6px 12px', borderRadius:'6px', border:'1px solid #cbd5e1', fontSize:'0.85rem'}}
          />
          <select
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={{padding:'6px 12px', borderRadius:'6px', border:'1px solid #cbd5e1', fontSize:'0.85rem'}}
          >
            <option value="All">All ({rows.length})</option>
            <option value="Online">Online ({rows.filter(r => r.presence === 'Online').length})</option>
            <option value="Unstable">Unstable ({rows.filter(r => r.presence === 'Unstable').length})</option>
            <option value="Disconnected">Disconnected ({rows.filter(r => r.presence === 'Disconnected').length})</option>
          </select>
        </div>
      </div>

      <div style={{display:'grid', gridTemplateColumns:selected ? '1fr 340px' : '1fr', gap:'16px', alignItems:'start'}}>
        {/* Left: Participant Cards Grid */}
        <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(280px, 1fr))', gap:'12px'}}>
          {filtered.map(r => {
            const isOnline = r.presence === 'Online';
            const isUnstable = r.presence === 'Unstable';
            const statusColor = isOnline ? '#10b981' : isUnstable ? '#f59e0b' : '#ef4444';
            const statusBg = isOnline ? '#ecfdf5' : isUnstable ? '#fffbeb' : '#fef2f2';
            const isPicked = selected?.id === r.id;

            return (
              <div
                key={r.id}
                onClick={() => setSelected(isPicked ? null : r)}
                style={{
                  background: isPicked ? '#f8fafc' : '#ffffff',
                  border: isPicked ? '2px solid #6366f1' : '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '14px 16px',
                  cursor: 'pointer',
                  boxShadow: isPicked ? '0 4px 12px rgba(99,102,241,0.12)' : '0 1px 3px rgba(0,0,0,0.03)',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start'}}>
                  <div>
                    <strong style={{fontSize:'0.95rem', color:'#1e293b', display:'block'}}>{r.name}</strong>
                    <span style={{fontSize:'0.8rem', color:'#64748b'}}>{r.enrollment}</span>
                  </div>
                  <span style={{
                    display:'inline-flex',
                    alignItems:'center',
                    gap:'6px',
                    fontSize:'0.75rem',
                    fontWeight:600,
                    padding:'3px 9px',
                    borderRadius:'12px',
                    background: statusBg,
                    color: statusColor,
                    border: `1px solid ${statusColor}33`
                  }}>
                    <span style={{width:'7px', height:'7px', borderRadius:'50%', background:statusColor}}/>
                    {r.presence}
                  </span>
                </div>

                <div style={{display:'flex', justifyContent:'space-between', marginTop:'14px', paddingTop:'10px', borderTop:'1px solid #f1f5f9', fontSize:'0.82rem', color:'#64748b'}}>
                  <div>
                    Reconnects: <strong style={{color: r.reconnects > 2 ? '#ef4444' : '#1e293b'}}>{r.reconnects}</strong>
                  </div>
                  <div>
                    {r.last ? `Last seen: ${clock(r.last)}` : 'Not joined yet'}
                  </div>
                </div>
              </div>
            );
          })}
          {!filtered.length && <p style={{color:'#64748b', padding:'20px 0'}}>No matching participants found.</p>}
        </div>

        {/* Right: Selected Member Detail Drawer */}
        {selected && (
          <div style={{
            background:'#ffffff',
            border:'1px solid #cbd5e1',
            borderRadius:'10px',
            padding:'18px',
            boxShadow:'0 4px 14px rgba(0,0,0,0.06)',
            position:'sticky',
            top:'20px'
          }}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'14px'}}>
              <div>
                <h3 style={{margin:'0 0 2px 0', fontSize:'1.1rem'}}>{selected.name}</h3>
                <span style={{fontSize:'0.82rem', color:'#64748b'}}>{selected.enrollment} · @{selected.username}</span>
              </div>
              <button
                className="link"
                style={{color:'#64748b', fontSize:'1.2rem', padding:'0 4px', lineHeight:1}}
                onClick={() => setSelected(null)}
              >
                ✕
              </button>
            </div>

            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'10px', marginBottom:'16px'}}>
              <div style={{background:'#f8fafc', padding:'10px', borderRadius:'6px', border:'1px solid #e2e8f0'}}>
                <span style={{fontSize:'0.75rem', color:'#64748b', display:'block'}}>Current State</span>
                <strong style={{
                  color: selected.presence === 'Online' ? '#10b981' : selected.presence === 'Unstable' ? '#f59e0b' : '#ef4444'
                }}>{selected.presence}</strong>
              </div>
              <div style={{background:'#f8fafc', padding:'10px', borderRadius:'6px', border:'1px solid #e2e8f0'}}>
                <span style={{fontSize:'0.75rem', color:'#64748b', display:'block'}}>Total Disconnects</span>
                <strong style={{color: selected.reconnects > 2 ? '#ef4444' : '#1e293b'}}>{selected.reconnects} times</strong>
              </div>
              <div style={{background:'#f8fafc', padding:'10px', borderRadius:'6px', border:'1px solid #e2e8f0'}}>
                <span style={{fontSize:'0.75rem', color:'#64748b', display:'block'}}>Connected Time</span>
                <strong>{selected.connectedSeconds != null ? `${selected.connectedSeconds}s` : '—'}</strong>
              </div>
              <div style={{background:'#f8fafc', padding:'10px', borderRadius:'6px', border:'1px solid #e2e8f0'}}>
                <span style={{fontSize:'0.75rem', color:'#64748b', display:'block'}}>Submissions</span>
                <strong>{selected.submits || 0}</strong>
              </div>
            </div>

            <h4 style={{fontSize:'0.9rem', margin:'14px 0 8px 0', color:'#334155'}}>Recent Activity Timeline</h4>
            <div style={{maxHeight:'240px', overflowY:'auto', display:'flex', flexDirection:'column', gap:'8px'}}>
              {participantEvents.map(e => (
                <div key={e.id} style={{fontSize:'0.82rem', display:'flex', justifyContent:'space-between', padding:'6px 8px', borderRadius:'4px', background:'#f1f5f9'}}>
                  <span style={{color: e.kind === 'Connected' || e.kind === 'Reconnected' ? '#059669' : '#dc2626', fontWeight:500}}>
                    {e.kind === 'Heartbeat lost' ? '⚠️ Disconnected / Heartbeat lost' : '✅ ' + e.kind}
                  </span>
                  <span style={{color:'#64748b'}}>{clock(e.at)}</span>
                </div>
              ))}
              {!participantEvents.length && <p style={{fontSize:'0.8rem', color:'#94a3b8', margin:0}}>No connection logs for this member.</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Decision({row, done}) {
  const [open, toggle] = useState(false), [err, fail] = useState('');
  return open ? (
    <form onSubmit={async e => {
      e.preventDefault();
      try {
        await postForm('/api/organizer/entries/' + row.id + '/eligibility', new FormData(e.target));
        toggle(false);
        done();
      } catch(e) { fail(e.message); }
    }}>
      <input type="hidden" name="action" value={row.eligible ? 'disqualify' : 'reinstate'}/>
      <input aria-label="Decision reason" name="reason" required maxLength={800} placeholder="Decision reason"/>
      <button>Confirm</button>
      <button type="button" className="link" onClick={() => toggle(false)}>Cancel</button>
      {err}
    </form>
  ) : (
    <button className="link" onClick={() => toggle(true)}>{row.eligible ? 'Disqualify' : 'Reinstate'}</button>
  );
}

function CreateContestModal({onClose, onCreated}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [duration, setDuration] = useState(60);
  const [stage, setStage] = useState('Waiting Room');
  const [starts, setStarts] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if(!title.trim()) { setErr("Contest title is required."); return; }
    setBusy(true);
    setErr('');
    try {
      const res = await api('/api/organizer/contests', {
        title: title.trim(),
        description: description.trim(),
        durationMinutes: Number(duration) || 60,
        stage: stage,
        starts: starts || undefined
      });
      onCreated(res.id);
    } catch(e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{position:'fixed', inset:0, background:'rgba(15,23,42,0.6)', backdropFilter:'blur(4px)', display:'grid', placeItems:'center', zIndex:1000, padding:'16px'}}>
      <div style={{background:'#fff', borderRadius:'12px', padding:'24px', maxWidth:'520px', width:'100%', boxShadow:'0 20px 25px -5px rgba(0,0,0,0.1)'}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
          <h2 style={{margin:0, fontSize:'1.3rem'}}>Create / Schedule New Contest</h2>
          <button className="link" onClick={onClose} style={{fontSize:'1.2rem', color:'#64748b'}}>✕</button>
        </div>
        {err && <div role="alert" style={{background:'#fef2f2', color:'#991b1b', padding:'10px', borderRadius:'6px', marginBottom:'12px'}}>{err}</div>}
        <form onSubmit={handleSubmit} style={{display:'flex', flexDirection:'column', gap:'14px'}}>
          <div>
            <label style={{display:'block', fontWeight:600, fontSize:'0.9rem', marginBottom:'4px'}}>Contest Title *</label>
            <input 
              required 
              placeholder="e.g. Code Clash 2.0 | Weekly Elimination Round" 
              value={title} 
              onChange={e => setTitle(e.target.value)}
              style={{width:'100%'}}
            />
          </div>
          <div>
            <label style={{display:'block', fontWeight:600, fontSize:'0.9rem', marginBottom:'4px'}}>Description / Instructions</label>
            <textarea 
              rows={3} 
              placeholder="Rules, batch target, or round information..." 
              value={description} 
              onChange={e => setDescription(e.target.value)}
              style={{width:'100%', borderRadius:'6px', border:'1px solid #cbd5e1', padding:'8px', fontFamily:'inherit'}}
            />
          </div>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'12px'}}>
            <div>
              <label style={{display:'block', fontWeight:600, fontSize:'0.9rem', marginBottom:'4px'}}>Duration (minutes)</label>
              <input 
                type="number" 
                min={5} 
                max={600} 
                value={duration} 
                onChange={e => setDuration(e.target.value)}
                style={{width:'100%'}}
              />
            </div>
            <div>
              <label style={{display:'block', fontWeight:600, fontSize:'0.9rem', marginBottom:'4px'}}>Initial Stage</label>
              <select value={stage} onChange={e => setStage(e.target.value)} style={{width:'100%'}}>
                <option value="Waiting Room">Waiting Room (Open for LAN entry)</option>
                <option value="Scheduled">Scheduled (Future date/time)</option>
                <option value="Draft">Draft (Hidden)</option>
              </select>
            </div>
          </div>
          {stage === 'Scheduled' && (
            <div>
              <label style={{display:'block', fontWeight:600, fontSize:'0.9rem', marginBottom:'4px'}}>Scheduled Start Time</label>
              <input 
                type="datetime-local" 
                value={starts} 
                onChange={e => setStarts(e.target.value)}
                style={{width:'100%'}}
              />
            </div>
          )}
          <div style={{display:'flex', justifyContent:'flex-end', gap:'10px', marginTop:'12px'}}>
            <button type="button" className="secondary" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create Contest'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FetchContestModal({onClose, onFetched}) {
  const [targetCid, setTargetCid] = useState('');
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function handleFetch(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const res = await api('/api/organizer/contest/fetch', {
        contestId: targetCid.trim() || undefined,
        force: force
      });
      onFetched(res.contest.id);
    } catch(e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{position:'fixed', inset:0, background:'rgba(15,23,42,0.6)', backdropFilter:'blur(4px)', display:'grid', placeItems:'center', zIndex:1000, padding:'16px'}}>
      <div style={{background:'#fff', borderRadius:'12px', padding:'24px', maxWidth:'480px', width:'100%', boxShadow:'0 20px 25px -5px rgba(0,0,0,0.1)'}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'16px'}}>
          <h2 style={{margin:0, fontSize:'1.3rem'}}>Fetch Contest from E-Code Cloud</h2>
          <button className="link" onClick={onClose} style={{fontSize:'1.2rem', color:'#64748b'}}>✕</button>
        </div>
        <p style={{fontSize:'0.9rem', color:'#64748b', margin:'0 0 14px 0'}}>
          Connect to <code>https://ecode-backend.onrender.com</code> to import official contest details, banner, roster, and question specifications.
        </p>
        {err && <div role="alert" style={{background:'#fef2f2', color:'#991b1b', padding:'10px', borderRadius:'6px', marginBottom:'12px'}}>{err}</div>}
        <form onSubmit={handleFetch} style={{display:'flex', flexDirection:'column', gap:'14px'}}>
          <div>
            <label style={{display:'block', fontWeight:600, fontSize:'0.9rem', marginBottom:'4px'}}>E-Code Contest ID (Optional)</label>
            <input 
              placeholder="Leave empty to fetch current active contest" 
              value={targetCid} 
              onChange={e => setTargetCid(e.target.value)}
              style={{width:'100%'}}
            />
            <small style={{color:'#64748b', display:'block', marginTop:'4px'}}>Example: <code>YJQAc3fZaKPD2Gyz6AYm</code></small>
          </div>
          <label style={{display:'flex', alignItems:'center', gap:'8px', cursor:'pointer', fontSize:'0.9rem'}}>
            <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)}/>
            Force re-fetch even if contest already exists locally
          </label>
          <div style={{display:'flex', justifyContent:'flex-end', gap:'10px', marginTop:'12px'}}>
            <button type="button" className="secondary" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="submit" disabled={busy}>{busy ? 'Connecting to E-Code…' : 'Fetch & Sync'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function Organizer({session}) {
  const [contests, setContests] = useState(session.contests || []);
  const [cid, pick] = useState(Number(new URLSearchParams(location.search).get('contest')) || session.contests[0]?.id);
  const [data, load] = useState(null);
  const [tab, select] = useState('Problems');
  const [notice, notify] = useState('');
  const [err, fail] = useState('');
  const [form, setForm] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showFetchModal, setShowFetchModal] = useState(false);
  const [refetchingId, setRefetchingId] = useState(null);

  const cursor = useRef(null);

  async function reloadContests(selectId) {
    try {
      const s = await api('/api/session');
      setContests(s.contests || []);
      if (selectId) pick(selectId);
    } catch(e) {}
  }

  useEffect(() => {
    cursor.current = null;
    notify('');
    load(null);
    if (!cid) return;
    let live = true;
    const poll = async () => {
      try {
        const d = await api('/api/organizer/' + cid);
        if (!live) return;
        const alerts = d.events.filter(v => v.kind === 'Heartbeat lost' && cursor.current !== null && v.id > cursor.current);
        if (alerts.length) notify(alerts.map(v => v.entry__display).join(', ') + ' · workspace heartbeat lost');
        cursor.current = d.events[0]?.id || 0;
        load(d);
        fail('');
      } catch(e) {
        if (live) fail(e.message);
      }
    };
    poll();
    const t = setInterval(poll, 4000);
    return () => { live = false; clearInterval(t); };
  }, [cid, form]);

  const [query, search] = useState(''), [status, filter] = useState('All'), [order, sort] = useState('name');
  const visible = (data?.rows || []).filter(r => [r.name, r.enrollment, r.username].join(' ').toLowerCase().includes(query.toLowerCase()) && (status === 'All' || (status === 'Disqualified' ? !r.eligible : r.presence === status))).sort((a,b) => order === 'name' ? a.name.localeCompare(b.name) : b.submits - a.submits);
  
  const contest = contests.find(x => x.id === cid);

  const metrics = [
    ['Registered entries', data?.rows.length, '#5a4abc'],
    ['Online in workspace', data?.rows.filter(v => v.presence === 'Online').length, '#087a65'],
    ['Unstable', data?.rows.filter(v => v.presence === 'Unstable').length, '#98651a'],
    ['Disqualified', data?.rows.filter(v => !v.eligible).length, '#9c2940'],
    ['Disconnected', data?.rows.filter(v => v.presence === 'Disconnected').length, '#b04c28'],
    ['Reconnected participants', data?.rows.filter(v => v.reconnects > 0).length, '#126a62'],
    ['Active judge jobs', data?.activeJobs, '#485480'],
    ['Official submissions', data?.submissions, '#34689e']
  ];

  async function handleDeleteContest(c) {
    if (c.title === "Question Bank Repository" || c.id === 10) {
      alert("The Question Bank Repository is permanently protected and cannot be deleted.");
      return;
    }
    if (!window.confirm(`Are you sure you want to delete "${c.title}"?\n\nThis will remove this contest and all its participant entries & submissions.\n(Questions will remain safely preserved in the Master Question Bank).`)) {
      return;
    }
    try {
      await api('/api/organizer/' + c.id + '/delete', {});
      notify(`Contest "${c.title}" has been deleted.`);
      const remaining = contests.filter(x => x.id !== c.id);
      setContests(remaining);
      if (cid === c.id) {
        pick(remaining[0]?.id || null);
      }
    } catch(e) {
      fail(e.message);
    }
  }

  async function handleRefetchContest(c) {
    setRefetchingId(c.id);
    fail('');
    try {
      const res = await api('/api/organizer/contest/fetch', {
        contestId: c.ecodeContestId || undefined,
        force: true
      });
      notify(`Successfully refetched "${res.contest.title}" from E-Code!`);
      await reloadContests(c.id);
    } catch(e) {
      fail("Failed to refetch: " + e.message);
    } finally {
      setRefetchingId(null);
    }
  }

  return (
    <>
      {/* Top Header */}
      <div className="page-heading" style={{alignItems:'flex-start', flexWrap:'wrap', gap:'16px'}}>
        <div>
          <h1 style={{fontSize:'2.2rem', margin:0}}>Organizer Arena Control</h1>
          <p style={{margin:'6px 0 0 0', color:'#64748b'}}>
            Schedule contests, manage offline LAN rounds, monitor live connections, and sync results with E-Code Cloud.
          </p>
        </div>
        <div style={{display:'flex', gap:'10px', flexWrap:'wrap'}}>
          <button onClick={() => setShowCreateModal(true)}>+ Create / Schedule Contest</button>
          <button className="secondary" onClick={() => setShowFetchModal(true)}>☁️ Fetch from E-Code</button>
          <button className="secondary" onClick={() => select('Question Bank')}>📚 Master Question Bank</button>
        </div>
      </div>

      {err && <div role="alert" className="alert" style={{background:'#fef2f2', color:'#991b1b', border:'1px solid #fecaca'}}>{err} <button className="link" onClick={() => fail('')}>✕</button></div>}
      {notice && <div role="alert" className="alert" style={{background:'#ecfdf5', color:'#065f46', border:'1px solid #a7f3d0'}}>{notice} <button className="link" onClick={() => notify('')}>Dismiss</button></div>}

      {/* Contest Management Overview Section */}
      <section style={{marginBottom:'24px'}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'12px'}}>
          <h2 style={{fontSize:'1.15rem', color:'#1e293b', margin:0}}>Available Contests ({contests.length})</h2>
          <span style={{fontSize:'0.85rem', color:'#64748b'}}>Select a contest below to inspect participants, problems, and connection events</span>
        </div>

        <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(340px, 1fr))', gap:'14px'}}>
          {contests.map(c => {
            const isSelected = c.id === cid;
            const isEcode = Boolean(c.ecodeContestId);
            const isProtected = c.title === "Question Bank Repository" || c.id === 10;

            return (
              <div 
                key={c.id}
                style={{
                  background: isSelected ? '#faf5ff' : '#ffffff',
                  border: isSelected ? '2px solid #7c3aed' : '1px solid #e2e8f0',
                  borderRadius:'12px',
                  padding:'16px',
                  boxShadow: isSelected ? '0 4px 14px rgba(124,58,237,0.1)' : '0 1px 3px rgba(0,0,0,0.04)',
                  display:'flex',
                  flexDirection:'column',
                  justifyContent:'space-between',
                  gap:'12px',
                  transition:'all 0.15s ease'
                }}
              >
                <div>
                  <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'8px'}}>
                    <strong style={{fontSize:'1.05rem', color:'#1e293b', lineHeight:1.3}}>{c.title}</strong>
                    <span className={'pill ' + c.state} style={{flexShrink:0}}>{c.state}</span>
                  </div>
                  
                  {isEcode && (
                    <div style={{marginTop:'6px', display:'flex', gap:'6px', alignItems:'center', flexWrap:'wrap'}}>
                      <span className="pill" style={{background:'#e0e7ff', color:'#3730a3', fontSize:'0.72rem'}}>
                        ☁️ E-Code: {c.ecodeContestId}
                      </span>
                      {c.syncStatus && (
                        <span className="pill" style={{background:'#f1f5f9', color:'#475569', fontSize:'0.72rem'}}>
                          {c.syncStatus}
                        </span>
                      )}
                    </div>
                  )}

                  <div style={{fontSize:'0.82rem', color:'#64748b', marginTop:'10px', display:'flex', flexDirection:'column', gap:'3px'}}>
                    <div>⏱ Duration: <strong>{c.duration} mins</strong> · Problems: <strong>{c.problemCount ?? c.totalProblems ?? '—'}</strong></div>
                    <div>Window: {clock(c.starts)} – {clock(c.ends)}</div>
                  </div>
                </div>

                {/* Card Action Buttons */}
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', borderTop:'1px solid #f1f5f9', paddingTop:'10px', gap:'6px', flexWrap:'wrap'}}>
                  <button 
                    onClick={() => { pick(c.id); }}
                    style={{
                      background: isSelected ? '#7c3aed' : '#f1f5f9',
                      color: isSelected ? '#fff' : '#1e293b',
                      border: 'none',
                      padding:'6px 14px',
                      fontSize:'0.85rem'
                    }}
                  >
                    {isSelected ? 'Selected ✓' : 'Manage Contest ➔'}
                  </button>

                  <div style={{display:'flex', gap:'6px'}}>
                    {isEcode && (
                      <button 
                        className="secondary" 
                        disabled={refetchingId === c.id}
                        onClick={() => handleRefetchContest(c)}
                        title="Refetch latest problems and roster from E-Code"
                        style={{padding:'5px 10px', fontSize:'0.78rem'}}
                      >
                        {refetchingId === c.id ? 'Refetching…' : '🔄 Refetch'}
                      </button>
                    )}
                    
                    {!isProtected ? (
                      <button 
                        className="secondary" 
                        onClick={() => handleDeleteContest(c)}
                        title="Delete contest"
                        style={{padding:'5px 10px', fontSize:'0.78rem', color:'#dc2626', borderColor:'#fca5a5'}}
                      >
                        🗑 Delete
                      </button>
                    ) : (
                      <span className="pill" style={{background:'#e2e8f0', color:'#475569', fontSize:'0.72rem'}}>Protected</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Selected Contest Workspace Panel */}
      {contest && (
        <section className="contestbar" style={{margin:'20px 0 16px 0', borderRadius:'12px'}}>
          <div>
            <span style={{fontSize:'0.78rem', textTransform:'uppercase', letterSpacing:'0.05em', color:'#c4b5fd', fontWeight:600}}>Active Contest Workspace</span>
            <h2 style={{margin:'2px 0 4px 0', fontSize:'1.4rem', color:'#fff'}}>{contest.title}</h2>
            <small style={{color:'#d8d3ed'}}>
              Stage: <strong>{contest.state}</strong> · Duration: {contest.duration} mins · Ends {clock(contest.ends)}
            </small>
          </div>
          
          <div style={{display:'flex', gap:'10px', alignItems:'center', flexWrap:'wrap'}}>
            {({"Draft":"Scheduled","Scheduled":"Waiting Room","Waiting Room":"Active","Live":"Ended"})[contest.state] && (
              <button onClick={async () => {
                const f = new FormData();
                f.set("stage", ({"Draft":"Scheduled","Scheduled":"Waiting Room","Waiting Room":"Active","Live":"Ended"})[contest.state]);
                try {
                  await postForm("/api/organizer/" + cid + "/stage", f);
                  reloadContests(cid);
                } catch(e) { fail(e.message); }
              }}>
                {{ "Draft":"Schedule Round", "Scheduled":"Open Waiting Room", "Waiting Room":"Start Round", "Live":"End Round" }[contest.state]}
              </button>
            )}

            {(contest.state === "Ended" || new Date(contest.ends) <= new Date()) && (
              <button className="secondary" onClick={async () => {
                if(!window.confirm("Restart this contest and return it to Waiting Room with fresh duration?")) return;
                const f = new FormData();
                f.set("stage", "Waiting Room");
                try {
                  await postForm("/api/organizer/" + cid + "/stage", f);
                  reloadContests(cid);
                } catch(e) { fail(e.message); }
              }}>
                Restart Contest
              </button>
            )}

            {contest.ecodeContestId && (
              <button 
                className="secondary" 
                disabled={refetchingId === contest.id}
                onClick={() => handleRefetchContest(contest)}
              >
                {refetchingId === contest.id ? 'Refetching…' : '🔄 Refetch E-Code'}
              </button>
            )}

            <button 
              className="secondary" 
              onClick={() => handleDeleteContest(contest)}
              style={{color:'#fca5a5', borderColor:'#fca5a5'}}
            >
              🗑 Delete Contest
            </button>
          </div>
        </section>
      )}

      {/* Metrics Bar for Selected Contest */}
      {data && cid && (
        <section className="metrics">
          {metrics.map(([label, n, color]) => (
            <div key={label} style={{'--accent': color}}>
              <span>{label}</span>
              <strong>{n ?? '—'}</strong>
            </div>
          ))}
        </section>
      )}

      {/* Sub Tabs for Contest Workspace */}
      <div className="tabs" role="tablist">
        {['Problems', 'Connection events', 'Participants', 'Standings & Publish', 'Submissions', 'E-Code Cloud', 'Question Bank'].map(t => (
          <button role="tab" aria-selected={tab === t} key={t} onClick={() => { select(t); setForm(''); }}>
            {t}
          </button>
        ))}
      </div>

      {/* Tab Panels */}
      {tab === 'Question Bank' && (
        <section className="card panel">
          <BankManager/>
        </section>
      )}

      {data && cid && (
        <section className="card panel">
          {/* Problems Tab */}
          {tab === 'Problems' && (
            <>
              <div className="bar">
                <div>
                  <h2 style={{margin:0}}>Contest Problems ({data.problems?.length || 0})</h2>
                  <p style={{margin:'4px 0 0 0', fontSize:'0.88rem', color:'#64748b'}}>
                    Problems assigned to this contest. Removing a problem removes it from this contest only; it remains safely in the Master Question Bank.
                  </p>
                </div>
                <div style={{display:'flex', gap:'8px'}}>
                  <button className="secondary" onClick={() => setForm(form === 'bank' ? '' : 'bank')}>Import from Question Bank</button>
                  <button onClick={() => setForm(form === 'problem' ? '' : 'problem')}>+ Add Problem (JSON)</button>
                </div>
              </div>

              {form === 'bank' ? (
                <BankPicker cid={cid} onDone={() => setForm('')}/>
              ) : form === 'problem' ? (
                <Author cid={cid} onDone={() => setForm('')}/>
              ) : (
                data.problems?.map(p => (
                  <div className="event" key={p.id} style={{display:'flex', justifyContent:'space-between', alignItems:'center', padding:'12px 14px', background:'#fff', border:'1px solid #e2e8f0', borderRadius:'8px', marginBottom:'8px'}}>
                    <div>
                      <b style={{fontSize:'1rem', color:'#1e293b'}}>{p.title}</b>
                      <span className="pill" style={{marginLeft:'10px', background: p.published ? '#ecfdf5' : '#fef2f2', color: p.published ? '#059669' : '#dc2626'}}>
                        {p.published ? 'Published' : 'Draft'}
                      </span>
                    </div>
                    <button
                      className="secondary"
                      style={{padding:'4px 12px', fontSize:'0.82rem', color:'#dc2626', borderColor:'#fca5a5'}}
                      onClick={async () => {
                        if(!window.confirm(`Remove "${p.title}" from this contest? (It will remain safely preserved in the Question Bank)`)) return;
                        try {
                          await postForm(`/api/organizer/${cid}/problems/${p.id}/remove`, new FormData());
                          api('/api/organizer/' + cid).then(load);
                        } catch(e) { fail(e.message); }
                      }}
                    >
                      🗑 Remove from Contest
                    </button>
                  </div>
                ))
              )}
              {!data.problems?.length && !form && (
                <p style={{padding:'20px 0', color:'#64748b', textAlign:'center'}}>
                  No problems added yet. Click &quot;Import from Question Bank&quot; to pick questions, or &quot;+ Add Problem&quot; to upload a JSON file.
                </p>
              )}
            </>
          )}

          {/* Connection Events / Live Status Tab */}
          {tab === 'Connection events' && (
            <ConnectionMonitor rows={data.rows || []} events={data.events || []}/>
          )}

          {/* Participants Tab */}
          {tab === 'Participants' && (
            <>
              <h2>Contest Roster & Eligibility</h2>
              <div className="actions" style={{display:'flex', gap:'10px', marginBottom:'14px'}}>
                <input aria-label="Search entries" placeholder="Search name, username or enrollment..." value={query} onChange={e => search(e.target.value)}/>
                <select aria-label="Connection filter" value={status} onChange={e => filter(e.target.value)}>
                  {['All', 'Online', 'Unstable', 'Disconnected', 'Unknown', 'Disqualified'].map(s => <option key={s}>{s}</option>)}
                </select>
                <select aria-label="Sort entries" value={order} onChange={e => sort(e.target.value)}>
                  <option value="name">Sort by Name</option>
                  <option value="submits">Most Submissions</option>
                </select>
              </div>
              <table>
                <thead>
                  <tr>
                    {['Participant', 'Enrollment', 'Workspace Status', 'Missed Heartbeats', 'Observed Duration', 'Reconnects', 'Last Seen', 'Submits', 'Eligibility'].map(h => <th key={h}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {visible.map(r => (
                    <tr key={r.id}>
                      <td><strong>{r.name}</strong><br/><small style={{color:'#64748b'}}>@{r.username}</small></td>
                      <td>{r.enrollment}</td>
                      <td><span className={'pill ' + r.presence}>{r.presence}</span></td>
                      <td>{r.missed ?? "—"}</td>
                      <td>{r.connectedSeconds == null ? "—" : r.connectedSeconds + " s"}</td>
                      <td>{r.reconnects}</td>
                      <td>{r.last ? clock(r.last) : '—'}</td>
                      <td>{r.submits}</td>
                      <td>
                        {!r.eligible && <strong style={{color:'#dc2626'}}>Disqualified </strong>}
                        {data.final ? (r.eligible ? "Eligible" : "Disqualified") : <Decision row={r} done={() => api("/api/organizer/" + cid).then(load)}/>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.rows?.length && <p style={{padding:'20px 0', color:'#64748b', textAlign:'center'}}>Entries appear when candidates join this contest from the LAN workspace.</p>}
            </>
          )}

          {/* Standings & Publishing Tab */}
          {tab === 'Standings & Publish' && (
            <>
              <div className="bar" style={{alignItems:'center'}}>
                <div>
                  <h2 style={{margin:0}}>Live Standings & Publishing</h2>
                  <p style={{margin:'4px 0 0 0', fontSize:'0.88rem', color:'#64748b'}}>
                    Real-time rankings calculated using score, solves, and elapsed penalty seconds.
                  </p>
                </div>
                <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
                  <a href={'/leaderboard/' + cid + '/'} target="_blank" rel="noreferrer" className="button secondary">Open Projector ↗</a>
                  <a href={'/organizer-export/' + cid} className="button secondary">Download Final JSON</a>
                </div>
              </div>

              {/* Publish to E-Code Server Action Card */}
              <div style={{background:'#f8fafc', padding:'16px', borderRadius:'8px', border:'1px solid #e2e8f0', margin:'16px 0'}}>
                <h3 style={{margin:'0 0 6px 0'}}>Publish Final Standings to E-Code Cloud Server</h3>
                <p style={{fontSize:'0.88rem', color:'#64748b', margin:'0 0 12px 0'}}>
                  Push the official finalized leaderboard, problem scores, and verified student identities back to <code>ecode-backend.onrender.com</code>.
                </p>
                <EcodeTransfer url={"/api/organizer/" + cid + "/publish"} publish onComplete={() => notify('Leaderboard successfully published to E-Code Cloud!')}/>
              </div>

              <div style={{marginTop:'16px'}}>
                <h3>Participant Rankings ({data.scores?.length || 0})</h3>
                {data.scores?.map((s, i) => (
                  <div className="event" key={i} style={{padding:'10px 0'}}>
                    <b>#{s.rank} {s.name}</b>
                    <span>{s.score ?? s.solved} points · {s.solved} solved</span>
                    <time>{s.seconds}s</time>
                  </div>
                ))}
                {!data.scores?.length && <p style={{color:'#64748b', padding:'10px 0'}}>No scores recorded yet.</p>}
              </div>
            </>
          )}

          {/* Submissions Tab */}
          {tab === 'Submissions' && (
            <>
              <h2>Judge Submissions & Audits</h2>
              <p style={{fontSize:'0.88rem', color:'#64748b', margin:'0 0 12px 0'}}>Click any entry to inspect student source code.</p>
              {data.jobs?.map(j => <JobRow key={j.id} j={j}/>)}
              {!data.jobs?.length && <p style={{padding:'20px 0', color:'#64748b', textAlign:'center'}}>No submissions recorded yet for this contest.</p>}
            </>
          )}

          {/* E-Code Cloud Tab */}
          {tab === 'E-Code Cloud' && (
            <EcodeIntegration cid={cid} contest={contest} onRefresh={() => reloadContests(cid)}/>
          )}
        </section>
      )}

      {/* Modals */}
      {showCreateModal && (
        <CreateContestModal 
          onClose={() => setShowCreateModal(false)} 
          onCreated={async (newId) => {
            setShowCreateModal(false);
            notify("Contest created successfully!");
            await reloadContests(newId);
          }}
        />
      )}

      {showFetchModal && (
        <FetchContestModal 
          onClose={() => setShowFetchModal(false)} 
          onFetched={async (newId) => {
            setShowFetchModal(false);
            notify("Contest fetched successfully from E-Code!");
            await reloadContests(newId);
          }}
        />
      )}
    </>
  );
}
