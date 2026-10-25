<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { workspaceRequest, assetPreviewUrl } from '../api/client'
import { useAppContext } from '../composables/useAppContext'
import MKHPCopywriter from './MKHPCopywriter.vue'
import MKHPCollector from './MKHPCollector.vue'
import MKHPCost from './MKHPCost.vue'
const app=useAppContext(),items=ref([]),current=ref(null),busy=ref(false),error=ref(''),page=ref(1)
let stopped=false,timer=null
const names={name:'商品名称',description:'网页介绍',price:'价格／最低价',price_max:'最高价',currency:'币种',size:'商品尺寸',package_size:'包裹尺寸',material:'材质',width:'宽度',height:'高度',depth:'深度',weight:'重量'}
async function load(){
  try{items.value=(await workspaceRequest('/mkhp/imports?page='+page.value)).items}catch(e){error.value=e.message}
}
async function poll(id){
  if(stopped)return
  try{
    const data=await workspaceRequest('/mkhp/imports/'+id)
    if(stopped)return
    current.value=data
    if(data.status==='pending'){timer=setTimeout(()=>poll(id),1800)}else{busy.value=false;await load()}
  }catch(e){error.value=e.message;busy.value=false}
}
function select(item){if(busy.value)return;clearTimeout(timer);current.value=item;if(item.status==='pending'){busy.value=true;poll(item.import_id)}}
function browserImported(id){clearTimeout(timer);busy.value=true;error.value='';poll(id)}
function openLibrary(image=null){
  if(!current.value?.folder_id||busy.value)return
  if(!window.confirm(image?'允许打开 PTMD 并将这张图片选为示例图吗？用途：为后续生成提供参考；本次不调用 AI。':'允许打开 PTMD 并定位此商品的示例图文件夹吗？用途：选择采集素材供后续生成使用；本次不调用 AI。'))return
  app.referenceLibraryToOpen={folder_id:current.value.folder_id,asset_id:image?.asset_id||''}
  app.showView('ptmd')
}
async function removeImage(image){
  if(busy.value||!window.confirm('允许将这张商品示例图移入回收站吗？用途：从 MKHP 和 PTMD 可选图库中移除；可在设置中心恢复，已有成品保留。'))return
  busy.value=true;error.value=''
  try{await workspaceRequest('/assets/'+image.asset_id,'DELETE');await poll(current.value.import_id)}catch(e){error.value=e.message}finally{busy.value=false}
}
async function moreImages(retryFailed=false){
  if(busy.value||!current.value)return
  if(!window.confirm(retryFailed?'允许重新下载最多20张失败图片并保存到当前来源文件夹？':'允许继续下载下一批最多20张图片并保存到当前来源文件夹？'))return
  busy.value=true;error.value=''
  try{const task=await workspaceRequest(`/mkhp/imports/${current.value.import_id}/images`,'POST',{confirm_fetch:true,retry_failed:retryFailed});await poll(task.import_id)}catch(e){error.value=e.message;busy.value=false}
}
function exportJson(){if(!current.value)return;const a=document.createElement('a'),blob=new Blob([JSON.stringify(current.value,null,2)],{type:'application/json'});a.href=URL.createObjectURL(blob);a.download='MHP-product-'+current.value.import_id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
onMounted(load)
onUnmounted(()=>{stopped=true;clearTimeout(timer)})
</script>
<template>
<section class="mkhp-importer">
  <h2>{{app.locale==='en'?'MKHP · Product collection':'MKHP · 商品采集'}}</h2>
  <MKHPCollector @imported="browserImported" />
  <p v-if="error" role="alert">{{error}}</p>
  <h3>{{app.locale==='en'?'Collection history':'采集历史'}}</h3>
  <p v-if="!items.length">{{app.locale==='en'?'No collections yet. Follow the beginner guide above to collect your first product.':'暂无采集记录。请按上方新手教程采集第一个商品，确认导入后会显示在这里。'}}</p>
  <div class="import-history"><button v-for="item in items" :key="item.import_id" :disabled="busy" @click="select(item)">{{item.result?.fields?.name?.value||item.source_url}} · {{item.status==='completed'?'已归档':item.status==='pending'?'采集中':'失败'}}</button></div>
  <div class="import-pages"><button :disabled="page<=1||busy" @click="page--;load()">上一页</button><span>第 {{page}} 页</span><button :disabled="items.length<30||busy" @click="page++;load()">下一页</button><button :disabled="busy" @click="load">刷新历史</button></div>
  <template v-if="current">
    <p v-if="current.result?.capture_method!=='browser-extension'" class="legacy-import" role="note">{{app.locale==='en'?'This is a legacy link import. New imports use the browser extension; this history is preserved.':'这是旧版链接导入记录，资料仍保留。新采集仅使用 Edge 插件，静态网页读取已停用。'}}</p>
    <p>来源：<a :href="current.source_url" target="_blank" rel="noopener noreferrer">{{current.source_url}}</a></p>
    <p v-if="current.error" role="alert">{{current.error}}</p>
    <p v-for="warning in current.result?.warnings||[]" :key="warning">{{warning}}</p>
    <div class="table-wrap"><table><thead><tr><th>识别项目</th><th>内容</th><th>来源证据</th></tr></thead><tbody>
      <tr v-for="(name,key) in names" :key="key"><th>{{name}}</th><td>{{current.result?.fields?.[key]?.value??'未识别'}}</td><td>{{current.result?.fields?.[key]?.evidence??'—'}}</td></tr>
    </tbody></table></div>
    <p>当前保留 {{current.result?.images?.length||0}} 张归档图片；不同来源网址分别存放，PTMD 中可按文件夹选择。<span v-if="current.result?.removed_image_count">另有 {{current.result.removed_image_count}} 张已删除或移入回收站。</span></p>
    <div class="import-images"><article v-for="(image,index) in current.result?.images||[]" :key="image.asset_id"><img :src="assetPreviewUrl(image.asset_id)" :alt="`商品示例图 ${index+1}`" loading="lazy"/><p>图片 {{index+1}}</p><a :href="image.source_url" target="_blank" rel="noopener noreferrer">图片来源</a><div class="image-actions"><button :disabled="busy" @click="openLibrary(image)">用于 PTMD 示例图</button><button :disabled="busy" @click="removeImage(image)">删除示例图</button></div></article></div>
    <div class="import-pages"><button v-if="current.result?.remaining_images" :disabled="busy" @click="moreImages(false)">继续归档图片（剩余 {{current.result.remaining_images}} 张）</button><button v-if="current.result?.image_errors?.length" :disabled="busy" @click="moreImages(true)">重试失败图片</button></div>
    <details v-if="current.result?.image_errors?.length"><summary>未能归档的图片（{{current.result.image_errors.length}}）</summary><p v-for="(entry,i) in current.result.image_errors" :key="i">{{entry.message}} · {{entry.source_url}}</p></details>
    <details v-if="current.result?.image_urls?.length"><summary>全部识别到的图片链接（{{current.result.image_urls.length}}）</summary><ol><li v-for="link in current.result.image_urls" :key="link"><a :href="link" target="_blank" rel="noopener noreferrer">{{link}}</a></li></ol></details>
    <div class="import-pages"><button @click="exportJson">下载识别结果 JSON</button><button :disabled="busy||!current.folder_id" @click="openLibrary()">前往此商品的 PTMD 示例文件夹</button></div>
    <MKHPCopywriter :key="current.import_id" :product="current" />
  </template>
  <MKHPCost />
</section>
</template>
<style scoped>
.legacy-import{padding:12px;border-left:3px solid var(--neon-blue);background:var(--bg-sidebar);border-radius:6px}
.image-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.image-actions button{font-size:12px;padding:6px 8px}
.import-history,.import-pages{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;align-items:center}.import-history button{max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.import-images{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px}.import-images article{margin:0;padding:10px}.import-images img{display:block;width:100%;height:150px;object-fit:contain;margin-bottom:8px}.mkhp-importer td{max-width:500px;overflow-wrap:anywhere;white-space:pre-wrap}.mkhp-importer details{padding:12px 0;overflow-wrap:anywhere}.mkhp-importer .pending-ai{color:var(--text-secondary)}
</style>
