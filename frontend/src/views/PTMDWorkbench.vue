<script setup>
import { computed, onMounted, onUnmounted, ref, nextTick, watch } from 'vue'
import TemplateLibrary from '../components/TemplateLibrary.vue'
import {workspaceRequest} from '../api/client'
import { fetchAccount, claimDailyCheckin, cancelGeneration, assetPreviewUrl, downloadBlob, fetchAssets, fetchGeneration, fetchGenerations, generationPreviewUrl, requestGeneration, uploadAsset } from '../api/client'
import { useAppContext } from '../composables/useAppContext'
import { membershipMessages } from '../i18n/membership'
import { parameterLabel } from '../parameters'
import {fetchSetCapabilities,fetchProductSets,createProductSet,fetchProductSet,cancelProductSet,reviewSetPage,retrySetPage,setDownloadUrl} from '../api/client'
import ProductSetResults from '../components/ptmd/ProductSetResults.vue'
import PTMDNavPanel from '../components/ptmd/PTMDNavPanel.vue'
import PTMDCanvas from '../components/ptmd/PTMDCanvas.vue'
import PTMDParamsPanel from '../components/ptmd/PTMDParamsPanel.vue'
import PTMDPromptBar from '../components/ptmd/PTMDPromptBar.vue'
import PTMDTutorial from '../components/ptmd/PTMDTutorial.vue'
import { createSetDraft } from '../ptmdDraft'

const props = defineProps({
  t: { type: Object, required: true },
})

defineEmits(['go-home'])
const clone = value => JSON.parse(JSON.stringify(value))
const app=useAppContext()
const creditLabels=computed(()=>membershipMessages[props.t.account.breadcrumb==='Account'?'en':'zh'])
const credits=ref(null)
const creditBusy=ref(false)
const creditError=ref(false)
async function loadCredits(){
 try{credits.value=await fetchAccount();creditError.value=false;app.creditsChanged()}catch{creditError.value=true}
}
async function checkinCredits(){
 if(creditBusy.value)return
 creditBusy.value=true
 try{const result=await claimDailyCheckin();credits.value={...credits.value,...result};app.creditsChanged();showToast(result.awarded>0?creditLabels.value.awarded:creditLabels.value.checked)}catch(error){showToast(userError(error))}finally{creditBusy.value=false}
}

const products = ref([])
const references = ref([])
const referenceFolderId = ref('')
const referenceUploading = ref(false)
const setWorkflow = ref(true)
const defaultResolution = ref('2000')
const setSpec = ref(createSetDraft())
const plannerPreset = ref(null)
const setState = ref(null)
const planning = ref(false)
const referenceReady = ref(false)
let setRequest = null
const productsLoading = ref(true)
const productsError = ref(false)
const productsErrorMessage = ref('')
const productsPage = ref(0)
const productsTotal = ref(0)
let productsRequestVersion = 0
let generationAbort = null
let cancelling = false
let unmounted = false
function userError(error) {
  const msg = props.t.ptmd.prompt
  if (/API 已移除/.test(error?.message || '')) return props.t.account.breadcrumb === 'Account' ? 'AI model API removed. Local photo layout is still available.' : error.message
  if(error?.status===402)return creditLabels.value.exhausted
  if (error?.code === 'NETWORK') return msg.networkError
  if (error?.code === 'TIMEOUT') return msg.timeout
  if (error?.code === 'CANCELLED') return msg.cancelled
  if (props.t.ptmd.params.options.language[0] === 'Chinese' && /上游|重复提交/.test(error?.message || '')) return msg.timeout
  return props.t.ptmd.params.options.language[0] === 'Chinese' ? msg.serviceError : (error?.message || msg.serviceError)
}
onUnmounted(() => { unmounted = true; generationAbort?.abort(); clearTimeout(toastTimer) })
const selectedProduct = ref(null)
const activeSection = ref('products')
const generationParams = ref(null)
const designSpec = ref(null)
const paramsPanel = ref(null)
const promptBar=ref(null)
const templateDraft=computed(()=>({workflow:setWorkflow.value?'set':'single',prompt:promptBar.value?.getPrompt?.()||'',params:generationParams.value||{},design:designSpec.value,
 planner:setWorkflow.value&&plannerPreset.value?{preset_id:plannerPreset.value.preset_id}:null,
 spec:setWorkflow.value&&(!plannerPreset.value||(setSpec.value.preset_id===plannerPreset.value.preset_id&&['local','reference'].includes(setSpec.value.engine)))?clone(setSpec.value):null}))
