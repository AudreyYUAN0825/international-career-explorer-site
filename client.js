let engineWorker;
let requestId=0;
const pending=new Map();
function makeWorker(){
  if(engineWorker)return engineWorker;
  engineWorker=new Worker(new URL('./worker.js',document.baseURI),{type:'module'});
  engineWorker.onmessage=({data})=>{const entry=pending.get(data.id);if(!entry)return;clearTimeout(entry.timer);pending.delete(data.id);if(data.diagnostic)console.error(data.diagnostic);entry.resolve({ok:data.ok,json:async()=>data.data});};
  engineWorker.onerror=()=>{for(const entry of pending.values()){clearTimeout(entry.timer);entry.reject(new Error('浏览器未能加载计算组件，请刷新重试'));}pending.clear();engineWorker.terminate();engineWorker=null;};
  return engineWorker;
}
function apiRequest(path,options={}){
  return new Promise((resolve,reject)=>{const worker=makeWorker(),id=++requestId;
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('加载超时，请检查网络后刷新重试'));},90000);
    pending.set(id,{resolve,reject,timer});worker.postMessage({id,path,body:options.body});
  });
}
