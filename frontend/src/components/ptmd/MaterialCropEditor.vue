<script setup>
import { ref } from 'vue'
defineProps({src:String,modelValue:{type:Array,default:null},english:Boolean})
const emit=defineEmits(['update:modelValue'])
const surface=ref(null),pending=ref(null)
let start=null
function point(e){const r=surface.value.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]}
function down(e){if(e.button!==0)return;start=point(e);surface.value.setPointerCapture(e.pointerId);pending.value=[...start,...start]}
function move(e){if(!start)return;const p=point(e);pending.value=[Math.min(start[0],p[0]),Math.min(start[1],p[1]),Math.max(start[0],p[0]),Math.max(start[1],p[1])]}
function up(e){if(!start)return;move(e);const p=pending.value;if(p[2]-p[0]>=.02&&p[3]-p[1]>=.02)emit('update:modelValue',p.map(v=>Math.round(v*100000)/100000));start=null;pending.value=null}
function box(p){return {left:p[0]*100+'%',top:p[1]*100+'%',width:(p[2]-p[0])*100+'%',height:(p[3]-p[1])*100+'%'}}
</script>
<template>
 <div class="material-crop">
  <p>{{ english?'Drag on the image to select a real detail. The original stays intact.':'在图片上拖动框选真实细节，原图保留。' }}</p>
  <div ref="surface" class="material-crop__surface" @pointerdown.prevent="down" @pointermove="move" @pointerup="up" @pointercancel="start=null;pending=null">
   <img :src="src" draggable="false" :alt="english?'Source crop selection':'素材裁切选择'" />
   <span v-if="pending||modelValue" class="material-crop__box" :style="box(pending||modelValue)" />
  </div>
  <button v-if="modelValue" type="button" @click="emit('update:modelValue',null)">{{ english?'Use full image':'恢复完整素材' }}</button>
 </div>
</template>
<style scoped>
.material-crop p{font-size:11px;line-height:1.5}.material-crop__surface{position:relative;touch-action:none;cursor:crosshair;background:repeating-conic-gradient(#ddd 0% 25%,#fff 0% 50%) 0/14px 14px}.material-crop img{display:block;width:100%;height:auto;pointer-events:none}.material-crop__box{position:absolute;border:2px solid #149ddd;box-sizing:border-box;background:#149ddd22;pointer-events:none}.material-crop button{margin-top:8px}
</style>
