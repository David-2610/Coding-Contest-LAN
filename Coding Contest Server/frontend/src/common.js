export const clock=v=>new Date(v).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
export async function postForm(url,form){
 const token=document.cookie.split('; ').find(v=>v.startsWith('csrftoken='))?.slice(10);
 const r=await fetch(url,{method:'POST',headers:{'X-CSRFToken':token},body:form});
 const d=await r.json();if(!r.ok)throw Error(d.error||'Unable to save');return d;
}
