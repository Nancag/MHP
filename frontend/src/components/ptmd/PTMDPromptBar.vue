<script setup>
import { computed, ref } from 'vue'
import { parameterLabel } from '../../parameters'

const props = defineProps({
  t: { type: Object, required: true },
  canDownload: { type: Boolean, default: false },
  canRegenerate: { type: Boolean, default: false },
  generating: { type: Boolean, default: false },
  availableCredits: { type: Number, default: null },
  params: { type: Object, default: null },
  setMode:Boolean,
  planning:Boolean,
  requirements:{type:String,default:''},
  requiredCredits:{type:Number,default:1},
})

const emit = defineEmits(['generate', 'regenerate', 'download', 'notice', 'cancel', 'update:requirements'])

const prompt = ref('')
defineExpose({getPrompt:()=>prompt.value,setPrompt:value=>{prompt.value=value}})
const english=computed(()=>props.t.account.breadcrumb==='Account')

const paramChips = computed(() => {
  if (!props.params || !props.t.ptmd.prompt.paramFormat) return []
  const fmt = props.t.ptmd.prompt.paramFormat
  const chips = []
  if (props.params.scene) chips.push(fmt.scene.replace('{v}', parameterLabel(props.t, 'scene', props.params.scene)))
  if (props.params.style) chips.push(fmt.style.replace('{v}', parameterLabel(props.t, 'style', props.params.style)))
  if (props.params.platform) chips.push(fmt.platform.replace('{v}', parameterLabel(props.t, 'platform', props.params.platform)))
  if (props.params.ratio) chips.push(fmt.ratio.replace('{v}', props.params.ratio))
  if (props.params.resolution) chips.push(fmt.resolution.replace('{v}', props.params.resolution))
  return chips
})

function useSuggestion(text) {
  if(prompt.value.includes(text))return
  prompt.value = prompt.value ? `${prompt.value}，${text}` : text
}

function handleGenerate() {
  emit('generate', props.setMode?'':prompt.value.trim())
}
</script>

<template>
  <footer class="wb-promptbar">
    <div class="wb-promptbar__head">
      <span class="wb-promptbar__title">
        <svg
          class="icon wb-promptbar__title-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M21 15 a2 2 0 0 1 -2 2 H7 l-4 4 V5 a2 2 0 0 1 2 -2 h14 a2 2 0 0 1 2 2 Z" />
        </svg>
        {{ setMode ? (english?'Creative brief (optional)':'画面要求（选填）') : t.ptmd.prompt.title }}
      </span>
      <div v-if="!setMode" class="wb-promptbar__chips">
        <button
          v-for="suggestion in t.ptmd.prompt.suggestions"
          :key="suggestion"
          class="wb-chip"
          type="button"
          :disabled="prompt.includes(suggestion)"
          :aria-pressed="prompt.includes(suggestion)"
          @click="useSuggestion(suggestion)"
        >
          {{ suggestion }}
        </button>
      </div>
      <div v-if="paramChips.length" class="wb-promptbar__params">
        <span
          v-for="chip in paramChips"
          :key="chip"
          class="wb-param-chip"
        >{{ chip }}</span>
      </div>
    </div>

    <div class="wb-promptbar__row">
      <textarea
        :value="setMode?requirements:prompt"
        @input="setMode?emit('update:requirements',$event.target.value):prompt=$event.target.value"
        class="wb-promptbar__input"
        :placeholder="setMode ? (english?'Optional style and background instructions; exact text belongs in each page editor.':'补充整体风格与背景要求；需要显示在图上的文字请填写到每页文案中。') : t.ptmd.prompt.placeholder"
        rows="2"
        maxlength="2000"
      ></textarea>
      <button
        class="wb-promptbar__download"
        type="button"
        :disabled="!canDownload"
        :title="t.ptmd.prompt.download"
        @click="emit('download')"
      >
        <svg
          class="icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M12 4 v12 M7 11 l5 5 l5 -5 M5 21 h14" />
        </svg>
        <span>{{ setMode ? (english?'Download preview':'下载预览') : t.ptmd.prompt.download }}</span>
      </button>
      <button
        class="wb-promptbar__regenerate"
        type="button"
        :disabled="!canRegenerate || generating || planning || (availableCredits !== null && availableCredits < requiredCredits)"
        :title="t.ptmd.prompt.regenerate"
        @click="emit('regenerate')"
      >
        <svg
          class="icon"
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
        <span>{{ setMode ? (english?'Regenerate whole set':'重新生成整套') : t.ptmd.prompt.regenerate }}</span>
      </button>
      <button v-if="generating" class="wb-promptbar__regenerate" type="button" @click="emit('cancel')">{{ t.ptmd.prompt.cancel }}</button>
      <button
        class="wb-promptbar__generate"
        type="button"
        :disabled="generating || planning || (availableCredits !== null && availableCredits < requiredCredits)"
        @click="handleGenerate"
      >
        <svg
          v-if="!generating"
          class="icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="m12 3 -9 9 h5 v9 h8 v-9 h5 Z" />
        </svg>
        <span v-if="!generating">{{ setMode ? (english?`Generate ${requiredCredits} images`:`生成${requiredCredits}张电商图`) : t.ptmd.prompt.generate }}</span>
        <span v-else class="wb-promptbar__spin">{{ t.ptmd.prompt.generating }}</span>
      </button>
    </div>
  </footer>
