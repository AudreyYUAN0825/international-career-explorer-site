import { loadPyodide } from './runtime/pyodide.mjs';
let request;
const ready = (async () => {
  const py = await loadPyodide({indexURL:new URL('./runtime/', import.meta.url).href});
  const response = await fetch(new URL('./engine.json?v=12235fca05ec', import.meta.url));
  if (!response.ok) throw new Error('无法加载报告规则');
  const files = await response.json();
  for (const [path, content] of Object.entries(files)) {
    py.FS.mkdirTree(path.slice(0,path.lastIndexOf('/')));
    py.FS.writeFile(path,content,{encoding:'utf8'});
  }
  await py.runPythonAsync("import sys\nsys.path.insert(0, '/app/评分原型')\nfrom bridge import browser_request");
  request = py.globals.get('browser_request');
})();
self.onmessage = async ({data:{id,path,body}}) => {
  try { await ready; self.postMessage({id,...JSON.parse(request(path,body??null))}); }
  catch (error) {self.postMessage({id,ok:false,data:{error:'加载或计算失败，请刷新重试。'},diagnostic:String(error)});}
};
