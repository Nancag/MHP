<script setup>
import {computed,ref,onMounted,onUnmounted,nextTick} from 'vue'
import {API_BASE,workspaceRequest} from '../api/client'
import {useAppContext} from '../composables/useAppContext'
import {createCollectorProbe} from '../collectorStatus'
import MKHPQuickGuide from './MKHPQuickGuide.vue'
const emit=defineEmits(['imported']),app=useAppContext()
const guide=ref(null),preview=ref(null),capture=ref(null),selected=ref([]),showImages=ref(false),busy=ref(false),error=ref('')
const installation=ref({state:'checking',version:''})
const installationText=computed(()=>{
  const en=app.locale==='en'
  if(installation.value.state==='installed')return en?`Plugin installed and enabled (v${installation.value.version}). Ready to collect products.`:`插件已安装并启用（v${installation.value.version}），可以开始采集商品。`
  if(installation.value.state==='outdated')return en?`Update extension v${installation.value.version} to v0.3.0, then refresh this page.`:`插件版本为 v${installation.value.version}，请更新至 v0.3.0 后刷新本页。`
  if(installation.value.state==='checking')return en?'Checking plugin connection…':'正在检测插件连接…'
  return en?'Plugin not detected. Install or enable it, refresh this page, then check again. Update older versions to v0.3.0.':'未检测到插件。请安装或启用后刷新本页，再点击“重新检测”；已安装旧版请更新至 v0.3.0。'
})
let probe=null,poll=null
const guideRevision=ref(0)
function checkInstallation(){probe?.check()}
function confirmDownload(event,helper=false){
  const message=helper?'允许下载 Windows 安装辅助工具吗？用途：在你运行并确认后，把插件保存到固定目录并协助打开 Edge 扩展管理页；仍需你手动确认加载。':'允许下载插件 ZIP 吗？用途：由你手动解压并在 Edge 扩展管理页加载。'
  if(!window.confirm(message))event.preventDefault()
}
function checkVisible(){if(!document.hidden)checkInstallation()}
const names={name:'商品名称',description:'商品介绍',price:'价格',price_max:'最高价',currency:'币种',size:'商品尺寸',package_size:'包裹尺寸',material:'材质',width:'宽度',height:'高度',depth:'深度',weight:'重量'}
let requestId='',requestSignature=''
const seenKey=()=>`mhp-collector-guide-v2:${app.user?.user_id||'browser'}`
function openGuide(){guideRevision.value++;guide.value?.showModal()}
function closeGuide(){try{localStorage.setItem(seenKey(),'seen')}catch{}guide.value?.close()}
function receive(event){
  if(event.source!==window||event.origin!==location.origin||event.data?.type!=='MHP_COLLECTOR_CAPTURE')return
  const packet=event.data,payload=packet.payload
  try{
    if(busy.value||typeof packet.nonce!=='string'||packet.nonce.length>64||JSON.stringify(payload).length>150000)return
    if(payload?.version!==1||!payload.fields?.name?.value||!Array.isArray(payload.image_urls)||payload.image_urls.length>100)return
    const source=new URL(payload.source_url)
    if(source.protocol!=='https:'||!['item.taobao.com','detail.tmall.com','mobile.yangkeduo.com','mobile.pinduoduo.com'].includes(source.hostname))return
    const fields={}
    for(const [key,field] of Object.entries(payload.fields)){
      if(!(key in names)||typeof field?.value!=='string'||field.value.length>2000)continue
      fields[key]={value:field.value,evidence:typeof field.evidence==='string'?field.evidence.slice(0,250):'页面候选字段'}
    }
    for(const key of Object.keys(names))if(!fields[key])fields[key]={value:'',evidence:'用户补充（网页未识别）'}
    const images=payload.image_urls.filter(value=>{try{const u=new URL(value);return u.protocol==='https:'&&/(^|\.)(alicdn\.com|taobaocdn\.com|pddpic\.com|yangkeduo\.com)$/.test(u.hostname)}catch{return false}})
    capture.value={version:1,source_url:source.href,fields,image_urls:[...new Set(images)],warnings:['浏览器候选内容需人工核对；缺失字段不推测。']}
    selected.value=[];showImages.value=false;requestId='';requestSignature='';error.value=''
    guide.value?.close();preview.value?.close();preview.value?.showModal()
    window.postMessage({type:'MHP_COLLECTOR_ACK',nonce:packet.nonce},location.origin)
  }catch{}
}
async function save(){
  if(busy.value||!capture.value)return
  const fields=Object.fromEntries(Object.entries(capture.value.fields).filter(([,v])=>v.value.trim()))
  if(!fields.name){error.value='请填写并核对商品名称';return}
  if(!window.confirm(`确认保存这些商品字段，并由后端访问、下载所选${selected.value.length}张图片？将按来源网址归档，不调用AI。`))return
  const data={version:1,source_url:capture.value.source_url,fields,image_urls:selected.value,warnings:capture.value.warnings,confirm_import:true}
  const signature=JSON.stringify(data)
  if(signature!==requestSignature){requestSignature=signature;requestId=crypto.randomUUID()}
  busy.value=true;error.value=''
  try{
    const task=await workspaceRequest('/mkhp/browser-imports','POST',{...data,request_id:requestId})
    preview.value.close();capture.value=null;emit('imported',task.import_id)
  }catch(e){error.value=e.message+'；若连接中断，请先刷新历史核对，避免重复导入。'}finally{busy.value=false}
}
function closePreview(){if(!busy.value){preview.value?.close();capture.value=null}}
onMounted(async()=>{
  window.addEventListener('message',receive)
  probe=createCollectorProbe(window,value=>{installation.value=value})
  checkInstallation()
  window.addEventListener('focus',checkVisible)
  document.addEventListener('visibilitychange',checkVisible)
  poll=window.setInterval(checkVisible,15000)
  await nextTick();try{if(!localStorage.getItem(seenKey()))openGuide()}catch{openGuide()}
})
onUnmounted(()=>{
  window.removeEventListener('message',receive)
  window.removeEventListener('focus',checkVisible)
  document.removeEventListener('visibilitychange',checkVisible)
  window.clearInterval(poll);probe?.dispose()
})
</script>
<template>
  <div class="collector-actions"><strong>{{app.locale==='en'?'Collect with the browser extension':'使用浏览器插件采集'}}</strong><button type="button" @click="openGuide">{{app.locale==='en'?'Beginner guide':'新手教程：从安装到采集'}}</button><a :href="`${API_BASE}/api/mkhp/collector/installer`" @click="confirmDownload($event,true)">{{app.locale==='en'?'Download Windows setup helper':'下载 Windows 安装辅助工具'}}</a><a :href="`${API_BASE}/api/mkhp/collector/download`" @click="confirmDownload($event)">{{app.locale==='en'?'Download Edge extension ZIP':'下载 Edge 插件 ZIP'}}</a><span>{{app.locale==='en'?'Open the product page in desktop Edge, then click Extensions → MHP 商品采集助手 beside the browser address bar. No product URL input is required in MHP.':'先在电脑端 Edge 打开商品页，再点击浏览器地址栏右侧“扩展”→“MHP 商品采集助手”。无需在 MHP 输入商品链接。'}}</span><div class="collector-installation" :data-state="installation.state"><p role="status" aria-live="polite">{{installationText}}</p><button type="button" :disabled="installation.state==='checking'" @click="checkInstallation">{{app.locale==='en'?'Check again':'重新检测'}}</button></div></div>
  <Teleport to="body">
    <dialog ref="guide" class="collector-dialog" :data-theme="app.theme" aria-labelledby="collector-guide-title" @cancel.prevent="closeGuide">
      <h2 id="collector-guide-title">{{app.locale==='en'?'MKHP beginner guide':'MKHP 新手教程'}}</h2>
      <div class="collector-installation" :data-state="installation.state"><p role="status" aria-live="polite">{{installationText}}</p><button type="button" :disabled="installation.state==='checking'" @click="checkInstallation">{{app.locale==='en'?'Check installation':'检测插件安装状态'}}</button></div>
      <MKHPQuickGuide :key="guideRevision" :english="app.locale==='en'" />
      <details class="guide-faq"><summary>{{app.locale==='en'?'Troubleshooting':'遇到问题怎么办？'}}</summary><p>{{app.locale==='en'?'Not connected: enable v0.3.0 in Edge, allow access to this MHP site and refresh. Keep only one MHP tab open in the same browser. Install status confirms the connection, not extraction quality.':'未连接：在 Edge 启用 v0.3.0，允许访问当前 MHP 站点，刷新后重新检测；同一浏览器只保留一个 MHP 标签页。安装状态只代表连接成功，不代表所有商品页都能识别。'}}</p><p>{{app.locale==='en'?'Missing fields: sign in to the product site and expand the specifications yourself. Unsupported pages or site changes can prevent extraction. Verify missing facts manually; do not guess dimensions.':'字段缺失：自行完成商品页登录或验证并展开参数。页面不支持或平台改版时可能无法识别；缺失信息需人工核实，不能猜测尺寸。'}}</p></details>
      <a href="/mhp-collector-guide.html" target="_blank" rel="noopener">{{app.locale==='en'?'Open full guide in a new tab':'在新标签页打开完整教程'}}</a><button type="button" autofocus @click="closeGuide">{{app.locale==='en'?'Close guide':'关闭教程，进入 MKHP'}}</button>
    </dialog>
    <dialog ref="preview" class="collector-dialog" :data-theme="app.theme" aria-labelledby="collector-preview-title" @cancel.prevent="closePreview">
      <h2 id="collector-preview-title">核对浏览器采集内容</h2>
      <template v-if="capture"><p>{{capture.source_url}}</p><p>空白字段表示未识别；可在此补充经你核实的信息。确认前不会下载图片或保存业务记录。</p>
        <label v-for="(field,key) in capture.fields" :key="key">{{names[key]}}<textarea v-model="field.value" maxlength="2000" :disabled="busy" rows="2" placeholder="未识别；如需补充，请先核实" /></label>

        <p>已选 {{selected.length}} / 20 张。候选图可能含无关内容，请逐张选择。</p><label><input v-model="showImages" type="checkbox" :disabled="busy" />显示候选缩略图（会由浏览器访问图片网址）</label>
        <div class="collector-images"><label v-for="(url,index) in capture.image_urls" :key="url"><input v-model="selected" type="checkbox" :value="url" :disabled="busy||selected.length>=20&&!selected.includes(url)" /><img v-if="showImages" :src="url" alt="候选商品图" loading="lazy" referrerpolicy="no-referrer"/><span>图片{{index+1}} · {{url}}</span></label></div>
      </template><p v-if="error" role="alert">{{error}}</p><button :disabled="busy" @click="save">{{busy?'正在提交…':'确认导入所选内容'}}</button><button :disabled="busy" @click="closePreview">取消</button>
    </dialog>
  </Teleport>
