<script setup>
import {ref,watch} from 'vue'
import {generationPreviewUrl} from '../../api/client'
const props=defineProps({batch:{type:Object,required:true},english:Boolean,selectedId:String,busy:Boolean})
const emit=defineEmits(['select','review','retry','download'])
const checks=ref([false,false,false,false]),edge=ref('2000')
watch(()=>props.selectedId,()=>{checks.value=[false,false,false,false]})
const labels=()=>props.english?['Product matches source','Copy is correct','No extra accessories','Layout meets requirements']:['商品与素材一致','文案无误','没有多余配件','版式符合要求']
function review(){if(props.busy||!checks.value.every(Boolean))return;emit('review',props.selectedId,{product_matches:checks.value[0],copy_matches:checks.value[1],no_extra_accessories:checks.value[2],layout_matches:checks.value[3]})}
</script>
<template>
 <section class="set-results">
  <p v-if="batch.spec.engine==='local'">{{ english?'Local material layout · 0 generation API calls · actual photos, no new views':'本地素材排版 · 0次生图API调用 · 使用真实素材，不生成新视角' }}</p>
  <div class="set-results__summary"><strong>{{ english?'Ecommerce set':'电商套图' }} {{ batch.completed }}/{{ batch.count }}</strong><span>{{ english?'Accepted':'已核对' }} {{ batch.accepted }}/{{ batch.count }}</span>
   <select v-model="edge" :aria-label="english?'Export size':'导出尺寸'"><option v-for="size in ['1200','2000']" :key="size" :value="size">{{ size+' px' }}</option></select>
   <button type="button" :disabled="busy||batch.accepted!==batch.count" aria-describedby="set-download-hint" @click="emit('download',edge)">{{ english?'Download reviewed set':'下载已核对套图' }}</button>
   <span id="set-download-hint" role="status">{{ busy?(english?'Processing, please wait…':'正在处理，请稍候…'):batch.accepted!==batch.count?(english?'Review every page before downloading.':'全部页面核对完成后才能下载。'):'' }}</span>
  </div>
  <p v-for="item in batch.items.filter(item=>item.status==='failed')" :key="item.generation_id" role="alert">{{ english?'Page':'第' }} {{ item.page_index+1 }}{{ english?':':'页：' }} {{ item.error }} {{ english?'Provider charges may still apply.':'上游可能仍已计费，请核对账单后决定是否重试。' }}</p>
  <div class="set-results__pages"><button v-for="item in batch.items" :key="item.generation_id" type="button" :class="{'is-selected':selectedId===item.generation_id}" @click="emit('select',item)">
    <img v-if="item.status==='completed'" :src="generationPreviewUrl(item.generation_id)" alt="" /><span v-else>{{ item.status==='pending'?'…':'×' }}</span>
    <small>{{ item.page_index+1 }} · {{ item.status==='completed' ? (item.review_status==='accepted'?'✓':(english?'Review':'待核对')) : item.status }}</small>
   </button></div>
  <div v-if="batch.items.find(item=>item.generation_id===selectedId)?.status==='completed'" class="set-results__review">
   <label v-for="(label,index) in labels()" :key="label"><input v-model="checks[index]" type="checkbox" />{{ label }}</label>
   <button type="button" :disabled="busy||!checks.every(Boolean)" aria-describedby="set-review-hint" @click="review">{{ english?'Confirm this page':'确认本页符合要求' }}</button>
   <span id="set-review-hint" role="status">{{ busy?(english?'Processing, please wait…':'正在处理，请稍候…'):!checks.every(Boolean)?(english?'Select all checks first.':'请先勾选全部核对项。'):'' }}</span>
  </div>
  <button v-if="batch.items.some(item=>item.generation_id===selectedId&&item.status!=='pending')" type="button" :disabled="busy" @click="emit('retry',selectedId)">{{ english?'Regenerate this page':'重新生成本页' }}</button>
  <p>{{ english?'Check every page against your source and requirements. Export at 1200 or 2000 pixels.':'请逐页对照商品素材和要求检查。支持1200/2000像素导出。' }}</p>
 </section>
</template>
<style scoped>
.set-results{flex:none;max-height:44%;overflow:auto;padding:10px 16px;background:var(--bg-sidebar);color:var(--text-primary);border-bottom:1px solid var(--border-dim);font-size:12px}.set-results__summary,.set-results__review{display:flex;align-items:center;flex-wrap:wrap;gap:9px}.set-results button,.set-results select{border:1px solid var(--border-dim);border-radius:8px;background:var(--bg-card-strong);color:var(--text-primary);padding:6px;cursor:pointer}.set-results button:disabled{opacity:.45;cursor:not-allowed}.set-results__pages{display:flex;gap:9px;overflow-x:auto;padding:10px 0}.set-results__pages button{width:74px;min-width:74px;display:flex;flex-direction:column;align-items:center;gap:4px}.set-results__pages img,.set-results__pages span{width:48px;height:64px;object-fit:contain}.set-results__pages span{display:grid;place-items:center}.set-results__pages .is-selected{border-color:var(--neon-blue)}.set-results__review label{display:flex;align-items:center;gap:3px}.set-results p{color:var(--text-secondary);font-size:11px;margin:8px 0 0}
</style>