</template>

<style scoped>
.wb-promptbar {
  position: relative;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: none;
  padding: 14px 18px;
  background: var(--bg-sidebar);
  border-top: 1px solid var(--border-dim);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.wb-promptbar__head {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.wb-promptbar__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.wb-promptbar__title-icon {
  width: 18px;
  height: 18px;
  color: var(--neon-purple);
  filter: drop-shadow(0 0 6px var(--glow-purple));
}

.wb-promptbar__chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.wb-promptbar__params {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.wb-param-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-glow);
  background: var(--bg-glass);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.wb-promptbar__row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.wb-promptbar__input {
  flex: 1;
  min-height: 52px;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  max-height: 120px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-smooth);
}

.wb-promptbar__input::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

.wb-promptbar__input:focus {
  outline: none;
  border-color: var(--neon-blue);
  box-shadow: 0 0 14px var(--glow-blue);
}

.wb-promptbar__download {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 13px 20px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-glow);
  background: var(--bg-glass);
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  transition: border-color var(--transition-fast), box-shadow var(--transition-smooth),
    transform var(--transition-fast), opacity var(--transition-fast);
}

.wb-promptbar__download:hover:not(:disabled) {
  border-color: var(--neon-blue);
  box-shadow: 0 0 12px var(--glow-blue);
  transform: translateY(-1px);
}

.wb-promptbar__download:active:not(:disabled) {
  transform: scale(0.97);
}

.wb-promptbar__download:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wb-promptbar__regenerate {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 13px 20px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-glow);
  background: var(--bg-glass);
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  transition: border-color var(--transition-fast), box-shadow var(--transition-smooth),
    transform var(--transition-fast), opacity var(--transition-fast);
}

.wb-promptbar__regenerate:hover:not(:disabled) {
  border-color: var(--neon-purple);
  box-shadow: 0 0 12px var(--glow-purple);
  transform: translateY(-1px);
}

.wb-promptbar__regenerate:active:not(:disabled) {
  transform: scale(0.97);
}

.wb-promptbar__regenerate:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wb-promptbar__generate {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 13px 24px;
  border-radius: var(--radius-full);
  background: var(--grad-btn);
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  box-shadow: 0 0 18px var(--glow-purple), 0 6px 22px rgba(59, 130, 246, 0.35);
  transition: filter var(--transition-fast), transform var(--transition-fast),
    box-shadow var(--transition-smooth);
  white-space: nowrap;
}

.wb-promptbar__generate:hover {
  filter: brightness(1.12) saturate(1.1);
  box-shadow: 0 0 26px var(--glow-purple);
  transform: translateY(-2px);
}

.wb-promptbar__generate:active {
  transform: scale(0.97);
}

.wb-promptbar__generate:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.wb-promptbar__spin {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.wb-promptbar__spin::before {
  content: '';
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: wbPromptSpin 0.8s linear infinite;
}

@keyframes wbPromptSpin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 767px) {
  .wb-promptbar__row { flex-wrap: wrap; }
  .wb-promptbar__input { flex-basis: 100%; min-width: 0; }
  .wb-promptbar {
    padding: 12px 14px;
  }
  .wb-promptbar__generate span,
  .wb-promptbar__download span,
  .wb-promptbar__regenerate span {
    display: none;
  }
  .wb-promptbar__generate {
    padding: 13px 18px;
  }
  .wb-promptbar__download,
  .wb-promptbar__regenerate {
    padding: 13px 16px;
  }
}
</style>