</template>
<style scoped>
.collector-installation{display:flex;align-items:center;flex-wrap:wrap;gap:10px;flex-basis:100%;padding:10px 12px;border:1px solid var(--border-dim,#ccc);border-radius:8px;overflow-wrap:anywhere}.collector-installation p{flex:1 1 240px;margin:0;font-size:13px}.collector-installation[data-state=installed]{background:#29834a14;border-color:#29834a;color:var(--text-primary,#17633c)}.collector-installation button{padding:7px 10px;cursor:pointer;border:1px solid #9996;border-radius:6px;background:var(--bg-glass,#eee);color:inherit}.collector-installation button:disabled{opacity:.6;cursor:wait}
.collector-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:14px 0;padding:14px;border:1px solid var(--border-dim);border-radius:12px}.collector-actions span{flex-basis:100%;font-size:12px}.collector-dialog{width:min(760px,90vw);max-height:85vh;overflow:auto;border:1px solid var(--border-dim,#ddd);border-radius:16px;padding:24px;background:var(--bg-card-strong,#fff);color:var(--text-primary,#222);font:14px/1.7 system-ui}.collector-dialog::backdrop{background:#0009}.collector-dialog label{display:block;margin:10px 0}.collector-dialog textarea{display:block;box-sizing:border-box;width:100%;padding:8px;color:inherit;background:var(--bg-glass,#f5f5f5);border:1px solid #9996;border-radius:8px}.collector-dialog button{padding:9px 14px;margin:8px 8px 0 0;cursor:pointer;border:1px solid #9996;border-radius:8px;background:var(--bg-glass,#eee);color:inherit}.collector-dialog a{color:var(--neon-blue,#3559c9)}.collector-dialog li{margin:12px 0}.collector-dialog code{overflow-wrap:anywhere}.collector-images{max-height:300px;overflow:auto}.collector-images label{border-bottom:1px solid #9994;padding:8px;overflow-wrap:anywhere}.collector-images img{width:100px;height:100px;object-fit:contain;vertical-align:middle}.collector-images span{font-size:12px}.collector-dialog [role=alert]{color:#d05d46}
</style>
