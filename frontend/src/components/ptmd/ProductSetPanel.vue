<script setup>
import { computed } from 'vue'
import MaterialCropEditor from './MaterialCropEditor.vue'
import ProductPlanAssistant from './ProductPlanAssistant.vue'
import {assetPreviewUrl} from '../../api/client'
const props=defineProps({modelValue:{type:Object,required:true},products:{type:Array,default:()=>[]},english:Boolean,busy:Boolean,credits:{type:Number,default:null},ready:Boolean})
const emit=defineEmits(['update:modelValue','apply-plan','planning'])
const local=computed(()=>props.modelValue.engine==='local')
const sources=computed(()=>[...new Map([...props.modelValue.pages.filter(p=>p.asset_id).map(p=>({asset_id:p.asset_id,filename:p.asset_id})),...props.products].map(p=>[p.asset_id,p])).values()])
const text=computed(()=>props.english?{
 name:'Product name / facts',requirements:'Creative requirements (background, style, prohibitions)',count:'Number of independent images',
 preset:'Russian washer · 8-image storyboard',notice:'Main image first, then details and use scenes. Confirm every claim and every page. No collages.',
 page:'Page',title:'Exact headline',copy:'Exact copy (one line per item)',direction:'Visual direction',source:'Product source image',
 main:'Main image',detail:'Product detail',scene:'Use scene',resolution:'Final long edge',quota:'Credits required',
 unavailable:'GPT Image 2 is not configured on the backend.',
 privacy:'GPT Image 2 receives the product original, up to 2 style references and your instructions. Provider fees apply; gateway compatibility is not yet verified.',
 size:'1200/2000 pixel output is available.',
}: {name:'商品名称 / 已确认事实',requirements:'创作要求（风格、背景、禁用内容）',count:'生成张数（每张独立输出）',preset:'俄语便携洗衣机 · 8张流程预设',
 notice:'先主图，再详情与使用场景。逐页填写并核实文案，不生成九宫格或拼图。',page:'第',title:'标题（逐字排版）',copy:'成品文案（每行一条）',
 direction:'本页画面要求',source:'本页商品素材',main:'主图',detail:'细节图',scene:'使用场景',resolution:'成品长边',quota:'需要生成额度',
 unavailable:'后端尚未配置 GPT Image 2。',privacy:'GPT Image 2 将接收商品原图、最多2张风格参考图和创作要求；上游另计费，渠道兼容性尚未实测。',size:'支持1200/2000像素输出。'})