function applyAiPlan(job){
 if(generating.value||planning.value||job.status!=='completed')return
 const plan=job.content
 const pages=plan.pages.map(p=>({asset_id:p.asset_id,kind:p.kind,title:p.title.target,title_zh:p.title.zh,
   copy_lines:p.copy_lines.map(c=>c.target),copy_lines_zh:p.copy_lines.map(c=>c.zh),direction:p.direction_zh,
   crop:null,source_is_scene:false,no_overlay:false}))
 setSpec.value={...setSpec.value,product_name:plan.product_name_zh,requirements:plan.brief_zh,
   language:job.request.language,count:pages.length,pages,preset_id:job.request.preset_id||null,
   ...(job.request.preset_id?{engine:'',image_quality:null}:{}),
   text_rendering:job.request.preset_id?null:(setSpec.value.engine==='reference'?null:'local'),
   reference_ids:setSpec.value.reference_ids.filter(id=>!pages.some(p=>p.asset_id===id))}
 setState.value=null
 if(job.request.preset_id!==plannerPreset.value?.preset_id)plannerPreset.value=job.request.preset_id?{preset_id:job.request.preset_id}:null
 selectedProduct.value=products.value.find(p=>p.asset_id===pages[0].asset_id)||{asset_id:pages[0].asset_id,filename:plan.product_name_zh}
 activeTab.value='original'
 showToast(english.value?'Bilingual plan applied. Choose production, typography and quality, then confirm image generation.':'双语方案已应用。请选择制作方式、排字方式与质量，再确认生图。')
}
async function applyTemplate(value){
 if(generating.value||planning.value)return
 if(value.origin==='mkhp'){
  setWorkflow.value=true
  setSpec.value={...setSpec.value,requirements:value.prompt,product_name:setSpec.value.product_name||(value.product_name||'').slice(0,100)}
  await nextTick();promptBar.value?.setPrompt(value.prompt)
  showToast(english.value?'MKHP prompt imported. Select the product original, GPT Image 2 and quality before generating.':'MKHP 提示词已填入，请选择商品原图、GPT Image 2 和生成质量，再确认生成。')
  return
 }
 setWorkflow.value=value.workflow==='set'
 plannerPreset.value=setWorkflow.value&&value.planner?{preset_id:value.planner.preset_id}:null
 if(setWorkflow.value){setSpec.value=createSetDraft(value.spec,selectedProduct.value?.asset_id||'',defaultResolution.value);setSpec.value.reference_ids=[];setState.value=null}
 if(plannerPreset.value){paramsOpen.value=true;activeSection.value='products'}
 designSpec.value=value.design||null
 await nextTick();paramsPanel.value?.restore({...value.params,resolution:['1200','2000'].includes(value.params?.resolution)?value.params.resolution:'2000'});promptBar.value?.setPrompt(value.prompt||'')
 showToast(english.value?'Template applied. Select material and review before generating.':'模板已套用，请选择素材并检查参数后生成')
}
async function removeAsset(item){
 if(generating.value||planning.value||!window.confirm(english.value?'Move this original to trash? Existing generated results remain.':'将这张原图移入回收站？已有生成结果保留，可在设置中心恢复。'))return
 try{await workspaceRequest('/assets/'+item.asset_id,'DELETE');if(selectedProduct.value?.asset_id===item.asset_id){selectedProduct.value=null;};setSpec.value.reference_ids=setSpec.value.reference_ids.filter(id=>id!==item.asset_id);setSpec.value.pages=setSpec.value.pages.map(p=>p.asset_id===item.asset_id?{...p,asset_id:''}:p);await loadAssets();showToast(english.value?'Moved to trash':'已移入回收站')}catch(e){showToast(e.message)}
}
const english = computed(() => props.t.account.breadcrumb === 'Account')
const uploadLoading = ref(false)
const activeTab = ref('original')
const lastGeneration = ref(null)
const generating = ref(false)
watch([generating,planning],([g,p])=>{app.workbenchBusy=g||p})
onUnmounted(()=>{app.workbenchBusy=false})
const generationResult = ref(null)
const generationHistory = ref([])
const historyLoading = ref(false)
const historyFilters = ref({})
const historyTotal = ref(0)
const historyPage = ref(0)
const historyError = ref('')
let historyRequestVersion = 0

