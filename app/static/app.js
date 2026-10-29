async function api(url,payload){
 const token=document.querySelector('meta[name="csrf-token"]')?.content||'';
 const response=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:JSON.stringify(payload)});
 let data={};try{data=await response.json()}catch{}
 if(!response.ok){let detail=data.detail||`Error HTTP ${response.status}`;if(typeof detail==='object')detail=JSON.stringify(detail);throw new Error(detail)}return data;
}
let toastTimer;
function toast(text,ok=false){let t=document.getElementById('toast');if(!t){alert(text);return}clearTimeout(toastTimer);t.textContent=text;t.className='toast visible'+(ok?' ok':'');toastTimer=setTimeout(()=>{t.className='toast'},4500)}
async function logout(){try{const x=await api('/api/logout',{});location.href=x.redirect}catch(err){toast(err.message)}}
