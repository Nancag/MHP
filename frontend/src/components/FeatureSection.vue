<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
const props=defineProps({t:{type:Object,required:true}})
const english=computed(()=>props.t.account.breadcrumb==='Account')
const updates=ref([]),failed=ref(false)
const controller=new AbortController()
onMounted(async()=>{
  const timer=setTimeout(()=>controller.abort(),10000)
  try{
    const response=await fetch('/updates.json',{cache:'no-store',signal:controller.signal})
    if(!response.ok)throw Error('Updates unavailable')
    const data=await response.json()
    if(!Array.isArray(data))throw Error('Invalid updates')
    updates.value=data.filter(group=>/^\d{4}-\d{2}-\d{2}$/.test(group.date)&&Array.isArray(group.items)&&group.items.every(item=>typeof item==='string')).slice(0,20)
  }catch(error){if(!controller.signal.aborted)failed.value=true}
  finally{clearTimeout(timer)}
})
onUnmounted(()=>controller.abort())
const rows=computed(()=>updates.value.map(group=>({...group,items:english.value&&Array.isArray(group.items_en)?group.items_en:group.items})))
const stats=computed(()=>english.value?[
  {n:'9',unit:'images',text:'Up to nine independent images in one set. Review each page before exporting.'},
  {n:'2',unit:'sizes',text:'1200 or 2000 pixels on the long edge. Choose the size your listing needs.'},
  {n:'2',unit:'languages',text:'Russian and English output copy, with Chinese and English interface options.'},
]:[
  {n:'9',unit:'张',text:'一套最多九张独立图片，逐页核对后导出。'},
  {n:'2',unit:'档分辨率',text:'长边 1200 / 2000 像素，按用途选择。'},
  {n:'2',unit:'种成品文案',text:'支持俄语、英语文案排版，界面可切换中文和英文。'},
])
</script>
<template>
  <section>
    <div class="hx-ticker" :aria-label="english?'Release updates':'更新告示'">
      <div v-if="rows.length" class="hx-ticker__track">
        <span v-for="(group,gi) in rows.concat(rows)" :key="gi" class="hx-ticker__item" :aria-hidden="gi>=rows.length?true:undefined">
          <em><template v-if="group.version">v{{ group.version }} · </template>{{ group.date }}</em><span v-for="(line,i) in group.items" :key="i"><b v-if="i>0">·</b>{{ line }}</span>
        </span>
      </div>
      <p v-else class="updates-empty">{{ english?(failed?'Updates are temporarily unavailable.':'No release announcements yet.'):(failed?'更新告示暂时无法读取。':'暂无更新告示。') }}</p>
    </div>
    <div class="hx-stats"><div v-for="s in stats" :key="s.n+s.unit" class="hx-stat"><div class="hx-stat__n">{{ s.n }}<small>{{ s.unit }}</small></div><p>{{ s.text }}</p></div></div>
    <div class="hx-foot"><span>MHP STUDIO · {{ english?'product photo studio':'商品图工作室' }} · 2026</span><span>{{ english?'Original photos · local layouts · reviewed exports':'真实素材 · 本地排版 · 审核导出' }}</span></div>
  </section>
</template>