const canDownload = computed(() => {
  if (activeTab.value === 'original') return !!selectedProduct.value
  if (activeTab.value === 'generated') return generationResult.value?.status === 'completed'
  return false
})

const canRegenerate = computed(() => !!lastGeneration.value)

const generationUrl = computed(() => {
  if (generationResult.value?.status !== 'completed') return ''
  return generationPreviewUrl(generationResult.value.generation_id)
})

const navOpen = ref(false)
const paramsOpen = ref(false)

const toastMsg = ref('')
let toastTimer = null

function showToast(message) {
  toastMsg.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMsg.value = ''
  }, 2600)
}

function mergeItems(previous, incoming, key) {
  return Array.from(new Map([...previous, ...incoming].map(item => [item[key], item])).values())
}

async function loadAssets(append = false) {
  if (append && (productsLoading.value || products.value.length >= productsTotal.value)) return
  const requestVersion = ++productsRequestVersion
  const page = append ? productsPage.value + 1 : 1
  productsLoading.value = true
  productsError.value = false
  try {
    const data = await fetchAssets(page,100,'product')
    if (unmounted || requestVersion !== productsRequestVersion) return
    const items = (data.items || []).filter(item=>item.role!=='reference')
    products.value = mergeItems(append ? products.value : [], items, 'asset_id')
    productsPage.value = page
    productsTotal.value = data.total || 0
  } catch (error) {
    if (unmounted || requestVersion !== productsRequestVersion) return
    productsError.value = true
    productsErrorMessage.value = userError(error)
    console.error('加载商品图片失败:', error)
  } finally {
    if (requestVersion === productsRequestVersion) productsLoading.value = false
  }
}

async function loadGenerationHistory(append = false) {
  if (append && (historyLoading.value || generationHistory.value.length >= historyTotal.value)) return
  const requestVersion = ++historyRequestVersion
  const page = append ? historyPage.value + 1 : 1
  const filters = { ...historyFilters.value }
  historyLoading.value = true
  historyError.value = ''
  try {
    const data = await fetchGenerations(filters, page)
    if (unmounted || requestVersion !== historyRequestVersion) return
    const items = Array.isArray(data.items) ? data.items : []
    generationHistory.value = mergeItems(append ? generationHistory.value : [], items, 'generation_id')
    historyTotal.value = data.total || 0
    historyPage.value = page
  } catch (error) {
    if (unmounted || requestVersion !== historyRequestVersion) return
    console.error('加载生成历史失败:', error)
    historyError.value = userError(error)
  } finally {
    if (requestVersion === historyRequestVersion) historyLoading.value = false
  }
}

function handleHistoryFilterChange(filters) {
  historyFilters.value = { ...filters }
  generationHistory.value = []
  historyPage.value = 0
  historyTotal.value = 0
  loadGenerationHistory()
}

onMounted(async () => {
  const referenceRequest=app.referenceLibraryToOpen
  app.referenceLibraryToOpen=null
  if(referenceRequest){
    referenceFolderId.value=referenceRequest.folder_id
    if(referenceRequest.asset_id)setSpec.value.reference_ids=[referenceRequest.asset_id]
    activeSection.value='products';navOpen.value=true
  }
  await loadAssets()
  loadGenerationHistory()
  loadCredits()
  await loadSetHistory(!referenceRequest)
  try{
    const settings=await workspaceRequest('/workspace/settings')
    if(unmounted)return
    const resolution=String(settings.preferences?.resolution)
    if(['1200','2000'].includes(resolution)){
      defaultResolution.value=resolution
      paramsPanel.value?.restore({resolution})
      if(!setState.value)setSpec.value={...setSpec.value,resolution}
    }
  }catch{}
  if(app.templateToApply){const value=app.templateToApply;app.templateToApply=null;await applyTemplate(value)}
})

