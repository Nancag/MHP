<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { workspaceRequest, downloadBlob, API_BASE } from '../api/client'
import { useAppContext } from '../composables/useAppContext'
const props=defineProps({product:{type:Object,required:true}})
const app=useAppContext(),cap=ref({models:[],languages:{},configured:false}),model=ref(''),language=ref(''),requirements=ref(''),drafts=ref([]),draft=ref(null),busy=ref(false),error=ref('')
let requestId='',requestSignature='',loadVersion=0,stopped=false,pollTimer=null
async function load(){
  const version=++loadVersion,id=props.product.import_id
  try{
    const [config,history]=await Promise.all([workspaceRequest('/mkhp/ai-capabilities'),workspaceRequest('/mkhp/drafts?import_id='+id)])
    if(stopped||version!==loadVersion)return
    cap.value=config;drafts.value=history.items;draft.value=history.items[0]||null
    if(draft.value?.status==='pending')poll(draft.value.draft_id,id)
  }catch(e){if(!stopped&&version===loadVersion)error.value=e.message}
}
async function poll(id,importId){
  clearTimeout(pollTimer)
  if(stopped||importId!==props.product.import_id)return
  try{
    const value=await workspaceRequest('/mkhp/drafts/'+id)
    if(stopped||importId!==props.product.import_id)return
    draft.value=value
    if(value.status==='pending')pollTimer=setTimeout(()=>poll(id,importId),2000)
    else await load()
  }catch(e){error.value=e.message}
}
async function generate(){
  if(busy.value||!model.value||!language.value)return
  const payload={import_id:props.product.import_id,model:model.value,language:language.value,requirements:requirements.value}
  if(!window.confirm(`允许将已识别的商品字段、语言和创作要求发送给 ${model.value}，生成双语介绍及生图提示词吗？本次可能产生 API 费用，不发送商品图片、登录信息或本地路径。文本模型不直接生成图片。`))return
  const signature=JSON.stringify(payload)
  if(signature!==requestSignature||!requestId){requestId=crypto.randomUUID();requestSignature=signature}
  busy.value=true;error.value=''
  try{
    const result=await workspaceRequest('/mkhp/drafts','POST',{...payload,request_id:requestId,confirm_send:true},{timeoutMs:95000})
    if(stopped)return
    draft.value=result
    // Only a deliberate new click after a known terminal result may create a new billable request.
    if(result.status!=='pending'){requestId='';requestSignature=''}
    await load()
    if(result.status==='failed')error.value=result.error
  }catch(e){if(!stopped){error.value=e.message+'；请先刷新任务历史核对结果，勿立即重复生成。';await load()}}
  finally{if(!stopped)busy.value=false}
}
async function download(format){
  if(!draft.value||busy.value)return
  busy.value=true;error.value=''
  try{await downloadBlob(`${API_BASE}/api/mkhp/drafts/${draft.value.draft_id}/export?format=${format}`,`MHP-product-${draft.value.draft_id}.${format}`)}catch(e){error.value=e.message}finally{busy.value=false}
}
function handoff(){
  if(draft.value?.status!=='completed')return
  if(!window.confirm('将生图提示词填入 PTMD 创作要求？此操作不调用生图。请在 PTMD 另行选择商品原图，并核对提示词；真实 AI 生图仍需要接通图像服务。'))return
  const c=draft.value.content
  app.templateToApply={origin:'mkhp',prompt:c.image_prompt_en+'\nNegative prompt: '+c.negative_prompt_en,
    product_name:props.product.result?.fields?.name?.value||'',draft_id:draft.value.draft_id}
  app.showView('ptmd')
}
watch(()=>props.product.import_id,()=>{clearTimeout(pollTimer);draft.value=null;error.value='';requestId='';requestSignature='';load()})
onMounted(load)
onUnmounted(()=>{stopped=true;clearTimeout(pollTimer);loadVersion++})
</script>
<template>
<div class="mkhp-copywriter">
  <h3>双语产品介绍与宣传图提示词</h3>
  <p v-if="!cap.configured">后端尚未配置经你确认的密钥与模型。模型列表查询曾返回 HTTP 403；配置并真实验证前，不能生成 AI 文案。</p>
  <p v-else>后端已配置，真实调用效果及费用仍需核对。AI 文案是待审草稿，发布前请检查翻译和商品事实。</p>
  <div class="fields"><label>文本模型<select v-model="model" :disabled="busy"><option value="" disabled>请选择模型</option><option v-for="id in cap.models" :key="id" :value="id">{{id}}</option></select></label>
  <label>介绍语言<select v-model="language" :disabled="busy"><option value="" disabled>请选择目标语言</option><option v-for="(name,code) in cap.languages" :key="code" :value="code">{{name}}</option></select></label></div>
  <label>用大白话描述宣传图需求<textarea v-model="requirements" rows="3" maxlength="2000" :disabled="busy" placeholder="例如：放在整洁的厨房台面，柔和侧光，突出商品，右侧留白供后续排版。" /></label>
  <div class="actions"><button :disabled="busy||!cap.configured||!model||!language||product.status!=='completed'||draft?.status==='pending'" @click="generate">{{busy?'处理中…':'生成双语介绍和提示词'}}</button><button :disabled="busy" @click="load">刷新任务历史</button></div>
  <p v-if="error" role="alert">{{error}}</p>
  <div class="history"><button v-for="item in drafts" :key="item.draft_id" :disabled="busy" @click="draft=item">{{item.language}} · {{item.model}} · {{item.status==='completed'?'已完成':item.status==='pending'?'处理中':'失败'}}</button></div>
  <template v-if="draft">
    <p v-if="draft.status==='pending'">文本任务尚未确认完成，请刷新历史查询；避免重复调用产生额外费用。</p>
    <p v-if="draft.error" role="alert">{{draft.error}}</p>
    <template v-if="draft.status==='completed'">
      <p>语言：{{cap.languages[draft.language]||draft.language}} · 模型：{{draft.model}} · Token：{{draft.usage?.total_tokens??'上游未返回'}}。费用以服务商账单为准。</p>
      <h4>{{draft.content.title.target}}</h4><p class="translation">中文：{{draft.content.title.zh}}</p>
      <article v-for="(section,i) in draft.content.sections" :key="i"><h4>{{section.heading.target}}</h4><p class="translation">{{section.heading.zh}}</p><p class="copy-text">{{section.body.target}}</p><p class="translation copy-text">中文翻译：{{section.body.zh}}</p></article>
      <h4 v-if="draft.content.selling_points?.length">商品卖点</h4><ol><li v-for="(point,i) in draft.content.selling_points" :key="i"><p>{{point.target}}</p><p class="translation">中文：{{point.zh}}</p></li></ol>
      <h4>宣传图提示词 English</h4><p class="copy-text">{{draft.content.image_prompt_en}}</p><h4>提示词中文翻译</h4><p class="copy-text">{{draft.content.image_prompt_zh}}</p><h4>负面提示词</h4><p>{{draft.content.negative_prompt_en}}</p>
      <p v-for="(note,i) in draft.content.notes_zh" :key="i">待核对：{{note}}</p>
      <div class="actions"><button :disabled="busy" @click="download('docx')">下载 Word</button><button :disabled="busy" @click="download('json')">下载双语 JSON</button><button :disabled="busy" @click="handoff">将提示词传入 PTMD</button></div>
    </template>
  </template>
</div>
</template>
<style scoped>
.mkhp-copywriter{margin-top:24px;padding-top:20px;border-top:1px solid var(--border-dim)}.mkhp-copywriter h3{font-size:20px}.mkhp-copywriter h4{font-size:16px;line-height:1.6;margin-top:18px}.translation{color:var(--text-secondary)}.copy-text{white-space:pre-wrap;overflow-wrap:anywhere}.actions,.history{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.history button{font-size:12px}
</style>
