let capture=null;
document.getElementById('installation').textContent=`插件已安装并启用（v${chrome.runtime.getManifest().version}）。请在 MKHP 确认连接状态后采集。`;
const status=document.getElementById('status'),captureButton=document.getElementById('capture'),sendButton=document.getElementById('send');
captureButton.addEventListener('click',async()=>{
  capture=null;document.getElementById('preview').hidden=true;captureButton.disabled=true;status.textContent='正在读取当前商品页…';
  try{
    const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
    const [result]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:mhpExtractProduct});
    if(result.error||!result.result)throw new Error(result.error?.message||'页面读取失败，请确认商品页已加载');
    capture=result.result;
    document.getElementById('facts').textContent=Object.entries(capture.fields).map(([k,v])=>`${k}：${v.value}`).join('\n');
    document.getElementById('images').textContent=`候选图片：${capture.image_urls.length} 张（本次最多导入20张）`;
    document.getElementById('preview').hidden=false;status.textContent='已读取。下一步只发送到 MHP 预览，不自动下载图片或调用 AI。';
  }catch(error){status.textContent=error.message}finally{captureButton.disabled=false}
});
sendButton.addEventListener('click',async()=>{
  if(!capture)return;sendButton.disabled=true;
  try{
    const tabs=await chrome.tabs.query({url:chrome.runtime.getManifest().host_permissions});
    if(tabs.length!==1)throw new Error('请在同一个 Edge 浏览器只打开一个 MHP 标签页（云端或本机），登录并进入 MKHP，再点击发送。');
    const [response]=await chrome.scripting.executeScript({target:{tabId:tabs[0].id},args:[capture],func:async(payload)=>{
      const nonce=crypto.randomUUID();
      return await new Promise(resolve=>{
        const timer=setTimeout(()=>{window.removeEventListener('message',receive);resolve(false)},4000);
        function receive(event){if(event.source===window&&event.origin===location.origin&&event.data?.type==='MHP_COLLECTOR_ACK'&&event.data.nonce===nonce){clearTimeout(timer);window.removeEventListener('message',receive);resolve(true)}}
        window.addEventListener('message',receive);window.postMessage({type:'MHP_COLLECTOR_CAPTURE',nonce,payload},location.origin);
      });
    }});
    if(!response?.result)throw new Error('MHP 未接收预览，请登录并打开 MKHP，再重新发送。');
    await chrome.tabs.update(tabs[0].id,{active:true});status.textContent='已送至 MHP 预览，请在那里勾选图片并确认导入。';
  }catch(error){status.textContent=error.message}finally{sendButton.disabled=false}
});