function selectProduct(product) {
  if(generating.value||planning.value)return
  const oldId=selectedProduct.value?.asset_id
  selectedProduct.value = product
  activeSection.value = 'products'
  navOpen.value = false
  activeTab.value = 'original'
  setSpec.value={...setSpec.value,pages:setSpec.value.pages.map(page=>!page.asset_id||page.asset_id===oldId?{...page,asset_id:product.asset_id}:page)}
}

async function handleUploadFile(files) {
  if(generating.value||planning.value||uploadLoading.value)return
  uploadLoading.value = true
  try {
    let record
    for(const file of (Array.isArray(files)?files:[files])){const item=await uploadAsset(file);record ||= item}
    await loadAssets()
    if(record)selectProduct(record)
    showToast(props.t.ptmd.products.uploadSuccess)
  } catch (error) {
    console.error('上传失败:', error)
    showToast(`${props.t.ptmd.products.uploadFailed}：${userError(error)}`)
  } finally {
    uploadLoading.value = false
  }
}

async function uploadReferences(files){
 if(generating.value||planning.value||referenceUploading.value||!files.length)return
 referenceUploading.value=true
 try{
  for(const file of files){const item=await uploadAsset(file,'reference');if(setSpec.value.reference_ids.length<2)setSpec.value.reference_ids.push(item.asset_id)}
  await loadAssets()
 }catch(error){showToast(userError(error))}finally{referenceUploading.value=false}
}
function toggleReference(id){
 if(generating.value||planning.value)return
 const ids=setSpec.value.reference_ids
 if(ids.includes(id))setSpec.value={...setSpec.value,reference_ids:ids.filter(value=>value!==id)}
 else if(ids.length<2)setSpec.value={...setSpec.value,reference_ids:[...ids,id]}
 else showToast(english.value?'Select at most two examples.':'最多选择2张示例图')
}
function applySet(state){
 setState.value=state
 const current=state.items.find(item=>item.generation_id===generationResult.value?.generation_id)
 generationResult.value=current||state.items.find(item=>item.status==='completed')||state.items[0]||null
 activeTab.value='generated'
}
async function pollSet(id){
 const deadline=Date.now()+9*260000
 while(!unmounted&&Date.now()<deadline){
  const state=await fetchProductSet(id);if(unmounted)return state;applySet(state)
  if(state.status!=='pending')return state
  await new Promise(resolve=>setTimeout(resolve,1200))
 }
 if(!unmounted)showToast(english.value?'Still processing. Check history later.':'任务仍在处理，请稍后在历史中查看')
}
async function loadSetHistory(restoreLast=true){
 try{
  referenceReady.value=(await fetchSetCapabilities()).reference_editing
  if(!restoreLast)return
  const data=await fetchProductSets()
  if(unmounted)return
  if(data.items?.length){
   const state=data.items[0];setSpec.value=clone(state.spec);plannerPreset.value=state.spec.preset_id?{preset_id:state.spec.preset_id}:null;applySet(state)
   if(state.status==='pending'){generating.value=true;try{await pollSet(state.batch_id)}finally{generating.value=false;loadCredits();loadGenerationHistory()}}
  }
 }catch(error){referenceReady.value=false}
}
async function generateSet(promptText='',fresh=false){
 if(generating.value||planning.value)return
 if(plannerPreset.value&&setSpec.value.preset_id!==plannerPreset.value.preset_id){showToast(english.value?'Review and apply the official storyboard first.':'请先完成官方模板策划并核对应用');return}
 if(!['local','reference'].includes(setSpec.value.engine)){showToast(english.value?'Choose production method first.':'请先自行选择制作方式');return}
 if(setSpec.value.engine!=='local'&&!referenceReady.value){showToast(english.value?'GPT Image 2 is not configured.':'后端尚未配置 GPT Image 2');return}
 const spec=clone(setSpec.value)
 spec.product_name=spec.product_name.trim()
 for(const page of spec.pages){page.copy_lines=page.copy_lines.filter(line=>line.trim())}
 if(promptText.trim()&&!spec.requirements.includes(promptText.trim()))spec.requirements=[spec.requirements,promptText.trim()].filter(Boolean).join('\n')
 if(!spec.product_name||spec.pages.some(page=>!page.asset_id||!page.title.trim())){showToast(english.value?'Select a product source and enter every headline.':'请填写商品名称，并为每一页选择商品素材、填写标题');return}
 if(spec.requirements.length>2000){showToast(english.value?'Shorten the creative requirements.':'创作要求超过2000字符，请精简');return}
 if(credits.value?.available<spec.count){showToast(english.value?`This set requires ${spec.count} credits.`:`本套需要${spec.count}张生成额度，当前不足；请减少张数或每日签到`);return}
 if(spec.engine!=='local'){
  if(!spec.text_rendering){showToast(english.value?'Choose typography first.':'请先选择程序排字或模型图文排版');return}
  if(!spec.image_quality){showToast(english.value?'Choose AI quality first.':'请先自行选择AI生成质量');return}
  if(!window.confirm(english.value?`Send product originals, ${spec.reference_ids.length} style references and instructions to GPT Image 2? Generate ${spec.count} images at ${spec.image_quality} quality, typography: ${spec.text_rendering}. AI lettering may contain errors. Provider fees apply in addition to MHP credits. No automatic retry.`:`确认向 GPT Image 2 发送商品原图、${spec.reference_ids.length}张风格参考图和创作要求？本次生成${spec.count}张，质量为${spec.image_quality}，排字方式：${spec.text_rendering==='model'?'模型图文（须核对外语拼写与数字）':'程序精确排字'}。除MHP额度外，上游另计费，失败不自动重试。`))return
 }
 const fingerprint=JSON.stringify(spec)
 if(fresh||!setRequest||setRequest.fingerprint!==fingerprint)setRequest={fingerprint,payload:{request_id:crypto.randomUUID(),spec,confirm_send:spec.engine!=='local'}}
 generating.value=true;cancelling=false
 try{
  let state=await createProductSet(setRequest.payload);setSpec.value=clone(state.spec);applySet(state)
  if(cancelling)state=await cancelProductSet(state.batch_id)
  if(state.status==='pending')state=await pollSet(state.batch_id)
  if(state)applySet(state)
  showToast(state?.status==='completed'?(english.value?'Set ready. Review each image.':'套图制作完成，请逐页核对商品与文案'):state?.status==='failed'?(english.value?'Image processing failed. Check sources and settings.':'图片处理失败，请检查素材、设置和服务状态'):props.t.ptmd.prompt.cancelled)
 }catch(error){showToast(userError(error))}
 finally{generating.value=false;if(!unmounted){loadCredits();loadGenerationHistory()}}
}
async function reviewPage(gid,payload){try{applySet(await reviewSetPage(setState.value.batch_id,gid,payload))}catch(error){showToast(userError(error))}}
async function regeneratePage(gid){
 if(generating.value||planning.value)return
 const row=setState.value.items.find(item=>item.generation_id===gid)
 if(!row)return
 const confirmSend=setSpec.value.engine!=='local'
 if(confirmSend&&!window.confirm(english.value?'Send images and instructions to GPT Image 2 again? Regenerating this page incurs new provider fees and one MHP credit.':'再次向 GPT Image 2 发送图片和创作要求？重生成本页会再次产生上游费用并占用1个MHP额度。'))return
 generating.value=true
 try{const state=await retrySetPage(setState.value.batch_id,gid,setSpec.value.pages[row.page_index],confirmSend);applySet(state);await pollSet(state.batch_id)}
 catch(error){showToast(userError(error))}finally{generating.value=false;loadCredits();loadGenerationHistory()}
}
async function downloadSet(edge){try{await downloadBlob(setDownloadUrl(setState.value.batch_id,edge),`MHP-${edge}.zip`)}catch(error){showToast(userError(error))}}

