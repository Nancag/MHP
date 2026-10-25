<script setup>
import {ref,computed,onMounted} from 'vue'
import {workspaceRequest,downloadBlob,API_BASE} from '../api/client'
import {useAppContext} from '../composables/useAppContext'
const props=defineProps({draft:{type:Object,default:null}}),emit=defineEmits(['apply'])
const app=useAppContext(),items=ref([]),query=ref(''),searchedQuery=ref(''),name=ref(''),description=ref(''),error=ref(''),catalogError=ref(''),busy=ref(false),loading=ref(true)
const en=computed(()=>app.locale==='en'),label=(zh,enText)=>en.value?enText:zh
const catalog=ref([]),catalogNotice=ref(''),pending=ref(null)
async function readFile(event){error.value='';pending.value=null;const file=event.target.files?.[0];event.target.value='';if(!file)return;try{if(file.size>65536)throw Error(label('模板文件不得超过64KB','Template files must be 64KB or smaller.'));const value=JSON.parse(await file.text());if(value.format!=='mhp-template'||value.version!==1||!value.template?.name||!value.template?.payload)throw Error(label('请选择 MHP 导出的 V1 JSON 模板，不支持 PSD/ZIP/HTML','Choose a V1 JSON template exported by MHP. PSD/ZIP/HTML are not supported.'));pending.value=value}catch(e){error.value=e.message}}
async function importFile(){if(busy.value||!pending.value)return;busy.value=true;try{await workspaceRequest('/workspace/templates/import','POST',pending.value);pending.value=null;await load()}catch(e){error.value=e.message}finally{busy.value=false}}
async function exportFile(item){try{await downloadBlob(`${API_BASE}/api/workspace/templates/${item.template_id}/export`,`MHP-template-${item.template_id}.json`)}catch(e){error.value=e.message}}
async function copy(item){if(busy.value||!window.confirm(label('允许将此模板复制到你的个人模板库吗？仅保存设置，不调用 AI。','Copy this template to your personal library? This only saves settings; no AI call.')))return;busy.value=true;try{await workspaceRequest('/workspace/templates','POST',{name:item.name,description:item.description,payload:item.payload});await load()}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(async()=>{try{const data=await workspaceRequest('/workspace/template-catalog');catalog.value=data.items;catalogNotice.value=data.notice}catch(e){catalogError.value=e.message}})
async function load(){error.value='';loading.value=true;try{const search=query.value;items.value=(await workspaceRequest('/workspace/templates?q='+encodeURIComponent(search))).items;searchedQuery.value=search}catch(e){error.value=e.message}finally{loading.value=false}}
onMounted(load)
async function save(){if(busy.value)return;busy.value=true;try{await workspaceRequest('/workspace/templates','POST',{name:name.value,description:description.value,payload:props.draft});name.value='';description.value='';await load()}catch(e){error.value=e.message}finally{busy.value=false}}
async function remove(item){if(busy.value||!window.confirm(label('删除此模板？','Delete this template?')))return;busy.value=true;try{await workspaceRequest('/workspace/templates/'+item.template_id,'DELETE');await load()}catch(e){error.value=e.message}finally{busy.value=false}}
function apply(item){if(!window.confirm(label('将模板填入 PTMD 创作设置？会替换当前编辑内容，不会开始生成。','Apply this template to PTMD? This replaces the current setup without starting generation.')))return;if(props.draft)emit('apply',item.payload);else{app.templateToApply=item.payload;app.showView('ptmd')}}
</script>
<template>
 <div class="template-library">
  <h2>{{ label('模板库','Template library') }}</h2>
  <p>{{ label('保存创作参数与文案，选择素材后可反复套用。模板不保存原图或API密钥。','Save creative parameters and copy, then apply them to selected material. Templates contain no original files or API keys.') }}</p>
  <details open class="template-catalog">
   <summary>{{ label('内置模板与平台规范预设','Built-in templates & platform presets') }}</summary>
   <p>{{ catalogNotice }}</p><p v-if="catalogError" role="alert">{{ catalogError }}</p>
   <article v-for="item in catalog" :key="item.template_id">
    <strong>{{ item.name }}</strong><p>{{ item.description }}</p><p v-for="rule in item.rules" :key="rule">{{ rule }}</p>
    <p v-if="item.source_url"><a :href="item.source_url" target="_blank" rel="noopener noreferrer">{{ label('官方规范来源','Official requirements') }}</a> · {{ label('核对日期','Checked') }} {{ item.checked_on }} · {{ item.verification==='pending'?label('待核实，暂不可用','Pending verification; unavailable'):label('已核实通用规范','General requirements verified') }}</p>
    <button :disabled="busy||item.verification==='pending'" @click="apply(item)">{{ label('套用','Apply') }}</button>
    <button :disabled="busy||item.verification==='pending'" @click="copy(item)">{{ label('复制到个人模板','Copy to personal templates') }}</button>
   </article>
  </details>
  <h3>{{ label('个人模板','Personal templates') }}</h3>
  <label>{{ label('导入 MHP V1 模板（JSON，≤64KB）','Import MHP V1 template (JSON, ≤64KB)') }}<input type="file" accept=".json,application/json" :disabled="busy" @change="readFile" /></label>
  <article v-if="pending"><strong>{{ label('导入预览：','Import preview: ') }}{{ pending.template.name }}</strong><p>{{ pending.template.description }}</p><p>{{ label('仅保存创作设置，不导入原图、不联网下载素材、不调用 AI。','Saves creative settings only. No original files, material downloads or AI calls.') }}</p><button :disabled="busy" @click="importFile">{{ label('确认保存到个人模板库','Save to personal templates') }}</button><button :disabled="busy" @click="pending=null">{{ label('取消','Cancel') }}</button></article>
  <form @submit.prevent="load"><input v-model="query" :aria-label="label('搜索个人模板','Search personal templates')" :placeholder="label('搜索名称或描述','Search names / descriptions')" maxlength="100" /><button :disabled="loading">{{ label('搜索','Search') }}</button></form>
  <div v-if="draft" class="template-save"><input v-model="name" maxlength="80" :placeholder="label('模板名称','Template name')"/><input v-model="description" maxlength="300" :placeholder="label('描述（选填）','Description (optional)')"/><button :disabled="busy||!name.trim()" @click="save">{{ label('保存当前创作设置','Save current setup') }}</button></div>
  <p v-if="error" role="alert">{{ error }}</p>
  <p v-if="loading" role="status">{{ label('正在加载个人模板…','Loading personal templates…') }}</p>
  <p v-else-if="!items.length&&!error">{{ searchedQuery?label('没有匹配的个人模板，请调整搜索词。','No matching personal templates. Try another search.'):label('暂无个人模板，可套用上方内置模板。','No personal templates yet. Apply a built-in template above.') }}</p>
  <article v-for="item in items" :key="item.template_id"><strong>{{ item.name }}</strong><p>{{ item.description }}</p><button :disabled="busy" @click="apply(item)">{{ label('套用模板','Apply') }}</button> <button :disabled="busy" @click="exportFile(item)">{{ label('导出 JSON','Export JSON') }}</button> <button :disabled="busy" @click="remove(item)">{{ label('删除','Delete') }}</button></article>
 </div>
</template>
<style scoped>
.template-library{line-height:1.6;overflow:auto}.template-library form,.template-save{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.template-library input{width:100%;padding:8px}.template-library article{padding:12px;margin:12px 0;border:1px solid var(--border-dim);border-radius:10px}.template-library button{padding:8px;border:1px solid var(--border-dim);border-radius:6px;background:var(--bg-sidebar);color:var(--text-primary);cursor:pointer}.template-library button:disabled{opacity:.5;cursor:not-allowed}.template-library p{overflow-wrap:anywhere}.template-catalog>summary{cursor:pointer;font-weight:700;color:var(--neon-blue);padding:10px 0}
</style>