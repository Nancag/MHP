<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { assetPreviewUrl, workspaceRequest } from '../../api/client'

const props = defineProps({ english: Boolean, busy: Boolean, language: String, count: Number, preset: { type: Object, default: null } })
const emit = defineEmits(['apply', 'busy'])
const cap = ref(null), models = computed(() => cap.value?.models || [])
const model = ref(''), language = ref(''), count = ref(null)
const wishes = ref(''), facts = ref(''), importId = ref(''), confirmed = ref(false)
const imports = ref([]), assets = ref([]), imageIds = ref([]), total = ref(0), assetPage = ref(0), importPage = ref(0)
const histories = ref([]), job = ref(null), content = ref(null), checked = ref(false)
const loading = ref(false), running = ref(false), saving = ref(false), error = ref('')
const locked = computed(() => props.busy || loading.value || running.value || saving.value)
const selectedImport = computed(() => imports.value.find(i => i.import_id === importId.value))
const selectedPreset = computed(() => cap.value?.presets?.find(p => p.preset_id === props.preset?.preset_id))
const counts = computed(() => selectedPreset.value?.counts || (props.preset ? [7,8,9] : [1,2,3,4,5,6,7,8,9]))
const importedFields = computed(() => Object.entries(selectedImport.value?.result?.fields || {}).filter(([, f]) => f?.value))
let loaded = false, disposed = false, attempt = null, pollVersion = 0
const tr = (zh, en) => props.english ? en : zh
onUnmounted(() => { disposed = true; ++pollVersion; emit('busy', false) })
watch(() => props.preset, async (value, previous) => {
  if (!value && !previous) return
  model.value = ''; language.value = 'ru'; count.value = null
  facts.value = ''; importId.value = ''; imageIds.value = []; confirmed.value = false
  wishes.value = ''; job.value = null; content.value = null; checked.value = false; attempt = null
  if (!value) { language.value = ''; return }
  if (!loaded) await load()
  if (!disposed && props.preset === value && !wishes.value) wishes.value = selectedPreset.value?.wishes || ''
}, { immediate: true })