async function handleGenerate(promptText='') {
  if(setWorkflow.value){await generateSet(promptText);return}
  showToast(english.value?'Use the storyboard to create one or more GPT Image 2 images.':'请使用套图工作台，通过 GPT Image 2 制作1张或多张图片')
}

async function handleCancel() {
  if(setWorkflow.value){cancelling=true;if(setState.value?.status==='pending'){try{applySet(await cancelProductSet(setState.value.batch_id))}catch(error){showToast(userError(error))}}return}
  if (cancelling) return
  cancelling = true
  if (!generationResult.value?.generation_id) {
    showToast(props.t.ptmd.prompt.cancelPending)
    return
  }
  try {
    const record = await cancelGeneration(generationResult.value.generation_id)
    generationAbort?.abort()
    generationResult.value = record
    showToast(record.status === 'completed' ? props.t.ptmd.prompt.generateSuccess : props.t.ptmd.prompt.cancelled)
    loadGenerationHistory()
    loadCredits()
  } catch (error) {
    cancelling = false
    showToast(userError(error))
  }
}

async function handleRegenerate() { if(setWorkflow.value) await generateSet('',true) }

async function handleDownload() {
  let url, filename
  if (activeTab.value === 'original' && selectedProduct.value) {
    url = assetPreviewUrl(selectedProduct.value.asset_id)
    filename = selectedProduct.value.filename || 'original.png'
  } else if (activeTab.value === 'generated' && generationResult.value) {
    url = generationPreviewUrl(generationResult.value.generation_id)
    filename = `generation_${generationResult.value.generation_id}.png`
  } else {
    showToast(props.t.ptmd.prompt.downloadEmpty)
    return
  }
  try {
    await downloadBlob(url, filename)
  } catch (error) {
    console.error('下载失败:', error)
    showToast(`${props.t.ptmd.prompt.downloadFailed}：${userError(error)}`)
  }
}

