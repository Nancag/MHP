<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ptmdTutorial } from '../../i18n/ptmdTutorial'

const props = defineProps({ english: Boolean, userId: { type: String, default: 'browser' } })
const dialog = ref(null)
const trigger = ref(null)
const heading = ref(null)
const stepIndex = ref(0)
const completed = ref(false)
const text = computed(() => ptmdTutorial[props.english ? 'en' : 'zh'])
const step = computed(() => text.value.steps[stepIndex.value])
const lastStep = computed(() => stepIndex.value === text.value.steps.length - 1)
const progressLabel = computed(() => text.value.step
  .replace('{current}', stepIndex.value + 1).replace('{total}', text.value.steps.length))
const storageKey = computed(() => `mhp-ptmd-tutorial-v1:${props.userId}`)

function saveProgress() {
  try {
    localStorage.setItem(storageKey.value, JSON.stringify({ step: stepIndex.value, completed: completed.value }))
  } catch { /* The tutorial still works when browser storage is unavailable. */ }
}

function openTutorial() {
  if (dialog.value?.open) return
  if (completed.value) stepIndex.value = 0
  dialog.value?.showModal()
}

function restoreProgress() {
  dialog.value?.close()
  stepIndex.value = 0
  completed.value = false
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey.value) || 'null')
    if (saved && Number.isInteger(saved.step) && saved.step >= 0 && saved.step < text.value.steps.length) {
      stepIndex.value = saved.step
      completed.value = saved.completed === true
    }
  } catch { /* Invalid or unavailable storage starts a fresh tutorial. */ }
  if (!completed.value) openTutorial()
}

function dismiss() {
  saveProgress()
  dialog.value?.close()
  trigger.value?.focus({ preventScroll: true })
}

async function moveStep(offset) {
  stepIndex.value = Math.max(0, Math.min(text.value.steps.length - 1, stepIndex.value + offset))
  saveProgress()
  await nextTick()
  heading.value?.focus({ preventScroll: true })
  heading.value?.closest('.ptmd-tutorial__body')?.scrollTo(0, 0)
}

function advance() {
  if (!lastStep.value) return moveStep(1)
  completed.value = true
  dismiss()
}

onMounted(restoreProgress)
watch(() => props.userId, restoreProgress)
onUnmounted(() => dialog.value?.close())
</script>

<template>
  <button ref="trigger" class="ptmd-tutorial-trigger" type="button" aria-haspopup="dialog" @click="openTutorial">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
      <path d="M12 5C8 3 5 3 2 4v15c3-1 6-1 10 1 4-2 7-2 10-1V4c-3-1-6-1-10 1Zm0 0v15" />
    </svg>
    {{ text.entry }}
  </button>

  <dialog ref="dialog" class="ptmd-tutorial" aria-labelledby="ptmd-tutorial-title" @cancel.prevent="dismiss">
    <div class="ptmd-tutorial__layout" :lang="english ? 'en' : 'zh-CN'">
      <header class="ptmd-tutorial__header">
        <div>
          <p class="ptmd-tutorial__eyebrow">PTMD · {{ text.entry }}</p>
          <h2 id="ptmd-tutorial-title">{{ text.title }}</h2>
          <p class="ptmd-tutorial__subtitle">{{ text.subtitle }}</p>
        </div>
        <button class="ptmd-tutorial__later" type="button" @click="dismiss">{{ text.later }}</button>
      </header>

      <div class="ptmd-tutorial__progress">
        <span role="status" aria-live="polite" aria-atomic="true">{{ progressLabel }}</span>
        <ol :aria-label="text.progress">
          <li v-for="(_, index) in text.steps" :key="index"
            :class="{ 'is-current': index === stepIndex, 'is-past': index < stepIndex }"
            :aria-current="index === stepIndex ? 'step' : undefined">
            <span>{{ index + 1 }}</span>
          </li>
        </ol>
      </div>

      <section class="ptmd-tutorial__body" aria-labelledby="ptmd-tutorial-step-title">
        <div class="ptmd-tutorial__scene">
          <span class="ptmd-tutorial__icon" aria-hidden="true">{{ step.icon }}</span>
          <span class="ptmd-tutorial__location">{{ step.location }}</span>
        </div>
        <h3 id="ptmd-tutorial-step-title" ref="heading" tabindex="-1">{{ step.title }}</h3>
        <p class="ptmd-tutorial__description">{{ step.description }}</p>
        <ul class="ptmd-tutorial__instructions">
          <li v-for="[label, detail] in step.items" :key="label">
            <strong>{{ label }}</strong>
            <p>{{ detail }}</p>
          </li>
        </ul>
        <blockquote v-if="step.example" class="ptmd-tutorial__example">{{ step.example }}</blockquote>
        <p class="ptmd-tutorial__tip"><span aria-hidden="true">💡</span> {{ step.tip }}</p>
      </section>

      <footer class="ptmd-tutorial__footer">
        <button class="ptmd-tutorial__previous" type="button" :disabled="stepIndex === 0" @click="moveStep(-1)">
          {{ text.previous }}
        </button>
        <button class="ptmd-tutorial__next" type="button" @click="advance" autofocus>
          {{ lastStep ? text.finish : text.next }} <span aria-hidden="true">{{ lastStep ? '✓' : '→' }}</span>
        </button>
      </footer>
    </div>
  </dialog>
</template>