function showJob(value) {
  if (!value) return
  job.value = value
  content.value = value.status === 'completed' ? JSON.parse(JSON.stringify(value.content)) : null
  checked.value = false
}
async function load() {
  if (locked.value) return
  loading.value = true; error.value = ''
  try {
    const results = await Promise.allSettled([
      workspaceRequest('/product-plans/capabilities'), workspaceRequest('/mkhp/imports?page=1'),
      workspaceRequest('/assets?page=1&page_size=60'), workspaceRequest('/product-plans'),
    ])
    if (disposed) return
    const [c, i, a, h] = results
    if (c.status === 'fulfilled') cap.value = c.value
    if (i.status === 'fulfilled') { imports.value = i.value.items; importPage.value = 1 }
    if (a.status === 'fulfilled') { assets.value = a.value.items; total.value = a.value.total; assetPage.value = 1 }
    if (h.status === 'fulfilled') histories.value = h.value.items
    const failure = results.find(r => r.status === 'rejected')
    if (failure) throw failure.reason
    loaded = true
    const pending = histories.value.find(h => h.status === 'pending')
    if (pending) { showJob(pending); resume(pending.plan_id) }
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function open(event) {
  if (event.target.open && !loaded) {
    language.value ||= props.language || ''
    if (!props.preset) count.value ??= props.count || null
    load()
  }
}
async function moreAssets() {
  if (locked.value) return
  loading.value = true
  try {
    const result = await workspaceRequest(`/assets?page=${assetPage.value + 1}&page_size=60`)
    if (disposed) return
    assets.value = [...new Map([...assets.value, ...result.items].map(i => [i.asset_id, i])).values()]
    assetPage.value++; total.value = result.total
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function moreImports() {
  if (locked.value) return
  loading.value = true
  try {
    const result = await workspaceRequest(`/mkhp/imports?page=${importPage.value + 1}`)
    if (disposed) return
    imports.value = [...new Map([...imports.value, ...result.items].map(i => [i.import_id, i])).values()]
    importPage.value++
    if (!result.items.length) error.value = tr('已加载所有采集记录', 'All imports loaded')
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function selectImage(id) {
  if (locked.value) return
  confirmed.value = false
  if (imageIds.value.includes(id)) imageIds.value = imageIds.value.filter(a => a !== id)
  else if (imageIds.value.length < 9) imageIds.value = [...imageIds.value, id]
  else error.value = tr('最多选择9张商品素材', 'Select up to 9 product images')
}
async function resume(id) {
  const version = ++pollVersion
  running.value = true; emit('busy', true)
  try {
    const deadline = Date.now() + 180000
    while (!disposed && version === pollVersion && Date.now() < deadline) {
      const value = await workspaceRequest('/product-plans/' + id)
      if (disposed || version !== pollVersion) return
      showJob(value)
      if (value.status !== 'pending') {
        histories.value = [value, ...histories.value.filter(h => h.plan_id !== id)]
        return
      }
      await new Promise(resolve => setTimeout(resolve, 1400))
    }
    if (!disposed) error.value = tr('任务仍可能在处理；请用“查看任务状态”，不要重复调用。', 'Processing may continue. Check status instead of submitting again.')
  } catch (e) { if (!disposed) error.value = e.message }
  finally { if (version === pollVersion) { running.value = false; emit('busy', false) } }
}
async function generate(fresh = false) {
  if (locked.value) return
  error.value = ''
  if (props.preset && (!selectedPreset.value || !counts.value.includes(Number(count.value)) || language.value !== selectedPreset.value.language)) {
    error.value = tr('请先加载官方模板，并选择7/8/9张俄语方案。', 'Load the official preset and select 7, 8 or 9 Russian images.')
    return
  }
  if (!model.value || !language.value || !count.value || !imageIds.value.length || !wishes.value.trim() || !confirmed.value || (!importId.value && !facts.value.trim())) {
    error.value = tr('请选择模型、语言、张数及商品图片，填写需求与商品事实，并勾选核对。', 'Select model, language, count and images; enter wishes and confirmed facts, then check the confirmation.')
    return
  }
  const payload = { model: model.value, language: language.value, count: Number(count.value), image_ids: [...imageIds.value],
    import_id: importId.value || null, confirmed_facts: facts.value.trim(), wishes: wishes.value.trim(), confirm_send: true, confirm_facts: true }
  if (props.preset) payload.preset_id = props.preset.preset_id
  const fingerprint = JSON.stringify(payload)
  if (!window.confirm(tr(`确认向 ${model.value} 发送所选${imageIds.value.length}张商品图片、已核对字段和需求，生成${count.value}页双语方案？可能产生文案接口费用；本次不生图，失败不自动重试。图片理解、参数及翻译仍需逐页核对。`,
    `Send ${imageIds.value.length} selected images, confirmed facts and wishes to ${model.value} for a ${count.value}-page bilingual plan? Provider fees may apply. No image generation or automatic retries. Review image interpretation, facts and translations page by page.`))) return
  if (fresh || !attempt || attempt.fingerprint !== fingerprint) attempt = { fingerprint, payload: { ...payload, request_id: crypto.randomUUID() } }
  running.value = true; emit('busy', true)
  try {
    const value = await workspaceRequest('/product-plans', 'POST', attempt.payload)
    if (disposed) return
    showJob(value)
    await resume(value.plan_id)
  } catch (e) { if (!disposed) error.value = e.message }
  finally { if (!disposed) { running.value = false; emit('busy', false) } }
}
async function apply() {
  if (locked.value || !checked.value || !content.value) return
  if (!window.confirm(tr('确认保存已编辑的双语方案，并替换工作台当前逐页文案与画面要求？此操作不调用模型、不开始生图。', 'Save this edited bilingual plan and replace the current storyboard? No model call or image generation.'))) return
  saving.value = true; emit('busy', true); error.value = ''
  try {
    const value = await workspaceRequest('/product-plans/' + job.value.plan_id, 'PUT', { content: content.value, confirm_save: true })
    if (disposed) return
    showJob(value)
    histories.value = [value, ...histories.value.filter(h => h.plan_id !== value.plan_id)]
    saving.value = false; emit('busy', false)
    emit('apply', value)
  } catch (e) { error.value = e.message }
  finally { saving.value = false; emit('busy', false) }
}
function addLine(page) {
  if (locked.value || page.copy_lines.length >= 4) return
  page.copy_lines.push({ target: '', zh: '' }); checked.value = false
}
function removeLine(page, index) {
  if (locked.value) return
  page.copy_lines.splice(index, 1); checked.value = false
}
</script>

<template>
  <details class="plan-assistant" :open="!!preset" @toggle="open">
    <summary>{{ tr('AI 帮我写需求与文案', 'AI brief & bilingual storyboard') }}</summary>
    <p>{{ tr('选商品资料 → 大白话描述 → 双语方案 → 核对后应用。调用文案与生图分别确认。', 'Select product materials → describe your wishes → bilingual plan → review and apply. Text and image calls require separate confirmation.') }}</p>
    <template v-if="selectedPreset">
      <strong>{{ selectedPreset.name }}</strong>
      <ul><li v-for="rule in selectedPreset.rules" :key="rule">{{ rule }}</li></ul>
      <p>{{ tr('截图参数待核对清单：以下均未确认为事实，不会自动发送给模型。仅把已核实内容填写到商品事实。', 'Reference claim checklist: these are unverified and are not sent to the model. Enter only verified information in product facts.') }}</p>
      <ul><li v-for="item in selectedPreset.checklist" :key="item">{{ item }}</li></ul>
    </template>
    <button type="button" :disabled="locked" @click="load">{{ tr('刷新资料与任务', 'Refresh materials & jobs') }}</button>
    <fieldset :disabled="locked">
      <label>{{ tr('商品资料（选填）', 'Imported facts (optional)') }}
        <select v-model="importId" @change="confirmed = false"><option value="">{{ tr('手动填写事实', 'Enter facts manually') }}</option>
          <option v-for="item in imports.filter(i => i.status === 'completed')" :key="item.import_id" :value="item.import_id">{{ item.result?.fields?.name?.value || item.source_url }}</option>
        </select>
      </label>
      <button type="button" @click="moreImports">{{ tr('加载更多采集记录', 'More imports') }}</button>
      <dl v-if="importedFields.length"><template v-for="[key, field] in importedFields" :key="key"><dt>{{ key }}</dt><dd>{{ field.value }}</dd></template></dl>
      <label>{{ tr('已确认商品名称与参数 / 补充或更正事实', 'Confirmed product name & facts / corrections') }}<textarea v-model="facts" maxlength="4000" rows="3" :placeholder="tr('填写真实参数；未核实的防水、阻燃等宣传不要填写为事实。', 'Enter verified facts only. Do not treat unverified supplier claims as facts.')" @input="confirmed = false" /></label>
      <label>{{ tr('选择给文案模型看的商品素材（1–9张，不会自动选中）', 'Product images for the text model (1–9, selected by you)') }}</label>
      <div class="plan-images">
        <label v-for="asset in assets" :key="asset.asset_id" :title="asset.filename">
          <input type="checkbox" :checked="imageIds.includes(asset.asset_id)" @change="selectImage(asset.asset_id)" />
          <img :src="assetPreviewUrl(asset.asset_id)" loading="lazy" :alt="asset.filename" />
          <span>{{ asset.asset_id.slice(0, 6) }}</span>
        </label>
      </div>
      <span>{{ imageIds.length }} / 9 · {{ assets.length }} / {{ total }}</span>
      <button v-if="assets.length < total" type="button" @click="moreAssets">{{ tr('加载更多素材', 'More images') }}</button>
      <p>{{ tr('图片用于理解外观和安排画面；图片上的参数仍需核对，模型不会据此验证功能。', 'Images help with appearance and composition. Printed claims still require seller verification.') }}</p>
      <label>{{ tr('大白话需求', 'Your creative wishes') }}<textarea v-model="wishes" rows="4" maxlength="4000" :placeholder="tr('例如：卖俄罗斯，做8张，暖色高级一点，主图字少，详情展示使用场景；尺寸只在主图展示。', 'Describe the market, style, scenes and what each image should emphasize. Choose the actual language and count below.')" /></label>
      <label>{{ tr('文案模型', 'Text model') }}<select v-model="model"><option value="" disabled>{{ tr('请选择', 'Choose') }}</option><option v-for="name in models" :key="name">{{ name }}</option></select></label>
      <label>{{ tr('文案语言', 'Copy language') }}<select v-model="language" :disabled="!!preset"><option value="" disabled>—</option><option value="ru">Русский</option><option value="en">English</option></select></label>
      <label>{{ tr('独立图片张数', 'Independent images') }}<select v-model="count"><option :value="null" disabled>—</option><option v-for="n in counts" :key="n" :value="n">{{ n }}</option></select></label>
      <label class="plan-check"><input v-model="confirmed" type="checkbox" />{{ tr('已核对选定商品、采集字段及补充事实；风格要求不作为商品参数。', 'I checked the product, imported fields and facts. Creative wishes are not specifications.') }}</label>
      <p v-if="cap && !cap.configured" role="alert">{{ tr('后端文案接口未配置，暂不能调用。', 'Text API is not configured.') }}</p>
      <button type="button" :disabled="!cap?.configured" @click="generate(false)">{{ tr('确认调用文案 API · 整理方案', 'Confirm text API call · create plan') }}</button>
      <button v-if="job?.status === 'failed' || job?.status === 'completed'" type="button" :disabled="!cap?.configured" @click="generate(true)">{{ tr('重新策划（新调用，可能再次计费）', 'New plan (new call, fees may apply)') }}</button>
    </fieldset>
    <p v-if="running" role="status">{{ tr('正在整理文案与逐页方案；不会开始生图。', 'Preparing bilingual storyboard. No images are being generated.') }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="job">{{ tr('当前任务', 'Current job') }}: {{ job.status }} <span v-if="job.error">{{ job.error }}</span></p>
    <button v-if="job?.status === 'pending'" :disabled="locked" type="button" @click="resume(job.plan_id)">{{ tr('查看任务状态（不重新调用）', 'Check status (no new model call)') }}</button>
    <label v-if="histories.length">{{ tr('已保存的策划记录', 'Saved plans') }}<select :disabled="locked" value="" @change="showJob(histories.find(h => h.plan_id === $event.target.value))"><option value="" disabled>—</option><option v-for="h in histories" :key="h.plan_id" :value="h.plan_id">{{ h.created_at.slice(0, 16) }} · {{ h.content?.product_name_zh || h.request?.wishes?.slice(0, 20) }} · {{ h.status }}</option></select></label>
    <fieldset v-if="content" :disabled="locked" @input="checked = false">
      <label>{{ tr('商品名称', 'Product name') }}<input v-model="content.product_name_zh" maxlength="100" /></label>
      <label>{{ tr('完整创作要求（可编辑）', 'Creative brief (editable)') }}<textarea v-model="content.brief_zh" maxlength="2000" rows="7" /></label>
      <ul v-if="content.notes_zh.length"><li v-for="(note, i) in content.notes_zh" :key="i">{{ note }}</li></ul>
      <details v-for="(page, index) in content.pages" :key="index" :open="index === 0">
        <summary>{{ index + 1 }} · {{ page.title.target }}</summary>
        <label>{{ tr('本页商品素材', 'Page product material') }}<select v-model="page.asset_id"><option v-for="id in job.request.image_ids" :key="id" :value="id">{{ id.slice(0, 8) }}</option></select></label>
        <img class="plan-source" :src="assetPreviewUrl(page.asset_id)" alt="" />
        <label>{{ tr('页面类型', 'Page type') }}<select v-model="page.kind" :disabled="index === 0"><option v-if="index === 0" value="main">{{ tr('主图', 'Main') }}</option><option value="feature">{{ tr('卖点', 'Feature') }}</option><option value="detail">{{ tr('细节', 'Detail') }}</option><option value="scene">{{ tr('场景', 'Scene') }}</option></select></label>
        <label>{{ tr('外语标题', 'Target headline') }}<textarea v-model="page.title.target" maxlength="90" rows="2" /></label>
        <label>{{ tr('标题中文翻译', 'Chinese headline translation') }}<textarea v-model="page.title.zh" maxlength="150" rows="2" /></label>
        <div v-for="(line, n) in page.copy_lines" :key="n">
          <label>{{ n + 1 }} · {{ tr('外语卖点', 'Target selling point') }}<textarea v-model="line.target" maxlength="80" rows="2" /></label>
          <label>{{ tr('对应中文翻译', 'Matching Chinese translation') }}<textarea v-model="line.zh" maxlength="150" rows="2" /></label>
          <button type="button" @click="removeLine(page, n)">{{ tr('删除这对卖点', 'Remove this pair') }}</button>
        </div>
        <button v-if="page.copy_lines.length < 4" type="button" @click="addLine(page)">{{ tr('添加一对双语卖点', 'Add a bilingual selling point') }}</button>
        <label>{{ tr('画面安排', 'Art direction') }}<textarea v-model="page.direction_zh" maxlength="400" rows="3" /></label>
      </details>
      <p>{{ tr('修改外语后请同步核对中文翻译。应用后还需选择制作方式、排字方式与质量。程序排版中的场景页需使用真实场景照片。', 'Keep translations in sync after editing. Choose production engine, typography and quality before generating. Local scene pages need actual scene photographs.') }}</p>
      <label class="plan-check"><input v-model="checked" type="checkbox" @input.stop />{{ tr('已逐页核对商品、文案、翻译和待补信息', 'I reviewed product facts, every page, translations and missing information') }}</label>
      <button type="button" :disabled="!checked" @click="apply">{{ tr('保存并应用到 PTMD（不开始生图）', 'Save & apply to PTMD (no image generation)') }}</button>
    </fieldset>
  </details>
</template>

<style scoped>
.plan-assistant{border:1px solid var(--border-glow);border-radius:10px;padding:12px;margin-bottom:16px;font-size:12px;color:var(--text-primary)}summary{cursor:pointer;font-weight:600;overflow-wrap:anywhere}p{line-height:1.7;color:var(--text-secondary)}fieldset{border:0;padding:0;margin:12px 0;display:flex;flex-direction:column;gap:10px;min-width:0}label{display:flex;flex-direction:column;gap:6px}input,textarea,select,button{font:inherit;color:var(--text-primary);background:var(--bg-card-strong);border:1px solid var(--border-dim);border-radius:7px;padding:8px;max-width:100%;box-sizing:border-box}textarea{width:100%;resize:vertical}button{cursor:pointer;margin:5px 0}button:disabled{opacity:.5;cursor:not-allowed}.plan-check{flex-direction:row;align-items:flex-start;line-height:1.6}.plan-check input{width:auto;flex:none}.plan-images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;max-height:260px;overflow:auto}.plan-images label{position:relative;padding:5px;border:1px solid var(--border-dim);border-radius:6px;cursor:pointer}.plan-images input{position:absolute;top:4px;left:4px}.plan-images img{width:100%;height:65px;object-fit:contain}.plan-images span{font-size:10px;text-align:center}.plan-source{max-width:100%;height:100px;object-fit:contain}dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:5px}dd{margin:0;overflow-wrap:anywhere}details details{border-top:1px solid var(--border-dim);padding:10px 0}details details label{margin:10px 0}[role=alert]{color:#dc8d3d}ul{padding-left:20px;line-height:1.6}
</style>