function handleParamsChange(params) {
  generationParams.value = { ...params }
}

async function handleSelectGeneration(gen) {
  if(generating.value||planning.value)return
  if(gen.batch_id){try{const state=await fetchProductSet(gen.batch_id);if(unmounted||generating.value||planning.value)return;setWorkflow.value=true;setSpec.value=clone(state.spec);plannerPreset.value=state.spec.preset_id?{preset_id:state.spec.preset_id}:null;applySet(state);generationResult.value=state.items.find(item=>item.generation_id===gen.generation_id)||gen}catch(error){showToast(userError(error))}return}
  setWorkflow.value=false
  generationResult.value = gen
  activeTab.value = 'generated'
  selectedProduct.value = null
  const params = {ratio:gen.ratio||'1:1',resolution:gen.resolution||'2000',language:gen.language||'zh',scene:gen.scene||'livingroom',platform:gen.platform||'ozon',style:gen.style||'premium'}
  designSpec.value = gen.design ? clone(gen.design) : null
  paramsPanel.value?.restore(params)
  if (gen.status === 'completed') lastGeneration.value = { prompt: gen.prompt, payload: { prompt: gen.prompt, asset_id: gen.asset_id, design:gen.design||null, params } }
  navOpen.value = false
}
</script>

<template>
  <div class="wb-root">
    <div class="wb-creditbar">
      <span>{{ creditLabels.available }}: <strong>{{ credits?.available ?? '—' }}</strong></span>
      <button type="button" :disabled="creditBusy||credits?.checked_in_today" @click="checkinCredits">{{ credits?.checked_in_today?creditLabels.checked:creditLabels.checkin }}</button>
      <button type="button" @click="app.showView('accountManagement')">{{ creditLabels.account }}</button>
      <button v-if="creditError" type="button" @click="loadCredits">{{ creditLabels.refresh }}</button>
      <PTMDTutorial :english="english" :user-id="app.user?.user_id || 'browser'" />
    </div>

    <div v-if="productsError" class="wb-banner">
      {{ productsErrorMessage }}
      <button class="wb-banner__retry" type="button" @click="loadAssets()">
        ↻ {{ t.ptmd.taskRunning }}
      </button>
    </div>

    <div class="wb-main">
      <PTMDNavPanel
        :t="t"
        :products="products"
        :products-total="productsTotal"
        :references="references"
        :reference-folder-id="referenceFolderId"
        :selected-references="setSpec.reference_ids"
        :reference-uploading="referenceUploading"
        :set-workflow="setWorkflow"
        :local-layout="setSpec.engine==='local'"
        :busy="generating || planning"
        :products-loading="productsLoading"
        :active-section="activeSection"
        :selected-id="selectedProduct ? selectedProduct.asset_id : ''"
        :selected-product="selectedProduct"
        :upload-loading="uploadLoading"
        :generations="generationHistory"
        :generations-loading="historyLoading"
        :generations-total="historyTotal"
        :generations-error="historyError"
        class="wb-nav-drawer"
        :class="{ 'wb-nav-drawer--open': navOpen }"
        @select-section="activeSection = $event; navOpen = false"
        @select-product="selectProduct"
        @upload-file="handleUploadFile"
        @upload-references="uploadReferences"
        @toggle-reference="toggleReference"
        @select-generation="handleSelectGeneration"
        @filter-change="handleHistoryFilterChange"
        @load-more-products="loadAssets(true)"
        @load-more-history="loadGenerationHistory(true)"
        @retry-history="loadGenerationHistory()"
        @delete-asset="removeAsset"
        @reference-deleted="setSpec.reference_ids=setSpec.reference_ids.filter(id=>id!==$event)"
      ><template #templates><TemplateLibrary :draft="templateDraft" @apply="applyTemplate" /></template></PTMDNavPanel>

      <div class="wb-center">
        <ProductSetResults v-if="setWorkflow&&setState" :batch="setState" :english="english" :selected-id="generationResult?.generation_id" :busy="generating" @select="generationResult=$event;activeTab='generated'" @review="reviewPage" @retry="regeneratePage" @download="downloadSet" />
        <PTMDCanvas
          :t="t"
          :product="selectedProduct"
          :generation="generationResult"
          :active-tab="activeTab"
          :generation-url="generationUrl"
          :generating="generating"
          @update:active-tab="activeTab = $event"
        />
      </div>

      <PTMDParamsPanel
        ref="paramsPanel"
        :t="t"
        v-model:design="designSpec"
        v-model:set-workflow="setWorkflow"
        v-model:set-spec="setSpec"
        :planner-preset="plannerPreset"
        :default-resolution="defaultResolution"
        :products="products"
        :busy="generating || planning"
        @planning="planning=$event"
        @apply-plan="applyAiPlan"
        :credits="credits?.available ?? null"
        :reference-ready="referenceReady"
        class="wb-params-drawer"
        :class="{ 'wb-params-drawer--open': paramsOpen }"
        @change="handleParamsChange"
      />

      <div class="wb-float-actions">
        <button class="wb-fab" type="button" :title="t.ptmd.nav.products" @click="navOpen = true">
          <svg
            class="icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M3 6 h18 v12 H3 Z" />
            <path d="M9 6 v12" />
          </svg>
        </button>
        <button class="wb-fab" type="button" :title="t.ptmd.params.title" @click="paramsOpen = true">
          <svg
            class="icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M4 21 v-7 M4 10 V3 M12 21 v-9 M12 8 V3 M20 21 v-5 M20 12 V3" />
            <path d="M2 14 h4 M10 8 h4 M18 16 h4" />
          </svg>
        </button>
      </div>

      <Transition name="wb-backdrop">
        <div
          v-if="navOpen || paramsOpen"
          class="wb-backdrop"
          @click="navOpen = false; paramsOpen = false"
        ></div>
      </Transition>
    </div>

    <PTMDPromptBar
      ref="promptBar"
      :t="t"
      :can-download="canDownload"
      :can-regenerate="(setWorkflow?!!setState:canRegenerate) && credits?.available !== 0"
      :available-credits="credits?.available ?? null"
      :params="setWorkflow ? {ratio:'3:4',resolution:setSpec.resolution,language:setSpec.language} : generationParams"
      :set-mode="setWorkflow"
      v-model:requirements="setSpec.requirements"
      :required-credits="setWorkflow?setSpec.count:1"
      :generating="generating"
      :planning="planning"
      @generate="handleGenerate"
      @regenerate="handleRegenerate"
      @cancel="handleCancel"
      @download="handleDownload"
    />

    <div class="wb-toast" :class="{ 'wb-toast--show': toastMsg }">{{ toastMsg }}</div>
  </div>
