<script setup>
import { reactive, watch } from 'vue'
import { values, defaults } from '../../parameters'
import ProductSetPanel from './ProductSetPanel.vue'
import { createSetDraft } from '../../ptmdDraft'

const props = defineProps({
  t: { type: Object, required: true },
  design: { type: Object, default: null },
  previewBusy: Boolean,
  setWorkflow:Boolean,
  setSpec:{type:Object,default:null},
  products:{type:Array,default:()=>[]},
  busy:Boolean,
  credits:{type:Number,default:null},
  referenceReady:Boolean,
  defaultResolution:{type:String,default:'2000'},
})

const emit = defineEmits(['change', 'update:design', 'preview', 'update:set-workflow', 'update:set-spec', 'apply-plan', 'planning'])

const fields = ['ratio', 'resolution', 'language', 'platform', 'scene', 'style']

const params = reactive(defaults())

function setField(field, value) {
  if(props.busy)return
  params[field] = value
  emitChange()
}

function reset() {
  if(props.busy)return
  if(props.setWorkflow){emit('update:set-spec',createSetDraft({},props.products[0]?.asset_id||'',props.defaultResolution));return}
  emit('update:design', null)
  Object.assign(params, defaults())
  emitChange()
}

watch(() => props.design?.kind, kind => {
  if (kind === 'russian_main') { params.ratio='3:4'; params.language='ru'; emitChange() }
})
function restore(value) { Object.assign(params, defaults(), value); emitChange() }
defineExpose({ restore })

function emitChange() {
  emit('change', { ...params })
}

emitChange()
</script>

<template>
  <aside class="wb-params">
    <div class="wb-params__header">
      <h3 class="wb-params__title">{{ t.ptmd.params.title }}</h3>
      <button class="wb-params__reset" type="button" :disabled="busy" @click="reset">
        <svg
          class="icon wb-params__reset-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M3 12 a9 9 0 1 0 3 -6.7 L3 8" />
          <path d="M3 3 v5 h5" />
        </svg>
        {{ t.ptmd.params.reset }}
      </button>
    </div>

    <div class="wb-params__body">
      <details class="wb-workflow-tools" :open="!setWorkflow">
      <summary>{{ t.account.breadcrumb==='Account'?'Other creative tools':'其他创作工具' }}</summary>
      <label class="wb-field-label">{{ t.account.breadcrumb==='Account'?'Creative workflow':'创作流程' }}
        <select class="wb-workflow-select" :value="setWorkflow?'set':'single'" :disabled="busy" @change="emit('update:set-workflow',$event.target.value==='set')"><option value="set">{{ t.account.breadcrumb==='Account'?'Reference-guided ecommerce set':'主图 + 示例 · 电商套图' }}</option><option value="single">{{ t.account.breadcrumb==='Account'?'Single image tools':'单图工具' }}</option></select>
      </label>
      </details>
      <ProductSetPanel v-if="setWorkflow&&setSpec" :model-value="setSpec" :products="products" :english="t.account.breadcrumb==='Account'" :busy="busy" :credits="credits" :ready="referenceReady" @update:model-value="emit('update:set-spec',$event)" @apply-plan="emit('apply-plan',$event)" @planning="emit('planning',$event)" />
      <template v-if="!setWorkflow">
      <p class="wb-field-hint">{{ t.ptmd.params.resolutionNote }}</p>
      <div v-for="field in fields" :key="field" class="wb-field">
        <span class="wb-field-label">
          {{ t.ptmd.params[field] }}
          <span v-if="field === 'ratio'" class="wb-field-hint">{{ t.ptmd.params.ratioHint }}</span>
        </span>
        <div class="wb-option-group">
          <button
            v-for="(option, index) in t.ptmd.params.options[field]"
            :key="option"
            class="wb-option"
            :class="{ 'wb-option--active': params[field] === values[field][index] }"
            type="button"
            :disabled="busy || (!!design && ((field === 'ratio' && values[field][index] !== '3:4') || (field === 'language' && values[field][index] !== 'ru')))"
            @click="setField(field, values[field][index])"
          >
            {{ option }}
          </button>
        </div>
      </div>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.wb-workflow-select{display:block;margin-top:8px;width:100%;padding:9px;border:1px solid var(--border-dim);border-radius:8px;background:var(--bg-card-strong);color:var(--text-primary);font:inherit}
.wb-workflow-tools>summary{cursor:pointer;color:var(--text-secondary);font-size:12px}.wb-workflow-tools[open]>summary{margin-bottom:10px}
.wb-params {
  position: relative;
  z-index: 20;
  width: var(--wb-param-w);
  min-width: var(--wb-param-w);
  display: flex;
  flex-direction: column;
  background: var(--bg-sidebar);
  border-left: 1px solid var(--border-dim);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  overflow: hidden;
}

.wb-params__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: none;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-dim);
}

.wb-params__title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  background: var(--logo-grad);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.wb-params__reset {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
  color: var(--text-secondary);
  font-size: 12px;
  transition: color var(--transition-fast), border-color var(--transition-fast),
    box-shadow var(--transition-smooth);
}

.wb-params__reset:hover {
  color: var(--neon-purple);
  border-color: var(--neon-purple);
  box-shadow: 0 0 10px var(--glow-purple);
}

.wb-params__reset-icon {
  width: 14px;
  height: 14px;
}

.wb-params__body {
  flex: 1;
  padding: 14px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
</style>