function update(key,value){emit('update:modelValue',{...props.modelValue,...(key==='engine'?{text_rendering:value==='local'?'local':null}:{}),[key]:value})}
function count(value){const pages=props.modelValue.pages.slice(0,value);while(pages.length<value)pages.push({asset_id:props.modelValue.pages[0]?.asset_id||'',kind:pages.length?(local.value?'feature':'detail'):'main',title:'',copy_lines:[],direction:''});emit('update:modelValue',{...props.modelValue,count:value,pages})}
function page(index,key,value){const pages=props.modelValue.pages.map((p,i)=>i===index?{...p,...(key==='asset_id'?{crop:null,source_is_scene:false}:{}),...(key==='kind'&&value==='scene'?{crop:null}:{}),[key]:value}:p);update('pages',pages)}
function sourceUrl(item){return assetPreviewUrl(item.asset_id)}
function preset(){
 const aid=props.modelValue.pages[0]?.asset_id||props.products[0]?.asset_id||''
 const entries=[
  ['main','МИНИ-СТИРАЛЬНАЯ МАШИНА',['Объём 2 л','Аккумулятор 3000 мА·ч'],'完整主体，大俄文品名，少字，通透高级的商品主图'],
  ['detail','ОБЪЁМ 2 Л',['Для небольших вещей'], '展示真实透明机身与容量感，不增加刻度或配件'],
  ['detail','АККУМУЛЯТОР 3000 мА·ч',['До 15 использований после полной зарядки'],'围绕续航与便携，避免虚构充电器或内部电池结构'],
  ['detail','БЕРЕЖНАЯ СТИРКА',['Имитация ручной стирки'],'用真实商品洗护特征表现温和洗涤，不虚构杀菌率'],
  ['detail','ДВА РЕЖИМА',['Управление одной кнопкой'],'展示实际操作面板，不虚构具体模式名称和时长'],
  ['detail','ПРОДУМАННЫЕ ДЕТАЛИ',[],'展示本页选定素材里的真实上盖或控制面板特写'],
  ['detail','ВЛАГОЗАЩИЩЁННЫЙ КОРПУС',[],'展示机身维护与水滴质感，不推导IP防水等级，不表现浸泡机身'],
  ['scene','КОМПАКТНАЯ И УДОБНАЯ',['Для разных сценариев использования'],'真实居家台面使用场景，商品尺度自然，不添加随箱配件'],
 ]
 emit('update:modelValue',{product_name:'便携式洗衣机',requirements:'制作独立俄语电商图，风格与供应商素材不同，主图大品名少字，详情丰富且真实。所有产品及配件按商品素材，不添加额外配件。',language:'ru',resolution:'2000',count:8,reference_ids:props.modelValue.reference_ids,
  engine:props.modelValue.engine||'local',image_quality:props.modelValue.image_quality||null,text_rendering:props.modelValue.text_rendering??null,palette:props.modelValue.palette||'cool',
  pages:entries.map(([kind,title,copy_lines,direction],index)=>({kind:local.value&&kind==='detail'&&index!==5?'feature':kind,title,copy_lines,direction,asset_id:aid}))})
}
</script>
<template>
 <ProductPlanAssistant :english="english" :busy="busy" :language="modelValue.language" :count="modelValue.count" @apply="emit('apply-plan',$event)" @busy="emit('planning',$event)" />
 <fieldset class="set-plan" :disabled="busy">
  <label>{{ english?'Create with':'制作方式' }}<select class="set-plan__engine" :value="modelValue.engine||'local'" @change="update('engine',$event.target.value)"><option value="local">{{ english?'Photo layout (no AI calls)':'素材排版（不调用AI）' }}</option><option value="reference" :disabled="!ready">GPT Image 2</option></select></label>
  <label v-if="!local">{{ english?'AI quality':'AI生成质量' }}<select :value="modelValue.image_quality||''" @change="update('image_quality',$event.target.value)"><option value="" disabled>{{ english?'Choose quality':'请选择质量' }}</option><option value="low">{{ english?'Low':'低' }}</option><option value="medium">{{ english?'Medium':'中' }}</option><option value="high">{{ english?'High':'高' }}</option></select></label>
  <label v-if="!local">{{ english?'Typography (choose before generating)':'文字排版（生图前自行选择）' }}<select :value="modelValue.text_rendering||''" @change="update('text_rendering',$event.target.value)"><option value="" disabled>{{ english?'Choose typography':'请选择排字方式' }}</option><option value="local">{{ english?'Exact program typography':'程序精确排字' }}</option><option value="model">{{ english?'AI integrated lettering & layout':'模型直接生成图文' }}</option></select></label>
  <p v-if="!local">{{ english?'Program typography preserves exact text in fixed zones. AI lettering allows flexible composition but spelling and numbers may be wrong; regenerating may cost more. Choose based on your needs.':'程序排字：文字可精确控制，但版式受固定区域限制。模型图文：布局更自由，但外语拼写和数字可能出错，重做可能再次收费。请按需要选择。' }}</p>
  <p v-if="!local">{{ english?'Low: lower cost, fewer details. Medium: more details, higher cost. High: finer details, usually slower and more expensive. Actual gateway rates and results are unverified.':'低：成本较低，细节较少；中：细节增加，成本提高；高：更注重细节，通常更慢、费用更高。渠道实际价格与效果尚未实测，请自行选择。' }}</p>
  <p v-if="!local&&!ready" class="set-plan__warning">{{ text.unavailable }}</p>
  <p>{{ local?(english?'Uses your photos; no new scenes or API calls.':'使用真实素材排版，不生成新场景，不调用生图API。'):text.privacy }}</p>
  <label>{{ english?'Product name':'商品名称' }}<input maxlength="100" :placeholder="english?'e.g. Portable washer':'例如：便携式洗衣机'" :value="modelValue.product_name" @input="update('product_name',$event.target.value)" /></label>
  <div class="set-plan__common">
   <label>{{ english?'Images':'张数' }}<select :value="modelValue.count" @change="count(Number($event.target.value))"><option v-for="n in 9" :key="n" :value="n">{{ n }}</option></select></label>
   <label>{{ english?'Copy language':'文案语言' }}<select :value="modelValue.language" @change="update('language',$event.target.value)"><option value="ru">{{ english?'Russian':'俄语' }}</option><option value="en">{{ english?'English':'英语' }}</option></select></label>
  </div>
  <p :class="{'set-plan__warning':credits!==null&&credits<modelValue.count}">{{ text.quota }}: {{ modelValue.count }} / {{ credits ?? '—' }}</p>
  <details v-for="(item,index) in modelValue.pages" :key="index" :open="index===0" class="set-plan__page">
   <summary>{{ index+1 }} · {{ item.title || (index?text.detail:text.main) }}</summary>
   <label><input type="checkbox" :checked="item.no_overlay||false" @change="page(index,'no_overlay',$event.target.checked)" />{{ english?'No added text or decoration (source lettering remains)':'无附加文字与装饰（原图已有文字仍会保留）' }}</label><label>{{ item.no_overlay?(english?'Internal page title (not printed)':'页面内部标题（不印在图片上）'):(english?'Text on image':'图片标题') }}<textarea rows="2" maxlength="90" :placeholder="english?'Enter the exact headline in the selected language':(modelValue.language==='ru'?'请输入俄语标题（示例：МИНИ-СТИРАЛЬНАЯ МАШИНА）':'请输入英语标题（示例：MINI WASHING MACHINE）')" :value="item.title" @input="page(index,'title',$event.target.value)" /></label>
   <label v-if="!item.no_overlay">{{ english?'Selling points (optional)':'卖点文案（选填）' }}<textarea rows="2" :placeholder="english?'One per line, up to four; keep the main image concise':'每行一条，最多四条；主图建议简短'" :value="item.copy_lines.join('\n')" @input="page(index,'copy_lines',$event.target.value.split('\n'))" /></label>
   <details v-if="item.title_zh||item.copy_lines_zh?.length"><summary>{{ english?'Chinese translation (reference only)':'中文翻译（仅供核对，不印在成品上）' }}</summary><label>{{ english?'Headline translation':'标题翻译' }}<textarea rows="2" maxlength="150" :value="item.title_zh" @input="page(index,'title_zh',$event.target.value)" /></label><label>{{ english?'Selling point translations':'卖点翻译' }}<textarea rows="3" :value="(item.copy_lines_zh||[]).join('\n')" @input="page(index,'copy_lines_zh',$event.target.value.split('\n'))" /></label><p>{{ english?'Keep translations aligned after changing target copy.':'修改外语文案后，请同步核对中文翻译。' }}</p></details>
   <details class="set-plan__page-options">
    <summary>{{ english?'Adjust source & layout':'调整素材与版式' }}</summary>
   <label>{{ text.source }}<select :value="item.asset_id" @change="page(index,'asset_id',$event.target.value)"><option value="" disabled>—</option><option v-for="(asset,n) in sources" :key="asset.asset_id" :value="asset.asset_id">{{ n+1 }} · {{ asset.filename.slice(0,12) }}</option></select></label>
   <select :value="item.kind" :disabled="index===0" @change="page(index,'kind',$event.target.value)"><option value="main">{{ text.main }}</option><option value="feature">{{ english?'Selling points':'卖点页' }}</option><option value="detail">{{ text.detail }}</option><option value="scene">{{ text.scene }}</option></select>
   <template v-if="local">
    <label v-if="item.kind==='scene'" class="set-plan__scene"><input type="checkbox" :checked="item.source_is_scene" @change="page(index,'source_is_scene',$event.target.checked)" />{{ english?'This is an actual scene photograph.':'确认本页素材为真实场景照片。' }}</label>
    <p v-if="item.kind==='detail'&&!item.crop&&item.asset_id===modelValue.pages[0].asset_id" class="set-plan__warning">{{ english?'Select a close-up photo or draw a detail crop below.':'请选择真实特写素材，或在下方框选细节。' }}</p>
    <MaterialCropEditor v-if="item.asset_id&&item.kind!=='scene'" :src="sourceUrl(item)" :model-value="item.crop" :english="english" @update:model-value="page(index,'crop',$event)" />
   </template>
   <label>{{ text.direction }}<textarea rows="2" maxlength="400" :value="item.direction" @input="page(index,'direction',$event.target.value)" /></label>
   </details>
  </details>
  <details class="set-plan__advanced">
   <summary>{{ english?'More settings':'更多设置' }} · {{ modelValue.resolution }} px · 3:4</summary>
   <label>{{ text.resolution }}<select :value="modelValue.resolution" @change="update('resolution',$event.target.value)"><option v-for="edge in ['1200','2000']" :key="edge">{{ edge }}</option></select></label>
   <label v-if="local">{{ english?'Palette':'配色' }}<select :value="modelValue.palette||'cool'" @change="update('palette',$event.target.value)"><option value="cool">{{ english?'Cool white / navy':'冷白 / 藏蓝' }}</option><option value="warm">{{ english?'Warm ivory':'暖米色' }}</option><option value="mono">{{ english?'Monochrome':'简约灰白' }}</option></select></label>
   <button class="set-plan__preset" type="button" @click="preset">{{ text.preset }}</button>
   <p>{{ text.size }}</p>
   <p>{{ local?(english?'Requirements are notes. Use source, crop, palette and copy controls to implement them. Source lettering remains. Examples are for manual comparison. Each image uses 1 MHP credit.':'本地模式的画面要求仅作备注，需通过素材、裁切、配色和文案设置落实；原图已有文字会保留，示例图供人工对照。每张使用1个MHP额度。'):text.privacy }}</p>
  </details>
 </fieldset>