</template>

<style scoped>
.poster-preview{position:fixed;inset:0;background:rgba(5,12,25,.87);z-index:150;display:flex;align-items:center;justify-content:center;padding:20px}.poster-preview>div{max-width:720px;text-align:center;color:white}.poster-preview img{display:block;max-height:75vh;max-width:100%;margin:auto;object-fit:contain}.poster-preview p{font-size:12px;line-height:1.6}.poster-preview button{border:1px solid #7890ab;border-radius:10px;padding:8px 16px;background:#15324c;color:white;cursor:pointer}
.wb-creditbar{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:6px 18px;background:var(--bg-sidebar);font-size:12px;color:var(--text-secondary);border-bottom:1px solid var(--border-dim)}.wb-creditbar button{border:1px solid var(--border-dim);border-radius:8px;background:var(--bg-glass);color:var(--text-primary);padding:4px 9px}.wb-creditbar button:disabled{opacity:.5;cursor:not-allowed}

.wb-root {
  position: relative;
  display: flex;
  flex-direction: column;
  height: calc(100dvh - var(--topbar-height));
  overflow: hidden;
  background: transparent;
}

.wb-main {
  position: relative;
  flex: 1;
  display: flex;
  min-height: 0;
}

.wb-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.wb-banner {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(239, 68, 68, 0.16);
  border-top: 1px solid rgba(239, 68, 68, 0.4);
  color: var(--text-secondary);
  font-size: 13px;
}

.wb-banner__retry {
  color: var(--neon-blue);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-full);
  padding: 4px 12px;
  background: var(--bg-glass);
}

