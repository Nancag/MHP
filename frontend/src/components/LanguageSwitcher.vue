<script setup>
import { toRefs } from 'vue'
import { useAppContext } from '../composables/useAppContext'

const context = useAppContext()
const { toggleLocale } = context
const { locale } = toRefs(context)

function pick(code) {
  if (locale.value !== code) toggleLocale()
}
</script>

<template>
  <div class="langpill" role="group" aria-label="language">
    <button type="button" :class="{ on: locale === 'zh' }" @click="pick('zh')">中</button>
    <button type="button" :class="{ on: locale === 'en' }" @click="pick('en')">EN</button>
  </div>
</template>

<style scoped>
.langpill {
  display: flex;
  align-items: center;
  height: 34px;
  padding: 3px;
  border: 1px solid var(--line);
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.45);
}
[data-theme='dark'] .langpill { background: rgba(255, 255, 255, 0.05); }

.langpill button {
  height: 26px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.6px;
  color: var(--ink-3);
  transition: background var(--transition-fast), color var(--transition-fast);
}
.langpill button:hover { color: var(--ink); }
.langpill button.on { background: var(--ink); color: var(--paper); }
</style>
