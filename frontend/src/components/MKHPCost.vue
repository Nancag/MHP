<script setup>
import {computed,reactive,ref,watch} from 'vue'
import {workspaceRequest} from '../api/client'
const fields=[['purchase','进货价（元）'],['package_weight_g','包裹重量（g）'],['freight_per_g','运费单价（元/g）'],['customs_percent','关税（%）'],['commission_percent','平台佣金（%），小于50'],['loss_percent','货损率（%），小于100']]
const form=reactive(Object.fromEntries([...fields.map(([key])=>[key,'']),['customs_base','']]))
const result=ref(null),error=ref(''),allowed=ref(false),busy=ref(false)
const ready=computed(()=>Object.values(form).every(v=>v!==''))
let sequence=0
async function calculate(){
 const token=++sequence;result.value=null;error.value='';busy.value=false
 if(!allowed.value||!ready.value){busy.value=false;return}
 const numbers=fields.map(([key])=>Number(form[key]))
 if(numbers.some(value=>!Number.isFinite(value)||value<0)){error.value='费用和费率必须为有效的非负数字。';return}
 if(Number(form.package_weight_g)<=0){error.value='包裹重量必须大于0g。';return}
 if(Number(form.commission_percent)>=50){error.value='平台佣金必须小于50%，否则售价为成本两倍的公式无解。';return}
 if(Number(form.loss_percent)>=100){error.value='货损率必须小于100%。';return}
 busy.value=true
 try{const data=await workspaceRequest('/mkhp/cost-estimate','POST',{...form});if(token===sequence)result.value=data}
 catch(e){if(token===sequence)error.value=e.message}
 finally{if(token===sequence)busy.value=false}
}
watch(form,calculate)
watch(allowed,calculate)
function download(){const url=URL.createObjectURL(new Blob([JSON.stringify(result.value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='MHP-cost-estimate.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
</script>
<template><section class="cost"><h3>成本与售价测算</h3><p>所有金额使用人民币。请逐项填写；无费用时明确填 0。运费单位为“元/g”，使用包裹重量，不自动采用网页商品重量。</p><div class="fields"><label v-for="[key,title] in fields" :key="key">{{title}}<input v-model="form[key]" type="number" :min="key==='package_weight_g'?0.000001:0" :max="key==='commission_percent'?49.999999:key==='loss_percent'?99.999999:undefined" step="0.000001" inputmode="decimal"/></label><label>关税计税基数<select v-model="form.customs_base"><option disabled value="">请明确选择</option><option value="purchase">仅进货价</option><option value="purchase_freight">进货价＋运费</option></select></label></div><label class="permission"><input v-model="allowed" type="checkbox"/>允许将本面板数字发送到 MHP 后端自动测算；不发送至 AI，不保存业务数据库。</label><p v-if="busy" role="status">计算中…</p><p v-if="error" role="alert">{{error}}</p><template v-if="result"><table><tbody><tr v-for="[key,title] in [['freight','运费'],['customs','关税'],['base_cost','货损前成本'],['loss_allocation','货损摊销'],['commission','按售价计算佣金'],['cost','最终成本价'],['selling_price','建议商品售价（成本×2）']]" :key="key"><th>{{title}}</th><td>¥ {{result[key]}}</td></tr></tbody></table><p>{{result.notice}}</p><details><summary>计算公式</summary><p>C＝（进货价＋运费＋关税）÷（1－货损率）÷（1－2×佣金率），售价＝2×C。百分数先除以100。佣金达到50%时，这个定价约束无有限解。</p></details><button @click="download">下载测算 JSON</button></template></section></template>
<style scoped>.cost{border:1px solid var(--border-dim);border-radius:12px;padding:16px;margin:20px 0;line-height:1.65}.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.fields label{display:grid;gap:5px}.fields input,.fields select{max-width:100%;min-width:0;padding:9px;background:var(--bg-card-strong);color:var(--text-primary);border:1px solid var(--border-dim);border-radius:6px}.permission{display:block;margin:14px 0}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:6px;border-bottom:1px solid var(--border-dim)}button{padding:9px;cursor:pointer}</style>
