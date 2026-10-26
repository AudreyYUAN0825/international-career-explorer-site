let engineWorker;
let requestId=0;
const pending=new Map();
function makeWorker(){
  if(engineWorker)return engineWorker;
  engineWorker=new Worker(new URL('./worker.js?v=1cf1037f0055',document.baseURI),{type:'module'});
  engineWorker.onmessage=({data})=>{const entry=pending.get(data.id);if(!entry)return;clearTimeout(entry.timer);pending.delete(data.id);if(data.diagnostic)console.error(data.diagnostic);entry.resolve({ok:data.ok,json:async()=>data.data});};
  engineWorker.onerror=()=>{for(const entry of pending.values()){clearTimeout(entry.timer);entry.reject(new Error('浏览器未能加载计算组件，请刷新重试'));}pending.clear();engineWorker.terminate();engineWorker=null;};
  return engineWorker;
}
let vacancyFeedPromise;
function publicVacancies(){
  if(!vacancyFeedPromise){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
    vacancyFeedPromise=fetch(new URL('./vacancies.json',document.baseURI),{cache:'no-store',signal:controller.signal}).then(async response=>{
      if(!response.ok)throw new Error('岗位资料暂时无法加载');const feed=await response.json();
      const updated=Date.parse(feed.updated_at);
      if(feed.schema!==1||!Array.isArray(feed.vacancies)||feed.vacancies.length>2000||!Number.isFinite(updated)||Date.now()-updated>48*3600000)throw new Error('岗位资料尚未更新，请通过下方官网入口查看最新招聘。');
      return feed;
    }).catch(error=>{vacancyFeedPromise=null;throw error}).finally(()=>clearTimeout(timer));
  }return vacancyFeedPromise;
}
function apiRequest(path,options={}){
  if(path==='/api/jobs/config')return Promise.resolve({ok:true,json:async()=>({enabled:true,provider:'UN Careers',message:'正在自动筛选 UN Careers 岗位。'})});
  if(path==='/api/jobs')return publicVacancies().then(feed=>engineRequest(path,{...options,body:JSON.stringify({...JSON.parse(options.body),vacancies:feed.vacancies,archived_vacancies:feed.archived_vacancies||[],data_updated_at:feed.updated_at})})).catch(error=>({ok:false,json:async()=>({error:error.name==='AbortError'?'岗位资料加载超时，可以重试。':error.message})}));
  return engineRequest(path,options);
}
function engineRequest(path,options={}){
  return new Promise((resolve,reject)=>{const worker=makeWorker(),id=++requestId;
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('加载超时，请检查网络后刷新重试'));},90000);
    pending.set(id,{resolve,reject,timer});worker.postMessage({id,path,body:options.body});
  });
}