.wb-float-actions {
  position: absolute;
  right: 14px;
  top: 14px;
  z-index: 35;
  display: none;
  flex-direction: column;
  gap: 8px;
}

.wb-fab {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1px solid var(--border-glow);
  background: var(--bg-card-strong);
  color: var(--text-primary);
  box-shadow: var(--shadow-card);
  transition: border-color var(--transition-fast), box-shadow var(--transition-smooth),
    transform var(--transition-fast);
}

.wb-fab:hover {
  border-color: var(--neon-blue);
  box-shadow: 0 0 12px var(--glow-blue);
  transform: translateY(-1px);
}

.wb-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  z-index: 60;
}

.wb-backdrop-enter-active,
.wb-backdrop-leave-active {
  transition: opacity var(--transition-fast);
}

.wb-backdrop-enter-from,
.wb-backdrop-leave-to {
  opacity: 0;
}

@media (min-width: 1024px) {
  .wb-backdrop,
  .wb-float-actions {
    display: none;
  }
}

@media (max-width: 1023px) {
  :deep(.wb-nav-drawer) {
    position: fixed;
    top: var(--topbar-height);
    bottom: 0;
    left: 0;
    z-index: 70;
    transform: translateX(-100%);
    transition: transform var(--transition-smooth);
    box-shadow: 8px 0 30px rgba(0, 0, 0, 0.4);
  }
  :deep(.wb-nav-drawer--open) {
    transform: translateX(0);
  }
  :deep(.wb-params-drawer) {
    position: fixed;
    top: var(--topbar-height);
    bottom: 0;
    right: 0;
    z-index: 70;
    transform: translateX(100%);
    transition: transform var(--transition-smooth);
    box-shadow: -8px 0 30px rgba(0, 0, 0, 0.4);
  }
  :deep(.wb-params-drawer--open) {
    transform: translateX(0);
  }
  .wb-float-actions {
    display: flex;
  }
}

@media (max-width: 767px) {
  .wb-float-actions {
    right: 10px;
    top: 10px;
  }
}
</style>