</template>
<style scoped>
.set-plan{border:0;padding:0;margin:0;display:flex;flex-direction:column;gap:12px;color:var(--text-primary);font-size:12px;min-width:0}.set-plan p{margin:0;color:var(--text-secondary);line-height:1.65}.set-plan label{display:flex;flex-direction:column;gap:6px}.set-plan input,.set-plan textarea,.set-plan select{font:inherit;width:100%;box-sizing:border-box;min-width:0;color:var(--text-primary);background:var(--bg-card-strong);border:1px solid var(--border-dim);border-radius:8px;padding:9px}.set-plan textarea{resize:vertical}.set-plan button{color:var(--neon-blue);border:1px solid var(--border-dim);background:var(--bg-glass);padding:10px;border-radius:10px;cursor:pointer}.set-plan__page{border-top:1px solid var(--border-dim);padding-top:10px}.set-plan__page summary{cursor:pointer;overflow-wrap:anywhere;margin-bottom:10px}.set-plan__page label,.set-plan__page>select{margin-bottom:10px}.set-plan p.set-plan__warning{color:#dc8d3d}
</style>
<style scoped>
.set-plan .set-plan__scene{flex-direction:row;align-items:center}.set-plan .set-plan__scene input{width:auto}
.set-plan__common{display:grid;grid-template-columns:1fr 1fr;gap:10px}.set-plan__advanced,.set-plan__page-options{border:1px solid var(--border-dim);padding:10px;border-radius:10px}.set-plan__advanced summary,.set-plan__page-options summary{cursor:pointer;color:var(--text-secondary);font-size:12px}.set-plan__advanced[open],.set-plan__page-options[open]{display:flex;flex-direction:column;gap:12px}.set-plan__advanced summary,.set-plan__page-options summary{margin-bottom:0}.set-plan__page-options[open]>summary,.set-plan__advanced[open]>summary{margin-bottom:10px}
</style>
