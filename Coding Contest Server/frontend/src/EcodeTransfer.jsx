import React,{useEffect,useRef,useState} from 'react';
import {api} from './workspace';

export function EcodeTransfer({url, publish=false, onComplete}){
 const [job,setJob]=useState({status:'idle'}),[error,setError]=useState(''),[sending,setSending]=useState(false);
 const callback=useRef(onComplete);
 callback.current=onComplete;
 useEffect(()=>{
   let live=true,timer;
   async function poll(){
     try{
       const next=await api(url);
       if(!live)return;
       setJob(next);setError('');
       if(next.status==='done' && job.status==='running')callback.current?.();
       if(next.status==='running')timer=setTimeout(poll,1500);
     }catch(e){if(live){setError(e.message);timer=setTimeout(poll,4000)}}
   }
   poll();return ()=>{live=false;clearTimeout(timer)};
 },[url,job.status]);
 async function start(){
   if(publish&&!window.confirm('Send these final standings and participant identities to E-Code?'))return;
   setSending(true);
   try{setError('');const next=await api(url,{});setJob(next);if(next.status==='done')callback.current?.()}
   catch(e){setError(e.message)}finally{setSending(false)}
 }
 return <div><button disabled={sending||job.status==='running'||(publish&&job.status==='done')} onClick={start}>{publish?'Send final leaderboard to E-Code':'Refresh roster from E-Code'}</button>
 <p role="status">{error||job.message}</p></div>
}
