<script setup>
import { ref, onUnmounted, watch } from 'vue'
import { workspaceRequest, uploadAsset, assetPreviewUrl } from '../../api/client'

const props = defineProps({ selected: {type:Array,default:()=>[]}, busy:Boolean, english:Boolean, initialFolderId:{type:String,default:''} })
const emit = defineEmits(['toggle', 'deleted', 'error'])
const folders=ref([]),folderId=ref('unfiled'),items=ref([]),page=ref(1),total=ref(0),loading=ref(false),input=ref(null),error=ref('')
const label=(zh,en)=>props.english?en:zh
let loadVersion=0
onUnmounted(()=>{loadVersion++})
async function load(){
  const version=++loadVersion,folder=folderId.value,currentPage=page.value
  error.value=''
  try{
    const [listing,data]=await Promise.all([workspaceRequest('/library/folders'),workspaceRequest(`/library/folders/${folder}/assets?page=${currentPage}`)])
    if(version!==loadVersion)return
    folders.value=listing.items;items.value=data.items;total.value=data.total
  }catch(e){if(version===loadVersion)error.value=e.message}
}
async function create(){
  if(loading.value||props.busy)return
  const name=window.prompt(label('创建示例图文件夹：请输入名称（将在本地保存）','Create a local reference folder: enter a name'))
  if(!name?.trim())return
  if(name.trim().length>120){error.value=label('文件夹名称最多120个字符','Folder names may contain up to 120 characters');return}
  loading.value=true
  try{const folder=await workspaceRequest('/library/folders','POST',{name:name.trim()});folderId.value=folder.folder_id;page.value=1;await load()}catch(e){error.value=e.message}finally{loading.value=false}
}
async function upload(event){
  const files=Array.from(event.target.files||[]);event.target.value=''
  if(!files.length||loading.value||props.busy)return
  if(!window.confirm(label(`将 ${files.length} 张图片上传并保存到当前示例图文件夹？`,`Upload and save ${files.length} images to this reference folder?`)))return
  loading.value=true;error.value=''
  try{for(const file of files)await uploadAsset(file,'reference',folderId.value==='unfiled'?null:folderId.value);page.value=1;await load()}
  catch(e){await load();error.value=e.message}finally{loading.value=false}
}
async function remove(item){
  if(loading.value||props.busy||!window.confirm(label('将这张示例图移入回收站？可以在设置中心恢复，已有成品保留。','Move this reference to trash? Restore it in Settings. Existing results remain.')))return
  loading.value=true
  try{await workspaceRequest('/assets/'+item.asset_id,'DELETE');emit('deleted',item.asset_id);await load()}catch(e){error.value=e.message}finally{loading.value=false}
}
watch(()=>props.initialFolderId,value=>{if(value){folderId.value=value;page.value=1}},{immediate:true})
watch(folderId,()=>{page.value=1;load()})
load()
</script>
<template>
<section class="reference-library">
  <h4>{{ label('示例图库','Reference library') }}</h4>
  <p>{{ label('MKHP 采集图按商品网址分别归档；也可创建文件夹保存自己的示例图。最多选择2张用于风格与排版参考。生成时另行确认。','MKHP images are filed by product URL. You can also create folders for your own references. Select up to 2 style/layout references; confirm generation separately.') }}</p>
  <select v-model="folderId" :disabled="busy||loading" aria-label="示例图文件夹"><option value="unfiled">{{ label('未分类','Unfiled') }}</option><option v-for="f in folders" :key="f.folder_id" :value="f.folder_id">{{ f.name }} ({{f.image_count}})</option></select>
  <div class="actions"><button :disabled="busy||loading" @click="create">{{label('创建文件夹','New folder')}}</button><button :disabled="busy||loading" @click="load">{{label('刷新','Refresh')}}</button></div>
  <p v-if="folders.find(f=>f.folder_id===folderId)?.source_url" class="source">{{folders.find(f=>f.folder_id===folderId).source_url}}</p>
  <input ref="input" type="file" accept="image/jpeg,image/png" multiple hidden @change="upload" />
  <button :disabled="busy||loading" @click="input?.click()">{{loading?'…':label('上传到当前文件夹','Upload to folder')}}</button>
  <p v-if="error" role="alert">{{error}}</p>
  <div class="images"><article v-for="item in items" :key="item.asset_id">
    <button class="image" :class="{selected:selected.includes(item.asset_id)}" :disabled="busy||loading" @click="emit('toggle',item.asset_id)"><img :src="assetPreviewUrl(item.asset_id)" :alt="item.filename" loading="lazy"/><span v-if="selected.includes(item.asset_id)">✓</span></button>
    <button class="delete" :disabled="busy||loading" @click="remove(item)">{{label('删除','Delete')}}</button>
  </article></div>
  <p v-if="!items.length">{{label('当前文件夹没有示例图。','No reference images in this folder.')}}</p>
  <div class="actions"><button :disabled="page<=1||loading||busy" @click="page--;load()">←</button><span>{{page}} / {{Math.max(1,Math.ceil(total/60))}}</span><button :disabled="page*60>=total||loading||busy" @click="page++;load()">→</button></div>
  <p>{{label('已选择','Selected')}} {{selected.length}} / 2 {{label('（跨文件夹保留）','(across folders)')}}</p>
</section>
</template>
<style scoped>
.reference-library{margin-top:18px;padding-top:16px;border-top:1px solid var(--border-dim);font-size:12px}.reference-library h4{font-size:14px}.reference-library p{line-height:1.65;color:var(--text-secondary);overflow-wrap:anywhere}.reference-library select{width:100%}.reference-library button,.reference-library select{color:var(--text-primary);background:var(--bg-sidebar);border:1px solid var(--border-dim);border-radius:7px;padding:7px;max-width:100%;cursor:pointer}.actions{display:flex;gap:8px;align-items:center;margin:9px 0}.images{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.images article{min-width:0}.image{position:relative;width:100%;aspect-ratio:1;padding:2px!important;overflow:hidden}.image img{width:100%;height:100%;object-fit:contain}.image.selected{border:2px solid var(--neon-blue)}.image span{position:absolute;top:3px;right:5px;color:var(--neon-blue)}.delete{width:100%;margin-top:3px}.source{font-size:10px}.reference-library button:disabled{opacity:.5;cursor:default}
</style>
