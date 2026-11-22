import "./editor.css";
import "./portal.css";
import React,{useEffect,useState,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {Workspace,api} from './workspace';
import {Lobby, Login, Roster, GlobalBoard} from './ContestLobby';
import {Organizer} from './organizer';

import {clock,postForm} from './common';
function Leaderboard({cid}){
 const [board,set]=useState(null),[offline,mark]=useState(false);
 useEffect(()=>{const poll=()=>api('/api/contests/'+cid+'/leaderboard').then(b=>{set(b);mark(false)}).catch(()=>mark(true));poll();const t=setInterval(poll,5000);return()=>clearInterval(t)},[cid]);
 return <><div className="page-heading"><div><h1>Leaderboard</h1><p>{board?.contest}</p></div><span>{offline?'Connection lost':board&&'Updated '+clock(board.updated)}</span></div><div className="card"><table><thead><tr>{['Rank','Contestant','Score','Solved','Total time'].map(v=><th key={v}>{v}</th>)}</tr></thead><tbody>{board?.rows.map((r,i)=><tr key={i}><td>{r.rank}</td><td>{r.name}</td><td>{r.score??r.solved}</td><td>{r.solved}</td><td>{Math.floor(r.seconds/60)}m {r.seconds%60}s</td></tr>)}</tbody></table>{board?.rows.length===0&&<p>No entries in this round yet.</p>}</div></>
}
function Site(){
 const [s,set]=useState(null),[err,fail]=useState('');const path=location.pathname;
 useEffect(()=>{api('/api/session').then(set).catch(e=>fail(e.message))},[]);
 if(!s)return <main>{err||'Loading contest site…'}</main>;
 const end=async()=>{try{await postForm('/api/logout',new FormData());location.assign('/logout/')}catch(e){fail(e.message)}};
 const segment=path.split('/')[1],cid=Number(path.split('/')[2]);
 let view;
 if(segment==='login')view=<Login/>;
 else if(segment==='profile' && s.details?.batch)view=<section className="card auth"><span className="eyeline">E-Code profile</span><h1>{s.name}</h1><dl className="dates"><dt>Enrollment</dt><dd>{s.details.enrollment}</dd><dt>Handle</dt><dd>{s.user}</dd><dt>Batch</dt><dd>{s.details.batch}</dd></dl></section>;
 else if(segment==='logout')view=<section className="card auth"><h1>{s.user?'Sign out of this device?':'You’re signed out'}</h1>{s.user?<button onClick={end}>Confirm sign out</button>:<a href="/">Back to contest schedule</a>}</section>;
 else if(segment==='global')view=<GlobalBoard/>;
 else if(segment==='roster')view=s.staff?<Roster/>:<Login/>;
 else if(segment==='organizer')view=s.staff?<Organizer session={s}/>:s.user?<p>Organizer access required.</p>:<Login/>;
 else if(segment==='contests')view=s.user?<Workspace cid={cid}/>:<Login/>;
 else if(segment==='leaderboard')view=<Leaderboard cid={cid}/>;
 else view=<Lobby session={s}/>;
 return <><header className="top"><div className="top-inner"><a className="wordmark" href="/"><img width="42" height="42" src="/static/ecode.jpg" alt="Ecode"/> CodeClash 1.0</a><nav aria-label="Main navigation"><a href="/" aria-current={path==="/"?"page":undefined}>Contests</a>{s.contests.length>0&&<a href={"/leaderboard/"+(cid||s.contests[0].id)+"/"} aria-current={segment==="leaderboard"?"page":undefined}>Standings</a>}<a href="/global/" aria-current={segment==="global"?"page":undefined}>Global rankings</a>{s.staff&&<><a href="/organizer/">Organizer</a><a href="/roster/">Roster</a></>}{s.user?<>{s.photo&&<img className="avatar" src="/api/profile/photo" alt=""/>}{s.staff?<b>{s.user}</b>:<a href="/profile/">{s.name||s.user}</a>}<button className="navbutton" onClick={end}>Sign out</button></>:<a className="navbutton" href="/login/">Sign in</a>}</nav></div></header><main>{err&&<p role="alert">{err}</p>}{view}</main></>
}
createRoot(document.getElementById('root')).render(<Site/>);