<style scoped>
.ptmd-tutorial-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-inline-start: auto;
  white-space: nowrap;
  cursor: pointer;
}
.ptmd-tutorial-trigger svg { width: 16px; height: 16px; }
.ptmd-tutorial {
  width: min(620px, calc(100vw - 32px));
  max-width: none;
  max-height: min(840px, calc(100dvh - 32px));
  padding: 0;
  border: 1px solid var(--border-dim);
  border-radius: 24px;
  overflow: hidden;
  background: var(--bg-card-strong);
  color: var(--text-primary);
  box-shadow: 0 24px 90px #0005;
  font-family: inherit;
}
.ptmd-tutorial::backdrop { background: #0d1018a8; backdrop-filter: blur(5px); }
.ptmd-tutorial__layout { display: flex; flex-direction: column; max-height: inherit; }
.ptmd-tutorial__header { display: flex; align-items: flex-start; gap: 16px; padding: 26px 28px 20px; }
.ptmd-tutorial__header > div { flex: 1; min-width: 0; }
.ptmd-tutorial__eyebrow { margin: 0 0 10px; font-size: 11px; font-weight: 700; letter-spacing: 1.4px; color: var(--neon-blue); }
.ptmd-tutorial h2 { margin: 0; font-size: 23px; line-height: 1.35; }
.ptmd-tutorial__subtitle { margin: 9px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.ptmd-tutorial button { min-height: 44px; padding: 10px 16px; border: 1px solid var(--border-dim); border-radius: 12px; font: inherit; font-size: 13px; cursor: pointer; }
.ptmd-tutorial .ptmd-tutorial__later { flex: none; min-height: 36px; padding: 6px 10px; font-size: 12px; color: var(--text-secondary); background: var(--bg-glass); }
.ptmd-tutorial__progress { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 28px 20px; color: var(--text-secondary); font-size: 12px; }
.ptmd-tutorial__progress ol { display: flex; gap: 8px; list-style: none; padding: 0; margin: 0; }
.ptmd-tutorial__progress li { width: 28px; height: 28px; display: grid; place-items: center; border: 1px solid var(--border-dim); border-radius: 50%; font-size: 11px; }
.ptmd-tutorial__progress .is-current { background: var(--neon-blue); border-color: var(--neon-blue); color: var(--bg-card-strong); font-weight: 700; }
.ptmd-tutorial__progress .is-past { color: var(--neon-blue); border-color: var(--neon-blue); }
.ptmd-tutorial__body { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 22px 28px; border-top: 1px solid var(--border-dim); }
.ptmd-tutorial__scene { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.ptmd-tutorial__icon { display: grid; place-items: center; width: 52px; height: 52px; background: var(--bg-root); border: 1px solid var(--border-dim); border-radius: 16px; font-size: 29px; }
.ptmd-tutorial__location { color: var(--text-secondary); font-size: 12px; }
.ptmd-tutorial h3 { margin: 0 0 10px; font-size: 25px; line-height: 1.4; }
.ptmd-tutorial h3:focus { outline: none; }
.ptmd-tutorial__description { margin: 0 0 22px; font-size: 14px; line-height: 1.7; color: var(--text-secondary); }
.ptmd-tutorial__instructions { display: grid; gap: 16px; margin: 0; padding: 0; list-style: none; }
.ptmd-tutorial__instructions li { padding-inline-start: 14px; border-inline-start: 2px solid var(--border-dim); }
.ptmd-tutorial__instructions strong { font-size: 14px; }
.ptmd-tutorial__instructions p { margin: 5px 0 0; font-size: 13px; line-height: 1.8; color: var(--text-secondary); }
.ptmd-tutorial__example { margin: 18px 0 0; padding: 14px; border: 1px dashed var(--border-dim); border-radius: 12px; color: var(--text-primary); font-size: 12px; line-height: 1.8; }
.ptmd-tutorial__tip { margin: 22px 0 0; padding: 12px 14px; border-radius: 12px; background: var(--bg-root); color: var(--text-secondary); font-size: 12px; line-height: 1.8; }
.ptmd-tutorial__footer { flex: none; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 28px; border-top: 1px solid var(--border-dim); }
.ptmd-tutorial__previous { color: var(--text-primary); background: var(--bg-glass); }
.ptmd-tutorial__previous:disabled { opacity: .4; cursor: default; }
.ptmd-tutorial .ptmd-tutorial__next { min-width: 126px; display: flex; align-items: center; justify-content: center; gap: 20px; background: var(--text-primary); color: var(--bg-card-strong); border-color: var(--text-primary); font-weight: 600; }
.ptmd-tutorial button:focus-visible, .ptmd-tutorial-trigger:focus-visible { outline: 2px solid var(--neon-blue); outline-offset: 3px; }
@media (max-width: 480px) {
  .ptmd-tutorial { width: calc(100vw - 20px); max-height: calc(100dvh - 20px); border-radius: 18px; }
  .ptmd-tutorial__header { padding: 20px 18px 16px; gap: 10px; }
  .ptmd-tutorial h2 { font-size: 20px; }
  .ptmd-tutorial__progress { padding: 0 18px 16px; }
  .ptmd-tutorial__progress ol { gap: 5px; }
  .ptmd-tutorial__progress li { width: 24px; height: 24px; }
  .ptmd-tutorial__body { padding: 18px; }
  .ptmd-tutorial h3 { font-size: 23px; }
  .ptmd-tutorial__footer { padding: 14px 18px; }
}
</style>
